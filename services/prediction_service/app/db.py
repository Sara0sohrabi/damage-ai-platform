import os
import json
from sqlalchemy import create_engine, text, inspect

DB = os.getenv('DATABASE_URL', 'postgresql+psycopg://damage:damage_dev@localhost:5434/damage_prediction_db')
engine = create_engine(DB, pool_pre_ping=True)


def init_prediction_schema():
    return None


def save_prediction(request_id, payload, predicted_loss, cluster, category, model_version, quality, metrics):
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO prediction_requests
            (request_id, customer_claim_id, request_payload, model_version)
            VALUES (:id, :claim, CAST(:payload AS jsonb), :version)"""), {
            'id': str(request_id), 'claim': str(request_id), 'payload': json.dumps(payload, ensure_ascii=False),
            'version': model_version})
        conn.execute(text("""INSERT INTO prediction_results
            (request_id, model_version, predicted_paid_loss)
            VALUES (:id, :version, :pred)"""), {
            'id': str(request_id), 'version': model_version, 'pred': predicted_loss})
        address = (payload.get('loss_location_address') or '').strip()
        if address:
            conn.execute(text('''INSERT INTO claim_loss_address (request_id, address)
                VALUES (:id, :address)'''), {'id': str(request_id), 'address': address})
        if any(payload.get(k) not in (None, '') for k in ('policyholder_national_id','policyholder_birth_date','policyholder_code','policyholder_name')):
            conn.execute(text('''INSERT INTO policyholder_identity
                (request_id,national_id,birth_date,policyholder_code,full_name)
                VALUES (:id,:national_id,:birth_date,:policyholder_code,:full_name)'''), {
                'id': str(request_id), 'national_id': payload.get('policyholder_national_id'),
                'birth_date': payload.get('policyholder_birth_date'),
                'full_name': payload.get('policyholder_name'),
                'policyholder_code': payload.get('policyholder_code')})


HISTORY_QUERY = """SELECT r.request_id,r.created_at,r.request_payload AS payload,
    (r.request_payload->>'estimate_amount')::numeric AS estimate_amount,
    p.predicted_paid_loss AS predicted_loss,a.paid_amount AS actual_paid_loss,
    r.model_version
    FROM prediction_requests r
    LEFT JOIN LATERAL (SELECT predicted_paid_loss FROM prediction_results
        WHERE request_id=r.request_id ORDER BY created_at DESC,id DESC LIMIT 1) p ON true
    LEFT JOIN LATERAL (SELECT paid_amount FROM claim_payment_results
        WHERE request_id=r.request_id ORDER BY received_at DESC,id DESC LIMIT 1) a ON true"""


def history(limit, offset):
    with engine.connect() as conn:
        total = conn.scalar(text('SELECT count(*) FROM prediction_requests'))
        rows = conn.execute(text(HISTORY_QUERY +
            ' ORDER BY r.created_at DESC,r.request_id DESC LIMIT :limit OFFSET :offset'),
            {'limit': limit, 'offset': offset}).mappings().all()
    items = []
    for row in rows:
        item = dict(row)
        actual, predicted = item['actual_paid_loss'], item['predicted_loss']
        error = abs(predicted - actual) if actual is not None and predicted is not None else None
        item.update(absolute_error=error, percentage_error=float(error / actual * 100)
                    if error is not None and actual != 0 else None,
                    status='compared' if error is not None else 'awaiting_actual')
        items.append(item)
    return {'items': items, 'total': total, 'limit': limit, 'offset': offset}


def bi_report():
    with engine.connect() as conn:
        summary = dict(conn.execute(text('WITH claims AS (' + HISTORY_QUERY + """ )
            SELECT count(*) AS total, count(predicted_loss) AS predicted_count,
            count(actual_paid_loss) AS paid_count,
            sum(estimate_amount) AS total_estimate, sum(predicted_loss) AS total_predicted,
            sum(actual_paid_loss) AS total_paid,
            avg(abs(predicted_loss-actual_paid_loss)) AS mae
            FROM claims""")).mappings().one())
        daily = [dict(r) for r in conn.execute(text('WITH claims AS (' + HISTORY_QUERY + """ )
            SELECT created_at::date AS day,count(*) AS count,sum(predicted_loss) AS predicted
            FROM claims GROUP BY created_at::date ORDER BY day DESC LIMIT 30""")).mappings()]
    return {'summary': summary, 'daily': daily, 'currency': 'IRR'}


def save_actual(request_id, actual):
    with engine.begin() as conn:
        return conn.execute(text('''UPDATE prediction_requests SET actual_paid_loss=:actual
            WHERE CAST(request_id AS text)=:id RETURNING request_id'''),
            {'id': str(request_id), 'actual': actual}).scalar() is not None


def mappings():
    result = {}
    with engine.connect() as conn:
        tables = set(inspect(conn).get_table_names())
        if 'mapping_values' in tables:
            for row in conn.execute(text('''SELECT mapping_name,mapped_code,mapped_title
                    FROM mapping_values WHERE active=true ORDER BY id''')).mappings():
                result.setdefault(row['mapping_name'] + '_code', {})[row['mapped_code']] = row['mapped_title']
        # Accept the project's domain lookup tables even when they are named
        # differently from the seed tables (province/city are common examples).
        for table in sorted(tables):
            if table in {'province','city','coverage','event_type','insured_item','damage_type','financial_damage_type','occupation','occupation_group','loss_location','structure_type','risk_density','ownership_type','property_type','insurance_type'}:
                cols = {c['name'] for c in inspect(conn).get_columns(table)}
                if 'code' in cols and 'title' in cols:
                    key = table + '_code'
                    select_cols = 'code, title' + (', province_code' if table == 'city' and 'province_code' in cols else '') + (', occupation_group_code' if table == 'occupation' and 'occupation_group_code' in cols else '')
                    for row in conn.execute(text(f'SELECT {select_cols} FROM "{table}" WHERE active=true ORDER BY code')).mappings():
                        result.setdefault(key, {})[str(row['code'])] = str(row['title'])
                        if table == 'city' and row.get('province_code') is not None:
                            result.setdefault('city_province_code', {})[str(row['code'])] = str(row['province_code'])
                        if table == 'occupation' and row.get('occupation_group_code') is not None:
                            result.setdefault('occupation_group_map', {})[str(row['code'])] = str(row['occupation_group_code'])
                continue
            if not table.endswith('_mapping') or table == 'mapping_values':
                continue
            cols = {c['name'] for c in inspect(conn).get_columns(table)}
            code_col = next((c for c in ('mapped_code', 'code', 'province_code', 'city_code') if c in cols), None)
            title_col = next((c for c in ('mapped_title', 'title', 'name', 'province_name', 'city_name') if c in cols), None)
            if not code_col or not title_col:
                continue
            key = table[:-8] + '_code'
            for row in conn.execute(text(f'SELECT "{code_col}" AS code, "{title_col}" AS title FROM "{table}"')).mappings():
                if row['code'] is not None and row['title']:
                    result.setdefault(key, {})[str(row['code'])] = str(row['title'])
        names = ['coverage','damage_type','event_type','loss_location','occupation','occupation_group',
                 'damaged_item','financial_damage_type','structure_type','risk_density','ownership_type','property_type']
        for name in names:
            table = name + '_mapping'
            if table in tables:
                for row in conn.execute(text(f'SELECT mapped_code,mapped_title FROM {table} WHERE active=true')).mappings():
                    result.setdefault(name + '_code', {})[row['mapped_code']] = row['mapped_title']
    return {key: [{'code': code, 'title': title} for code, title in values.items()] for key, values in result.items()}
