from __future__ import annotations

import io
import os
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from .inference import ModelNotConfigured, VehicleVisionModel
from .persistence import create_assessment, create_media, get_claim_results, initialize_database, save_analysis
from .cost_model import CostModelNotConfigured, predict_repair_cost

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
            "device": vision_model._device, "model_path": str(vision_model.model_path), "cost_model_configured": Path(os.getenv("VEHICLE_REPAIR_COST_MODEL", "models/vehicle_vision/vehicle_repair_cost.joblib")).is_file()}


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


# Claim workflow, management dashboard and explainable fraud screening.
from .workflow import create_claim_record, get_claim_record, list_claim_records, dashboard_summary, screen_claim

class ClaimCreate(BaseModel):
    claim_id: str = Field(min_length=3, max_length=160)
    policy_number: str = Field(min_length=2, max_length=100)
    plate_number: str = Field(min_length=5, max_length=30)
    make: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    year: int = Field(ge=1300, le=2100)
    accident_date: str = Field(min_length=8, max_length=30)
    city: str = Field(min_length=1, max_length=100)
    claimed_amount_irr: int = Field(default=0, ge=0)
    claimant_name: str | None = Field(default=None, max_length=150)

@app.post("/api/v1/claims", status_code=201)
def register_claim(request: ClaimCreate):
    try:
        create_claim_record(**request.model_dump())
    except Exception as exc:
        if "unique" in str(exc).lower():
            raise HTTPException(status_code=409, detail={"code":"CLAIM_ALREADY_EXISTS"})
        raise
    return {"success":True,"claim":get_claim_record(request.claim_id)}

@app.get("/api/v1/claims")
def claims_list(status: str | None = None, limit: int = 100, offset: int = 0):
    if limit < 1 or limit > 500 or offset < 0:
        raise HTTPException(status_code=422, detail={"code":"INVALID_PAGINATION"})
    return {"items":list_claim_records(status=status,limit=limit,offset=offset),
            "limit":limit,"offset":offset}

@app.get("/api/v1/claims/{claim_id}")
def claim_detail(claim_id: str):
    record=get_claim_record(claim_id)
    if not record: raise HTTPException(status_code=404,detail={"code":"CLAIM_NOT_FOUND"})
    return {"claim":record}

@app.get("/api/v1/admin/dashboard")
def admin_dashboard():
    return dashboard_summary()

@app.get("/api/v1/claims/{claim_id}/fraud-screening")
def claim_fraud_screening(claim_id: str):
    claim=get_claim_record(claim_id)
    if not claim: raise HTTPException(status_code=404,detail={"code":"CLAIM_NOT_FOUND"})
    return {"claim_id":claim_id,**screen_claim(claim),
            "notice":"Rule-based screening only. Alerts are not proof of fraud and must not trigger automatic claim rejection."}

@app.get('/', response_class=HTMLResponse, include_in_schema=False)
def admin_ui():
    return HTMLResponse('''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مدیریت خسارت خودرو</title><style>body{font-family:Tahoma;background:#f3f5f8;color:#182230;margin:0}header{background:#101828;color:white;padding:22px}main{max-width:1100px;margin:24px auto;padding:0 16px}.grid,.fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.card,form{background:white;border:1px solid #ddd;border-radius:12px;padding:16px;margin-bottom:16px}.metric{font-size:25px;font-weight:bold}label{display:block;margin:8px 0 4px}input{width:100%;padding:10px;border:1px solid #ccc;border-radius:7px;box-sizing:border-box}button{background:#175cd3;color:white;border:0;border-radius:7px;padding:10px;cursor:pointer;margin-top:10px}table{width:100%;border-collapse:collapse}td,th{text-align:right;padding:9px;border-bottom:1px solid #eee}.notice{background:#fffaeb;padding:12px;border-radius:8px}</style></head><body><header><h2>سامانه هوشمند ارزیابی خسارت خودرو</h2>مدیریت پرونده‌ها و بررسی کارشناسی</header><main><p class="notice">هشدارهای تقلب صرفاً برای اولویت‌بندی بررسی هستند؛ نه اثبات تقلب و نه رد خودکار خسارت.</p><div class="grid"><div class="card">کل پرونده‌ها<div class="metric" id="total">—</div></div><div class="card">ثبت‌شده<div class="metric" id="submitted">—</div></div><div class="card">در حال بررسی<div class="metric" id="review">—</div></div><div class="card">مجموع مبلغ (ریال)<div class="metric" id="amount">—</div></div></div><form id="f"><h3>ثبت پرونده</h3><div class="fields"><div>شناسه پرونده<input name="claim_id" required></div><div>بیمه‌نامه<input name="policy_number" required></div><div>پلاک<input name="plate_number" required></div><div>سازنده<input name="make" value="IKCO" required></div><div>مدل<input name="model" required></div><div>سال ساخت<input name="year" type="number" min="1300" max="2100" required></div><div>تاریخ حادثه<input name="accident_date" placeholder="1405-08-16" required></div><div>شهر<input name="city" value="Tehran" required></div><div>مبلغ اعلامی (ریال)<input name="claimed_amount_irr" type="number" min="0" value="0"></div><div>نام بیمه‌گذار<input name="claimant_name"></div></div><button>ثبت پرونده</button><span id="msg"></span></form><section class="card"><h3>پرونده‌های اخیر</h3><button id="refresh">به‌روزرسانی</button><table><thead><tr><th>شناسه</th><th>خودرو</th><th>پلاک</th><th>مبلغ</th><th>بررسی</th></tr></thead><tbody id="rows"></tbody></table></section></main><script>const n=x=>Number(x||0).toLocaleString('fa-IR');async function load(){let [a,b]=await Promise.all([fetch('/api/v1/admin/dashboard'),fetch('/api/v1/claims?limit=50')]);let s=(await a.json()).claims,L=(await b.json()).items;for(let [id,v] of Object.entries({total:s.total_claims,submitted:s.submitted,review:s.under_review,amount:n(s.total_claimed_irr)}))document.getElementById(id).textContent=n(v);let root=document.getElementById('rows');root.replaceChildren();for(let x of L){let tr=document.createElement('tr');for(let v of [x.claim_id,x.make+' '+x.model,x.plate_number,n(x.claimed_amount_irr)]){let td=document.createElement('td');td.textContent=v;tr.append(td)}let td=document.createElement('td'),btn=document.createElement('button');btn.textContent='هشدارها';btn.onclick=()=>screening(x.claim_id);td.append(btn);tr.append(td);root.append(tr)}}async function screening(id){let r=await fetch('/api/v1/claims/'+encodeURIComponent(id)+'/fraud-screening'),j=await r.json();alert(j.alerts?.length?j.alerts.map(x=>x.code+': '+x.detail).join('\\n'):'هشدار قاعده‌محور یافت نشد؛ این نتیجه نبود تقلب را ثابت نمی‌کند.')}document.getElementById('f').onsubmit=async e=>{e.preventDefault();let v=Object.fromEntries(new FormData(e.target));v.year=Number(v.year);v.claimed_amount_irr=Number(v.claimed_amount_irr);let r=await fetch('/api/v1/claims',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(v)}),j=await r.json();document.getElementById('msg').textContent=r.ok?' ثبت شد':JSON.stringify(j.detail||j);if(r.ok){e.target.reset();load()}};document.getElementById('refresh').onclick=load;load();</script></body></html>''')
