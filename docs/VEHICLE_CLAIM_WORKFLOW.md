# Vehicle claim workflow and Persian admin UI

The Vehicle Vision API now exposes a minimal Persian RTL claim-management UI at `GET /`.
It is intended for local development and workflow validation, not production deployment.

## Run

From the repository root:

```bash
pip install -r services/vehicle_vision/requirements-dev.txt
uvicorn services.vehicle_vision.app.main:app --host 127.0.0.1 --port 8010
```

Open `http://127.0.0.1:8010/`. API docs are at `/docs`; health is at `/health`.

The service uses SQLite by default (`./vehicle_vision.db`) unless
`VEHICLE_VISION_DATABASE_URL` or `DATABASE_URL` is configured. Docker Compose maps
the API to host port 8010 and stores media in its named volume.

## Claim workflow endpoints

- `POST /api/v1/claims`: register a claim.
- `GET /api/v1/claims?limit=50&offset=0`: list claims (optional status filter).
- `GET /api/v1/claims/{claim_id}`: claim detail.
- `GET /api/v1/admin/dashboard`: operational counters and claimed total.
- `GET /api/v1/claims/{claim_id}/fraud-screening`: explainable rule-based alerts.
- Existing media, vision analysis, assessment and repair-cost endpoints remain available.

Claim registration requires `claim_id`, `policy_number`, `plate_number`, `make`,
`model`, `year`, `accident_date`, and `city`. Amount is in IRR. Dates are retained
as supplied; integrations should standardize on ISO-8601 or a documented Jalali format.

## Fraud screening limitations

The initial rules flag a repeated plate/date, repeated policy/date, and an amount above
`VEHICLE_FRAUD_HIGH_AMOUNT_IRR` (default 5,000,000,000 IRR). These are triage signals,
not a fraud model, proof of fraud, or a basis for automatic rejection. The endpoint always
returns `automatic_decision: false`.

## Model readiness

The dashboard and claim registry do not require trained model weights. Image inference
still requires `models/vehicle_vision/vehicle_damage_yolo.pt`; repair-cost prediction
still requires `models/vehicle_vision/vehicle_repair_cost.joblib`. Neither artifact nor
a labeled training dataset is committed to this repository. A missing artifact returns
HTTP 503 by design. Do not present a rule alert, detector confidence, or empty detections
as a confirmed damage/fraud decision.

## Production blockers

Before exposing this service to real claimant data, add authentication and role-based
authorization, audit trails, encrypted private object storage, retention/deletion policy,
rate limiting, and deployment secrets. The current lightweight UI is a development
workflow screen and is not an authenticated production portal.
