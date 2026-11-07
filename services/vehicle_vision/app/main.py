from __future__ import annotations

import io
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from .inference import ModelNotConfigured, VehicleVisionModel
from .persistence import create_assessment, create_media, get_claim_results, initialize_database, save_analysis\nfrom .cost_model import CostModelNotConfigured, predict_repair_cost

MAX_IMAGE_BYTES = int(os.getenv("VEHICLE_VISION_MAX_IMAGE_BYTES", str(12 * 1024 * 1024)))
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MEDIA_ROOT = Path(os.getenv("VEHICLE_VISION_MEDIA_ROOT", "data/vehicle_media"))

app = FastAPI(title="Iran Vehicle Damage AI — Vision API", version="0.2.0",
              description="Vehicle evidence, visual damage analysis and expert review API.")
vision_model = VehicleVisionModel()


@app.on_event("startup")
def startup() -> None:
    initialize_database()


class AssessmentItem(BaseModel):
    operation_code: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=250)
    quantity: float = Field(default=1, gt=0)
    unit_price_irr: int = Field(ge=0)


class CostEstimateRequest(BaseModel):
    make: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=1300, le=2100)
    city: str = Field(min_length=1, max_length=100)
    part: str = Field(min_length=1, max_length=100)
    damage_type: str = Field(min_length=1, max_length=100)
    severity: str = Field(min_length=1, max_length=50)
    affected_area_pct: float = Field(ge=0, le=100)
    labor_hours: float = Field(ge=0, le=1000)


class AssessmentRequest(BaseModel):
    reviewer: str = Field(min_length=1, max_length=150)
    notes: str | None = None
    approved: bool = False
    items: list[AssessmentItem] = Field(default_factory=list)


def _read_image(file: UploadFile) -> tuple[bytes, Image.Image]:
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail={"code": "UNSUPPORTED_IMAGE_TYPE"})
    content = file.file.read(MAX_IMAGE_BYTES + 1)
    if not content:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_FILE"})
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail={"code": "IMAGE_TOO_LARGE", "max_bytes": MAX_IMAGE_BYTES})
    try:
        probe = Image.open(io.BytesIO(content))
        probe.verify()
        image = Image.open(io.BytesIO(content)).convert("RGB")
    except (UnidentifiedImageError, OSError, RuntimeError):
        raise HTTPException(status_code=400, detail={"code": "INVALID_IMAGE"})
    return content, image


def _run_inference(image: Image.Image) -> list[dict]:
    try:
        return vision_model.predict(image)
    except ModelNotConfigured as exc:
        raise HTTPException(status_code=503, detail={"code": "MODEL_NOT_CONFIGURED", "message": str(exc)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"code": "VISION_INFERENCE_FAILED", "message": str(exc)})


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "vehicle-vision", "model_configured": vision_model.ready,
            "device": vision_model._device, "model_path": str(vision_model.model_path)}


@app.post("/api/v1/vehicle/vision/analyze")
async def analyze_vehicle_image(file: UploadFile = File(...)) -> dict:
    _, image = _read_image(file)
    detections = _run_inference(image)
    return {"success": True, "analysis_id": str(uuid4()),
            "media": {"filename": file.filename, "content_type": file.content_type,
                      "width": image.width, "height": image.height},
            "model": {"path": str(vision_model.model_path), "device": vision_model._device,
                      "confidence_threshold": vision_model.confidence},
            "detections": detections, "detection_count": len(detections), "review_required": True}


@app.post("/api/v1/claims/{claim_id}/media")
async def upload_claim_media(claim_id: str, file: UploadFile = File(...)) -> dict:
    content, image = _read_image(file)
    media_id = str(uuid4())
    extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[file.content_type]
    destination = MEDIA_ROOT / media_id[:2] / f"{media_id}{extension}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    try:
        create_media(media_id=media_id, claim_id=claim_id, storage_key=str(destination),
                     filename=file.filename or f"{media_id}{extension}", content_type=file.content_type,
                     size_bytes=len(content), width=image.width, height=image.height)
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return {"success": True, "media_id": media_id, "claim_id": claim_id,
            "width": image.width, "height": image.height, "review_required": True}


@app.post("/api/v1/claims/{claim_id}/vision/analyze")
async def analyze_claim_media(claim_id: str, file: UploadFile = File(...)) -> dict:
    content, image = _read_image(file)
    media_id, analysis_id = str(uuid4()), str(uuid4())
    extension = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[file.content_type]
    destination = MEDIA_ROOT / media_id[:2] / f"{media_id}{extension}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    try:
        create_media(media_id=media_id, claim_id=claim_id, storage_key=str(destination),
                     filename=file.filename or f"{media_id}{extension}", content_type=file.content_type,
                     size_bytes=len(content), width=image.width, height=image.height)
        detections = _run_inference(image)
        save_analysis(analysis_id=analysis_id, claim_id=claim_id, media_id=media_id,
                      model_version=os.getenv("VEHICLE_VISION_MODEL_VERSION", "unversioned"),
                      device=vision_model._device, detections=detections)
    except Exception:
        # Evidence remains available if model weights are not installed or inference fails.
        raise
    return {"success": True, "claim_id": claim_id, "media_id": media_id, "analysis_id": analysis_id,
            "detections": detections, "detection_count": len(detections), "review_required": True}


@app.get("/api/v1/claims/{claim_id}/vision/result")
def claim_vision_results(claim_id: str) -> dict:
    return {"claim_id": claim_id, "results": get_claim_results(claim_id), "review_required": True}


@app.post("/api/v1/claims/{claim_id}/assessment")
def review_claim_assessment(claim_id: str, request: AssessmentRequest) -> dict:
    total = sum(round(item.quantity * item.unit_price_irr) for item in request.items)
    assessment_id = str(uuid4())
    create_assessment(assessment_id=assessment_id, claim_id=claim_id, reviewer=request.reviewer,
                      notes=request.notes, approved=request.approved,
                      items=[item.model_dump() for item in request.items], total_estimate_irr=total)
    return {"success": True, "assessment_id": assessment_id, "claim_id": claim_id,
            "total_estimate_irr": total, "currency": "IRR", "approved": request.approved,
            "reviewer": request.reviewer,
            "notice": "Estimate uses expert-entered prices; it is not an automated market-price prediction."}


@app.post("/api/v1/vehicle/repair-cost/estimate")
def estimate_vehicle_repair_cost(request: CostEstimateRequest) -> dict:
    try:
        result = predict_repair_cost(request.model_dump())
    except CostModelNotConfigured as exc:
        raise HTTPException(status_code=503, detail={"code": "COST_MODEL_NOT_CONFIGURED", "message": str(exc)})
    except Exception:
        raise HTTPException(status_code=500, detail={"code": "COST_MODEL_INFERENCE_FAILED"})
    return {
        "success": True,
        **result,
        "currency": "IRR",
        "review_required": True,
        "notice": "Indicative model estimate only; final amount requires expert approval.",
    }
