# Vehicle Vision service

Standalone FastAPI service for vehicle claim evidence, image inference and expert review.

## Local run (Apple Silicon / M5)

```bash
python3 -m venv .venv-vision
source .venv-vision/bin/activate
pip install -r services/vehicle_vision/requirements.txt
export VEHICLE_VISION_DATABASE_URL=sqlite:///./vehicle_vision.db
export VEHICLE_VISION_MODEL=models/vehicle_damage_yolo.pt
uvicorn services.vehicle_vision.app.main:app --reload --port 8010
```

PyTorch selects Apple MPS when available and otherwise CPU. No CUDA setup is needed on M-series Macs.

## API

- `GET /health`
- `POST /api/v1/vehicle/vision/analyze` — inference only
- `POST /api/v1/claims/{claim_id}/media` — persist validated image evidence
- `POST /api/v1/claims/{claim_id}/vision/analyze` — persist evidence and detections
- `GET /api/v1/claims/{claim_id}/vision/result` — retrieve analyses
- `POST /api/v1/claims/{claim_id}/assessment` — persist expert-entered repair items and total

Example:

```bash
curl -X POST http://localhost:8010/api/v1/claims/CLM-100/vision/analyze \
  -F "file=@./sample-car-damage.jpg"
```

Assessment body:

```json
{"reviewer":"adjuster-01","notes":"Workshop inspection required","approved":false,"items":[{"operation_code":"BUMPER_REPAIR","title":"Front bumper repair","quantity":1,"unit_price_irr":25000000}]}
```

Database URL: `VEHICLE_VISION_DATABASE_URL`, then `DATABASE_URL`; SQLite is the local default. Images are stored under `VEHICLE_VISION_MEDIA_ROOT` (default `data/vehicle_media`). Production should use private object storage and authenticated access.

## Model and safeguards

Weights are external and are not committed. Set `VEHICLE_VISION_MODEL` to trained YOLO weights. Until then inference returns HTTP 503. Detections are decision support and require human review. Assessment totals only expert-entered prices; no Iranian market price is fabricated.

Initial labels should cover vehicle parts (bumper, hood, doors, fender, lights, glass, mirror, wheel) and damage (scratch, dent, crack, broken_glass, deformation, missing_part). Version the annotation schema and evaluate per-class precision/recall and mAP before production.


## Training the vision model

Prepare a licensed, annotated YOLO dataset using [the dataset guide](../../data/vehicle_vision/README.md) and `data/vehicle_vision/damage_dataset.yaml`. Then run:

```bash
python -m services.vehicle_vision.scripts.train_vehicle_vision --epochs 100 --imgsz 960
```

The trainer selects MPS on Apple Silicon, otherwise CUDA or CPU, and exports `models/vehicle_vision/vehicle_damage_yolo.pt`.

## Training the repair-cost baseline

The repair-cost model is separate from the visual detector and from the fire/property model. It requires expert-approved Iranian invoice rows; the repository contains only a CSV header template, not fabricated training data.

```bash
python -m services.vehicle_vision.scripts.train_repair_cost --input /path/to/approved_repair_invoices.csv
```

The split is grouped by claim to reduce leakage. The artifact is saved to `models/vehicle_vision/vehicle_repair_cost.joblib`. Only deploy after reviewing held-out MAE/RMSE/R² and validating across vehicle makes, cities and repair types.
