"""Claim workflow, operational dashboard and explainable rule-based fraud screening."""
from __future__ import annotations
import os
from sqlalchemy import text
from .persistence import engine

SCHEMA = """CREATE TABLE IF NOT EXISTS vehicle_claims (
 claim_id VARCHAR(160) PRIMARY KEY, policy_number VARCHAR(100) NOT NULL,
 plate_number VARCHAR(30) NOT NULL, make VARCHAR(100) NOT NULL, model VARCHAR(100) NOT NULL,
 year INTEGER NOT NULL, accident_date VARCHAR(30) NOT NULL, city VARCHAR(100) NOT NULL,
 claimed_amount_irr BIGINT NOT NULL DEFAULT 0, claimant_name VARCHAR(150),
 status VARCHAR(30) NOT NULL DEFAULT 'submitted',
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"""

def initialize_workflow():
    with engine.begin() as conn:
        conn.execute(text(SCHEMA))

def _dict(row):
    if row is None: return None
    item = dict(row)
    if item.get("created_at"): item["created_at"] = item["created_at"].isoformat()
    return item

def create_claim_record(**values):
    initialize_workflow()
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO vehicle_claims
        (claim_id,policy_number,plate_number,make,model,year,accident_date,city,claimed_amount_irr,claimant_name)
        VALUES (:claim_id,:policy_number,:plate_number,:make,:model,:year,:accident_date,:city,:claimed_amount_irr,:claimant_name)"""), values)

def get_claim_record(claim_id):
    initialize_workflow()
    with engine.connect() as conn:
        row=conn.execute(text("SELECT * FROM vehicle_claims WHERE claim_id=:id"),{"id":claim_id}).mappings().first()
    return _dict(row)

def list_claim_records(status=None,limit=100,offset=0):
    initialize_workflow()
    query="SELECT * FROM vehicle_claims"
    params={"limit":limit,"offset":offset}
    if status:
        query+=" WHERE status=:status"
        params["status"]=status
    query+=" ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
    with engine.connect() as conn:
        rows=conn.execute(text(query),params).mappings().all()
    return [_dict(row) for row in rows]

def dashboard_summary():
    initialize_workflow()
    with engine.connect() as conn:
        row=conn.execute(text("""SELECT COUNT(*) AS total_claims,
        COALESCE(SUM(CASE WHEN status='submitted' THEN 1 ELSE 0 END),0) AS submitted,
        COALESCE(SUM(CASE WHEN status='under_review' THEN 1 ELSE 0 END),0) AS under_review,
        COALESCE(SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END),0) AS approved,
        COALESCE(SUM(claimed_amount_irr),0) AS total_claimed_irr FROM vehicle_claims""")).mappings().one()
    return {"claims":dict(row),"currency":"IRR"}

def screen_claim(claim):
    initialize_workflow()
    with engine.connect() as conn:
        same_plate=conn.execute(text("""SELECT COUNT(*) FROM vehicle_claims
        WHERE plate_number=:plate AND accident_date=:date AND claim_id<>:id"""),
        {"plate":claim["plate_number"],"date":claim["accident_date"],"id":claim["claim_id"]}).scalar_one()
        same_policy=conn.execute(text("""SELECT COUNT(*) FROM vehicle_claims
        WHERE policy_number=:policy AND accident_date=:date AND claim_id<>:id"""),
        {"policy":claim["policy_number"],"date":claim["accident_date"],"id":claim["claim_id"]}).scalar_one()
    alerts=[]
    if same_plate:
        alerts.append({"code":"POSSIBLE_DUPLICATE_VEHICLE_EVENT","severity":"high",
                       "detail":"Another claim has the same plate number and accident date."})
    if same_policy:
        alerts.append({"code":"MULTIPLE_CLAIMS_SAME_POLICY_DATE","severity":"medium",
                       "detail":"Another claim uses the same policy number and accident date."})
    threshold=int(os.getenv("VEHICLE_FRAUD_HIGH_AMOUNT_IRR","5000000000"))
    if int(claim["claimed_amount_irr"])>=threshold:
        alerts.append({"code":"HIGH_CLAIMED_AMOUNT","severity":"review",
                       "detail":"Claimed amount is above the configured review threshold."})
    return {"screening_type":"explainable_rules_v1","alert_count":len(alerts),
            "risk_level":"review" if alerts else "no_rule_alert","alerts":alerts,
            "automatic_decision":False}
