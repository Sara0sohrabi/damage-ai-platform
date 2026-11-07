from fastapi.testclient import TestClient
from services.vehicle_vision.app.main import app
client=TestClient(app)

def _claim(cid):
    return {"claim_id":cid,"policy_number":"POL-WF-001","plate_number":"12الف345",
    "make":"IKCO","model":"Dena","year":1402,"accident_date":"2026-10-20",
    "city":"Tehran","claimed_amount_irr":1000000}

def test_claim_registration_detail_and_dashboard():
    response=client.post("/api/v1/claims",json=_claim("WF-CLAIM-001"))
    assert response.status_code==201
    assert response.json()["claim"]["make"]=="IKCO"
    assert client.get("/api/v1/claims/WF-CLAIM-001").status_code==200
    assert client.get("/api/v1/admin/dashboard").json()["claims"]["total_claims"]>=1

def test_fraud_screening_is_explainable_and_non_automatic():
    client.post("/api/v1/claims",json=_claim("WF-CLAIM-002"))
    client.post("/api/v1/claims",json=_claim("WF-CLAIM-003"))
    result=client.get("/api/v1/claims/WF-CLAIM-003/fraud-screening")
    assert result.status_code==200
    assert result.json()["alert_count"]>=1
    assert result.json()["automatic_decision"] is False
