"""Private document OCR and reviewed vehicle identity records.

Requires VEHICLE_DOCUMENT_API_KEY; no public document access is enabled by default.
OCR is advisory, never an identity verification or vehicle make/model classifier.
"""
from __future__ import annotations
import io
import json
import os
import re
import secrets
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field
from sqlalchemy import text
from .persistence import engine

router = APIRouter(prefix="/api/v1/claims", tags=["vehicle-documents"])
KINDS = {"national_card", "driver_license", "vehicle_card", "vehicle_front", "vehicle_rear", "vehicle_left", "vehicle_right"}
DOC_ROOT = Path(os.getenv("VEHICLE_DOCUMENT_STORAGE_ROOT", "data/private_vehicle_documents"))
MAX_BYTES = 10 * 1024 * 1024
SCHEMA = """CREATE TABLE IF NOT EXISTS vehicle_identity_documents (
 document_id VARCHAR(36) PRIMARY KEY, claim_id VARCHAR(160) NOT NULL,
 kind VARCHAR(40) NOT NULL, storage_key TEXT NOT NULL,
 original_filename TEXT, sha256 VARCHAR(64) NOT NULL,
 ocr_text TEXT, extracted_json TEXT NOT NULL, confirmed_json TEXT,
 review_status VARCHAR(30) NOT NULL DEFAULT 'pending_review',
 created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"""

def require_key(x_document_api_key: str | None = Header(default=None)):
    expected = os.getenv("VEHICLE_DOCUMENT_API_KEY")
    if not expected or not x_document_api_key or not secrets.compare_digest(x_document_api_key, expected):
        raise HTTPException(status_code=403, detail="Document API is disabled or access denied")

def initialize():
    with engine.begin() as conn:
        conn.execute(text(SCHEMA))

def extract_fields(kind: str, raw: str) -> dict:
    # OCR output is untrusted. Only pattern-based suggestions are returned.
    normalized = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    result = {}
    if kind == "national_card":
        for candidate in re.findall(r"(?<!\d)\d{10}(?!\d)", normalized):
            if _national_id_checksum(candidate):
                result["national_id_candidate"] = candidate
                break
    if kind == "vehicle_card":
        vin = re.search(r"(?<![A-Z0-9])[A-HJ-NPR-Z0-9]{17}(?![A-Z0-9])", normalized.upper())
        if vin: result["vin_candidate"] = vin.group(0)
        year = re.search(r"(?<!\d)(13\d{2}|14\d{2}|19\d{2}|20\d{2})(?!\d)", normalized)
        if year: result["year_candidate"] = int(year.group(0))
    return result

def _national_id_checksum(value: str) -> bool:
    if len(value) != 10 or len(set(value)) == 1: return False
    rem = sum(int(value[i]) * (10 - i) for i in range(9)) % 11
    return int(value[9]) == (rem if rem < 2 else 11 - rem)

def run_ocr(image: Image.Image) -> tuple[str, str]:
    try:
        import pytesseract
        text_value = pytesseract.image_to_string(image, lang=os.getenv("VEHICLE_OCR_LANG", "fas+eng"))
        return text_value, "tesseract"
    except (ImportError, Exception) as exc:
        # Missing binary/language pack must be explicit, not silently treated as empty OCR.
        return "", "unavailable: " + type(exc).__name__

@router.post("/{claim_id}/documents", dependencies=[Depends(require_key)], status_code=201)
async def upload_document(claim_id: str, kind: str = Form(...), file: UploadFile = File(...)):
    if kind not in KINDS:
        raise HTTPException(422, detail="Invalid document kind")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, detail="Only JPEG, PNG and WEBP are accepted")
    data = await file.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES: raise HTTPException(413, detail="Invalid image size")
    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
        image = Image.open(io.BytesIO(data)).convert("RGB")
        if image.width * image.height > 30_000_000: raise ValueError("Too many pixels")
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(400, detail="Invalid image")
    from .workflow import get_claim_record
    if not get_claim_record(claim_id):
        raise HTTPException(404, detail="Claim not found")
    import hashlib
    initialize()
    document_id = str(uuid4())
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[file.content_type]
    destination = DOC_ROOT / document_id[:2] / (document_id + ext)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw, provider = run_ocr(image) if kind in {"national_card", "driver_license", "vehicle_card"} else ("", "not_applicable")
    fields = extract_fields(kind, raw)
    destination.write_bytes(data)
    destination.chmod(0o600)
    try:
        with engine.begin() as conn:
            conn.execute(text("""INSERT INTO vehicle_identity_documents
            (document_id, claim_id, kind, storage_key, original_filename, sha256, ocr_text, extracted_json)
            VALUES (:id,:claim,:kind,:path,:filename,:sha,:raw,:fields)"""),
            {"id":document_id,"claim":claim_id,"kind":kind,"path":str(destination),
             "filename":file.filename,"sha":hashlib.sha256(data).hexdigest(),
             "raw":raw,"fields":json.dumps(fields,ensure_ascii=False)})
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return {"document_id":document_id,"kind":kind,"ocr_provider":provider,
            "extracted_fields":fields,"review_status":"pending_review",
            "identity_verified":False,"vehicle_model_verified":False}

class DocumentReview(BaseModel):
    confirmed_fields: dict[str, str | int | None] = Field(default_factory=dict)
    approved: bool = False

