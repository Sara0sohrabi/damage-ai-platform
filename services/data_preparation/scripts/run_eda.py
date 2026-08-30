import argparse, json, os
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text

DB=os.getenv("DATABASE_URL", "postgresql+psycopg://damage:damage_dev@localhost:5432/damage_ai")
FEATURES=["coverage_code","event_type_code","province_code","city_code","loss_location_code","occupation_code","occupation_group_code","damaged_item_code","damage_type_code","financial_damage_type_code","property_type_code","structure_type_code","risk_density_code","ownership_type_code","premium","item_sum_insured","total_sum_insured","estimate_amount"]
TARGET="paid_loss"

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--dataset-version",default="dataset_001"); ap.add_argument("--output",default="/reports"); args=ap.parse_args()
    engine=create_engine(DB)
    df=pd.read_sql(text("SELECT * FROM clean_damage_data WHERE dataset_version=:v ORDER BY id"), engine, params={"v":args.dataset_version})
    if df.empty: raise RuntimeError(f"No clean data for {args.dataset_version}")
    numeric=[c for c in ["premium","item_sum_insured","total_sum_insured","estimate_amount","paid_loss"] if c in df]
    summary={"rows":int(len(df)),"columns":int(len(df.columns)),"missing_cells":int(df.isna().sum().sum()),"duplicate_rows":int(df.duplicated().sum()),"numeric":{}}
    for c in numeric:
        s=pd.to_numeric(df[c],errors="coerce"); summary["numeric"][c]={"count":int(s.notna().sum()),"min":None if s.dropna().empty else float(s.min()),"max":None if s.dropna().empty else float(s.max()),"mean":None if s.dropna().empty else float(s.mean())}
    summary["coverage_counts"]=df.get("coverage_code",pd.Series(dtype=str)).astype(str).value_counts(dropna=False).to_dict()
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    path=out/f"eda_{args.dataset_version}.json"; path.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM eda_runs WHERE dataset_version=:v"),{"v":args.dataset_version})
        conn.execute(text("INSERT INTO eda_runs(dataset_version,report_version,row_count,column_count,missing_cells,duplicate_rows,summary_json,report_path) VALUES (:v,'eda_v1',:r,:c,:m,:d,CAST(:j AS jsonb),:p)"),{"v":args.dataset_version,"r":summary["rows"],"c":summary["columns"],"m":summary["missing_cells"],"d":summary["duplicate_rows"],"j":json.dumps(summary,ensure_ascii=False),"p":str(path)})
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
