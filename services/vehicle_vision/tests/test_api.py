from fastapi.testclient import TestClient

from services.vehicle_vision.app.main import app


def test_health_reports_service():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "vehicle-vision"


def test_assessment_totals_expert_entered_items():
    client = TestClient(app)
    response = client.post(
        "/api/v1/claims/TEST-CLAIM/assessment",
        json={
            "reviewer": "qa-reviewer",
            "approved": False,
            "items": [
                {"operation_code": "PART", "title": "Part replacement", "quantity": 2, "unit_price_irr": 1500},
                {"operation_code": "LABOR", "title": "Labor", "quantity": 1, "unit_price_irr": 500},
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["total_estimate_irr"] == 3500
    assert response.json()["approved"] is False


def test_cost_estimate_is_unavailable_without_trained_artifact():
    client = TestClient(app)
    response = client.post(
        "/api/v1/vehicle/repair-cost/estimate",
        json={
            "make": "Saipa", "model": "Tiba", "year": 1398, "city": "Tehran",
            "part": "front_bumper", "damage_type": "dent", "severity": "moderate",
            "affected_area_pct": 20, "labor_hours": 3,
        },
    )
    assert response.status_code == 503