@router.post("/{claim_id}/documents/{document_id}/review", dependencies=[Depends(require_key)])
def review_document(claim_id: str, document_id: str, review: DocumentReview):
    initialize()
    if len(json.dumps(review.confirmed_fields,ensure_ascii=False)) > 8000:
        raise HTTPException(422, detail="Review data too large")
    with engine.begin() as conn:
        result = conn.execute(text("""UPDATE vehicle_identity_documents SET
        confirmed_json=:fields, review_status=:status
        WHERE claim_id=:claim AND document_id=:id"""),
        {"fields":json.dumps(review.confirmed_fields,ensure_ascii=False),
         "status":"reviewed" if review.approved else "needs_correction",
         "claim":claim_id,"id":document_id})
        if not result.rowcount: raise HTTPException(404, detail="Document not found")
    return {"document_id":document_id,"review_status":"reviewed" if review.approved else "needs_correction",
            "identity_verified":False,"vehicle_model_verified":False}

@router.get("/{claim_id}/documents", dependencies=[Depends(require_key)])
def list_documents(claim_id: str):
    initialize()
    with engine.connect() as conn:
        rows = conn.execute(text("""SELECT document_id,kind,extracted_json,confirmed_json,review_status,created_at
        FROM vehicle_identity_documents WHERE claim_id=:claim ORDER BY created_at DESC"""),
        {"claim":claim_id}).mappings().all()
    return {"items":[{"document_id":r["document_id"],"kind":r["kind"],
                      "extracted_fields":json.loads(r["extracted_json"]),
                      "confirmed_fields":json.loads(r["confirmed_json"]) if r["confirmed_json"] else None,
                      "review_status":r["review_status"]} for r in rows]}

# Minimal document intake page. API key is kept only in page memory (not persisted).
from fastapi.responses import HTMLResponse

@router.get("/documents/intake", response_class=HTMLResponse, include_in_schema=False)
def intake_page():
    return HTMLResponse("""<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8">
<title>مدارک پرونده خسارت خودرو</title><style>
body{font:15px Tahoma,sans-serif;background:#f5f6f8;color:#20242a;max-width:750px;margin:35px auto;padding:16px}
section{background:white;padding:22px;border-radius:12px;border:1px solid #ddd}
label{display:block;margin-top:16px}input,select,textarea{width:100%;padding:10px;box-sizing:border-box;margin-top:6px}
button{padding:12px 22px;background:#222;color:white;border:0;border-radius:8px;margin-top:16px;cursor:pointer}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eee;padding:12px}
</style><section><h2>ثبت تصویر مدارک و خودرو</h2>
<p>پس از ثبت پرونده، شناسه آن را وارد کنید. OCR نیازمند بررسی و تأیید انسانی است.</p>
<label>شناسه پرونده<input id="claim" required></label>
<label>کلید دسترسی مدارک<input id="key" type="password" autocomplete="off" required></label>
<label>نوع تصویر<select id="kind"><option value="national_card">کارت ملی</option>
<option value="driver_license">گواهینامه</option><option value="vehicle_card">کارت خودرو</option>
<option value="vehicle_front">نمای جلو خودرو</option><option value="vehicle_rear">نمای عقب خودرو</option>
<option value="vehicle_left">نمای چپ خودرو</option><option value="vehicle_right">نمای راست خودرو</option></select></label>
<label>عکس<input id="file" type="file" accept="image/jpeg,image/png,image/webp"></label>
<button onclick="upload()">بارگذاری و استخراج</button><p id="status"></p>
<label>اطلاعات پیشنهادی OCR (قابل اصلاح)<textarea id="fields" rows="7">{}</textarea></label>
<button onclick="review()">ثبت اطلاعات تأییدشده</button><pre id="result"></pre></section>
<script>
let current=null;
const el=id=>document.getElementById(id);
async function upload(){
  const claim=el('claim').value.trim(), file=el('file').files[0];
  if(!claim||!file){el('status').textContent='شناسه پرونده و عکس الزامی است';return}
  let form=new FormData();form.append('kind',el('kind').value);form.append('file',file);
  try{
    const r=await fetch('/api/v1/claims/'+encodeURIComponent(claim)+'/documents',
      {method:'POST',headers:{'X-Document-Api-Key':el('key').value},body:form});
    const j=await r.json();if(!r.ok)throw Error(JSON.stringify(j.detail));
    current=j.document_id;el('fields').value=JSON.stringify(j.extracted_fields,null,2);
    el('status').textContent='تصویر ثبت شد؛ اطلاعات را بررسی و سپس تأیید کنید. OCR: '+j.ocr_provider;
    el('result').textContent=JSON.stringify(j,null,2);
  }catch(e){el('status').textContent=e.message}
}
async function review(){
 if(!current){el('status').textContent='ابتدا عکس را بارگذاری کنید';return}
 try{
  const fields=JSON.parse(el('fields').value);
  const r=await fetch('/api/v1/claims/'+encodeURIComponent(el('claim').value.trim())+
    '/documents/'+encodeURIComponent(current)+'/review',
    {method:'POST',headers:{'Content-Type':'application/json','X-Document-Api-Key':el('key').value},
     body:JSON.stringify({confirmed_fields:fields,approved:true})});
  const j=await r.json();if(!r.ok)throw Error(JSON.stringify(j.detail));
  el('status').textContent='اطلاعات بررسی‌شده در دیتابیس ذخیره شد';
  el('result').textContent=JSON.stringify(j,null,2);
 }catch(e){el('status').textContent=e.message}
}
</script></html>""")
