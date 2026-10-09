"""Copy a verified, unchanged-code snapshot from training to prediction.

Source transaction is READ ONLY. Destination changes are atomic and additive.
Existing master rows must match exactly; this command never overwrites them.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

DOMAINS = {
    'coverage': 'coverage_mapping', 'event_type': 'event_type_mapping',
    'insured_item': 'damaged_item_mapping', 'damage_type': 'damage_type_mapping',
    'financial_damage_type': 'financial_damage_type_mapping',
    'occupation_group': 'occupation_group_mapping', 'loss_location': 'loss_location_mapping',
    'structure_type': 'structure_type_mapping', 'risk_density': 'risk_density_mapping',
    'ownership_type': 'ownership_type_mapping', 'property_type': 'property_type_mapping',
}
RAW_PAIRS = {
    'coverage': ('Coverage_Code', 'CoverageTitel'),
    'damage_type': ('کد نوع خسارت', 'نوع خسارت'),
}


def row(code, title, source, version='mapping_001', active=True, **extra):
    if code is None:
        raise ValueError(f'Missing code in {source}')
    return dict(code=str(code), title=title, source_table=source,
                source_version=version, active=active, requires_review=False, **extra)


def snapshot(conn):
    data = {}
    for name, source in DOMAINS.items():
        records = conn.execute(sql.SQL('SELECT * FROM {} ORDER BY mapped_code').format(sql.Identifier(source))).fetchall()
        data[name] = [row(r['mapped_code'], r['mapped_title'], source,
                          r['mapping_version'], r['active']) for r in records]
    for name, code_key, title_key in [('province','ProvinceName_Code','ProvinceName'),
                                      ('city','CityName_Code','CityName')]:
        records = conn.execute('''SELECT DISTINCT raw_data->>%s AS code,
            raw_data->>%s AS title, raw_data->>'ProvinceName_Code' AS province_code
            FROM raw_damage_data''', (code_key,title_key)).fetchall()
        data[name] = [row(r['code'],r['title'],'raw_damage_data',
                         **({'province_code':r['province_code']} if name=='city' else {})) for r in records]
    data['occupation'] = [row(r['activity_code'],r['activity_title'],'occupation_activity_mapping',
                               r['mapping_version'],r['active'],occupation_group_code=r['macro_group_code'])
                          for r in conn.execute('SELECT * FROM occupation_activity_mapping').fetchall()]
    data['insurance_type'] = [row(r['code'],r['title'],'insurance_type_mapping') for r in conn.execute(
        'SELECT DISTINCT insurance_type_code AS code,insurance_type_name AS title FROM insurance_type_mapping').fetchall()]
    data['insured_item_type'] = [row(r['code'],r['title'],'raw_damage_data') for r in conn.execute(
        "SELECT DISTINCT raw_data->>'Moredbime_Code' AS code,raw_data->>'Moredbime' AS title FROM raw_damage_data").fetchall()]
    conflicts = []
    for name,(code_key,title_key) in RAW_PAIRS.items():
        raw = conn.execute('SELECT DISTINCT raw_data->>%s AS code,raw_data->>%s AS title FROM raw_damage_data',
                           (code_key,title_key)).fetchall()
        generic = conn.execute('SELECT mapped_code AS code,mapped_title AS title FROM mapping_values WHERE mapping_name=%s', (name,)).fetchall()
        for record in data[name]:
            titles = {r['title'].strip() for r in raw+generic if r['code']==record['code'] and r['title'] and r['title'].strip()}
            titles.add(record['title'].strip())
            if len(titles)>1:
                record['requires_review']=True
                conflicts.append({'table':name,'code':record['code'],'titles':sorted(titles)})
    for name, records in data.items():
        codes = [r['code'] for r in records]
        if len(codes)!=len(set(codes)):
            raise ValueError(f'Conflicting duplicate codes in {name}; nothing transferred')
        for record in records:
            title = record['title'] or ''
            if not title.strip() or title.startswith('Value ') or title in ('-100','فاقد مقدار'):
                record['requires_review']=True
        records.sort(key=lambda r:r['code'])
    for child, field, parent in [('city','province_code','province'),('occupation','occupation_group_code','occupation_group')]:
        parents={r['code'] for r in data[parent]}
        if any(r[field] not in parents for r in data[child]):
            raise ValueError(f'Orphan relationship in {child}')
    return data, conflicts


def apply(conn, data):
    order=['province','occupation_group']+[k for k in data if k not in ('province','occupation_group')]
    for name in order:
        parent = 'province' if name=='city' else 'occupation_group' if name=='occupation' else None
        relation = sql.SQL(', {} TEXT NOT NULL REFERENCES {}(code)').format(
            sql.Identifier(parent+'_code'), sql.Identifier(parent)) if parent else sql.SQL('')
        conn.execute(sql.SQL('''CREATE TABLE IF NOT EXISTS {} (
            code TEXT PRIMARY KEY, title TEXT, source_table TEXT NOT NULL,
            source_version TEXT NOT NULL, active BOOLEAN NOT NULL,
            requires_review BOOLEAN NOT NULL DEFAULT false {})''').format(sql.Identifier(name),relation))
        for record in data[name]:
            old=conn.execute(sql.SQL('SELECT * FROM {} WHERE code=%s').format(sql.Identifier(name)),(record['code'],)).fetchone()
            if old is not None:
                if dict(old)!=record:
                    raise ValueError(f'Existing {name} code {record["code"]} differs; transaction rolled back')
                continue
            conn.execute(sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(name),
                sql.SQL(',').join(map(sql.Identifier,record)),
                sql.SQL(',').join(sql.Placeholder() for _ in record)), list(record.values()))
        actual=conn.execute(sql.SQL('SELECT * FROM {} ORDER BY code').format(sql.Identifier(name))).fetchall()
        if sorted(actual,key=lambda r:r['code']) != data[name]:
            raise ValueError(f'Snapshot verification failed: {name}')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    source=os.environ['TRAINING_DATABASE_URL']
    target=os.environ['PREDICTION_DATABASE_URL']
    with psycopg.connect(source,row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        assert conn.execute('SELECT current_database() AS name').fetchone()['name']=='damage_ai'
        data,conflicts=snapshot(conn)
        metrics=conn.execute("SELECT model_version,mae,rmse,r2,within_10pct,within_20pct FROM model_runs WHERE model_version='damagefire_001_gradient_boosting_raw_v2'").fetchone()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=Path('backups')/('master-data-'+stamp+'.json')
    backup.parent.mkdir(exist_ok=True)
    backup.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    if args.apply:
        with psycopg.connect(target,row_factory=dict_row) as conn:
            assert conn.execute('SELECT current_database() AS name').fetchone()['name']=='damage_prediction_db'
            apply(conn,data)
    report={'applied':args.apply,'source':'damage_ai','target':'damage_prediction_db',
            'backup':str(backup),'counts':{k:len(v) for k,v in data.items()},'conflicts':conflicts,
            'review_counts':{k:sum(r['requires_review'] for r in v) for k,v in data.items()}}
    Path('docs/master-data-import.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    model_path=Path('models/damagefire_001_gradient_boosting_raw_v2.joblib')
    if metrics and model_path.exists():
        meta={'version':metrics['model_version'], 'sha256':hashlib.sha256(model_path.read_bytes()).hexdigest(),
              'metrics':{k:float(v) if v is not None else None for k,v in metrics.items() if k!='model_version'},
              'source':'damage_ai.model_runs', 'dataset_version':None}
        model_path.with_suffix('.json').write_text(json.dumps(meta,indent=2))
    print(json.dumps(report,ensure_ascii=False,indent=2))
