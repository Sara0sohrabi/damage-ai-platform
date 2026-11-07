# Iran Vehicle Damage AI — Integration plan

## Product goal
Assess Iranian motor-vehicle claims from photos and video:
1. Identify visible vehicle body parts.
2. Detect and localize visible damage.
3. Estimate damage severity and affected area.
4. Convert reviewed visual findings into repair operations and estimated cost.
5. Preserve expert approval and audit history.

## Existing platform reuse
- Keep the current React/Vite frontend and FastAPI financial-claim API.
- Keep the existing fire/property financial model separate.
- Reuse the existing claim evidence concept and PostgreSQL infrastructure.
- Add the new vision service under `services/vehicle_vision`.

## Target flow
```text
Claim UI
  -> upload images/video
  -> evidence storage + metadata
  -> vehicle vision inference
       -> vehicle part detections
       -> damage detections / masks
       -> severity features
  -> expert review / correction
  -> repair operation catalogue + Iranian price catalogue
  -> motor repair-cost model
  -> final adjuster approval
```

## Planned endpoints
- `POST /api/v1/vehicle/vision/analyze` (implemented in the standalone vision app)
- `POST /api/v1/claims/{claim_id}/media` (next: persistent media storage)
- `POST /api/v1/claims/{claim_id}/vision/analyze` (next: claim-linked orchestration)
- `GET /api/v1/claims/{claim_id}/vision/result` (next: persisted result)
- `POST /api/v1/claims/{claim_id}/assessment` (next: expert-reviewed estimate)

## Data model to add
- `vehicle_claims`
- `vehicle_claim_media`
- `vehicle_vision_analyses`
- `vehicle_damage_detections`
- `vehicle_repair_operations`
- `vehicle_price_catalog`
- `vehicle_assessment_reviews`

Store media in object storage; store only object keys and metadata in PostgreSQL. Never store large image/video blobs in relational rows.

## Model roadmap
- Stage A: public datasets for vehicle parts and damage, label normalization and dataset cards.
- Stage B: part detection/segmentation model.
- Stage C: damage detection/segmentation model with severity labels.
- Stage D: video frame sampling, duplicate suppression and cross-frame tracking.
- Stage E: repair-cost estimation trained on Iranian invoices, part prices and expert-approved claims.

## Hardware
The development target is the user's Apple Silicon M5 Mac. Use PyTorch MPS when available and CPU fallback. Do not configure CUDA for local M5 execution. Production GPU deployment can be selected independently later.

## Important safeguards
- Current vision API returns 503 until project-specific trained weights are installed.
- Model detections are decision support, not a final claim decision.
- Keep model version, dataset version, confidence, source media and expert edits auditable.
- Do not use the existing property/fire loss model to estimate motor repair costs.
