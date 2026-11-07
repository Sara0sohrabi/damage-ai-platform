from __future__ import annotations

import io
import os
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from .inference import ModelNotConfigured, VehicleVisionModel

MAX_IMAGE_BYTES = int(os.getenv("VEHICLE_VISION_MAX_IMAGE_BYTES", str(12 * 1024 * 1024)))
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}

app = FastAPI(
    title="Iran Vehicle Damage AI — Vision API",
    version="0.1.0",
    description="Vehicle-part and visible-damage inference module for Damage AI Platform.",
)
vision_model = VehicleVisionModel()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "vehicle-vision",
        "model_configured": vision_model.ready,
        "device": vision_model._device,
        "model_path": str(vision_model.model_path),
    }


@app.post("/api/v1/vehicle/vision/analyze")
async def analyze_vehicle_image(file: UploadFile = File(...)) -> dict:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail={"code": "UNSUPPORTED_IMAGE_TYPE", "allowed": sorted(ALLOWED_CONTENT_TYPES)},
        )

    content = await file.read(MAX_IMAGE_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_FILE"})
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"code": "IMAGE_TOO_LARGE", "max_bytes": MAX_IMAGE_BYTES},
        )

    try:
        probe = Image.open(io.BytesIO(content))
        probe.verify()
        image = Image.open(io.BytesIO(content)).convert("RGB")
    except (UnidentifiedImageError, OSError, RuntimeError):
        raise HTTPException(status_code=400, detail={"code": "INVALID_IMAGE"})

    analysis_id = str(uuid4())
    try:
        detections = vision_model.predict(image)
    except ModelNotConfigured as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "MODEL_NOT_CONFIGURED", "message": str(exc)},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "VISION_INFERENCE_FAILED", "message": str(exc)},
        )

    return {
        "success": True,
        "analysis_id": analysis_id,
        "media": {
            "filename": file.filename,
            "content_type": file.content_type,
            "width": image.width,
            "height": image.height,
        },
        "model": {
            "path": str(vision_model.model_path),
            "device": vision_model._device,
            "confidence_threshold": vision_model.confidence,
        },
        "detections": detections,
        "detection_count": len(detections),
        "review_required": True,
    }
