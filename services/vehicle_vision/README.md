# Iran Vehicle Damage AI — Computer Vision module

This module adds vehicle-image inspection to the existing Damage AI Platform without replacing its financial claim model or frontend.

## Current MVP scope
- Image upload and validation
- Vehicle part / damage inference through a custom Ultralytics YOLO model
- Bounding-box output and optional segmentation polygons
- Model health and clear `MODEL_NOT_CONFIGURED` response when trained weights are absent

> No pretrained weights are bundled. The service must not claim to detect damage until a model trained for the project's labels is supplied.

## Run locally (Apple Silicon / M5)
From the repository root:

```bash
python3 -m venv .venv-vision
source .venv-vision/bin/activate
pip install -r services/vehicle_vision/requirements.txt
export VEHICLE_VISION_MODEL=models/vehicle_damage_yolo.pt
uvicorn services.vehicle_vision.app.main:app --reload --port 8010
```

PyTorch should be installed with an Apple-Silicon-compatible build. The inference adapter selects MPS when available and falls back to CPU. Docker CPU inference remains supported; do not use NVIDIA CUDA settings on an M5 Mac.

## API
- `GET /health`
- `POST /api/v1/vehicle/vision/analyze` — multipart form field `file`

Example:

```bash
curl -X POST http://localhost:8010/api/v1/vehicle/vision/analyze \
  -F "file=@./sample-car-damage.jpg"
```

The response contains detections, class names, confidence, bounding boxes and segmentation polygons when the selected model provides masks.

## Label design (initial)
Keep part and damage classes explicit and versioned. A practical first label set is:
- Parts: front_bumper, rear_bumper, hood, trunk, roof, windshield, front_left_door, front_right_door, rear_left_door, rear_right_door, fender, headlight, taillight, side_mirror, wheel
- Damage: scratch, dent, crack, broken_glass, deformation, missing_part

For a production model, use a two-stage or multi-head dataset design so part localization and damage classification are not confused. Store dataset version, annotation schema, model version and evaluation metrics with every training run.

## Integration boundary
The existing financial prediction endpoint remains unchanged. The vision output should later be transformed into reviewed claim features (damaged part, damage type, severity, affected area, confidence) and passed into a separately trained repair-cost model. Do not feed raw detection scores directly into the current fire/property-loss model.
