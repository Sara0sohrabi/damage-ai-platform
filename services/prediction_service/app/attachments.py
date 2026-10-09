"""Local claim documents, kept outside publicly served frontend assets."""
import json
import os
from pathlib import Path
from uuid import UUID, uuid4
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import text
from .db import engine
from .image_analysis import analyze

router = APIRouter(prefix='/api/v1/claim/predictions', tags=['Documents'])
ROOT = Path(os.getenv('CLAIM_DOCUMENT_DIR', str(Path(__file__).resolve().parents[3] / 'var' / 'claim_documents')))
LIMIT = 10 * 1024 * 1024
EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.pdf', '.docx', '.xlsx', '.txt'}


def folder(request_id):
    with engine.connect() as conn:
        if not conn.scalar(text('SELECT 1 FROM prediction_requests WHERE request_id=:id'), {'id':str(request_id)}):
            raise HTTPException(404, 'پرونده پیدا نشد')
    return ROOT / str(request_id)


@router.post('/{request_id}/documents', summary='بارگذاری یک مدرک؛ بدنه باینری، حداکثر ۱۰ مگابایت')
async def upload(request_id: UUID, request: Request, filename: str = Query(..., min_length=1, max_length=200), item_id: str | None = Query(None, pattern=r'^[a-zA-Z0-9-]{1,64}$')):
    directory = folder(request_id)
    if item_id:
        with engine.connect() as conn:
            payload = conn.scalar(text('SELECT request_payload FROM prediction_requests WHERE request_id=:id'), {'id':str(request_id)})
        if not any(item.get('item_id') == item_id for item in payload.get('damaged_items', [])):
            raise HTTPException(422, 'قلم در این پرونده ثبت نشده است')
    name = Path(filename.replace('\\', '/')).name
    if Path(name).suffix.lower() not in EXTENSIONS:
        raise HTTPException(422, 'نوع فایل مجاز نیست')
    directory.mkdir(parents=True, exist_ok=True)
    identifier = str(uuid4())
    target = directory / (identifier + '.bin')
    size = 0
    try:
        with target.open('xb') as stream:
            async for chunk in request.stream():
                size += len(chunk)
                if size > LIMIT:
                    raise HTTPException(413, 'حداکثر حجم هر فایل ۱۰ مگابایت است')
                stream.write(chunk)
        if size == 0:
            raise HTTPException(422, 'فایل خالی است')
        metadata = {'id':identifier, 'filename':name, 'size':size, 'item_id':item_id}
        (directory / (identifier + '.json')).write_text(json.dumps(metadata, ensure_ascii=False))
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return metadata


@router.get('/{request_id}/documents', summary='فهرست مدارک پرونده')
def documents(request_id: UUID):
    directory = folder(request_id)
    return {'items':[json.loads(p.read_text()) for p in sorted(directory.glob('*.json'))]}


@router.get('/{request_id}/documents/{document_id}', summary='دریافت مدرک پرونده')
def download(request_id: UUID, document_id: UUID):
    directory = folder(request_id)
    metadata = directory / (str(document_id) + '.json')
    target = directory / (str(document_id) + '.bin')
    if not metadata.exists() or not target.exists():
        raise HTTPException(404, 'مدرک پیدا نشد')
    name = json.loads(metadata.read_text())['filename']
    return FileResponse(target, filename=name, media_type='application/octet-stream', headers={'X-Content-Type-Options':'nosniff'})

@router.post('/{request_id}/documents/{document_id}/analyze', summary='غربال‌گری محلی تصویر خسارت')
def analyze_document(request_id: UUID, document_id: UUID):
    directory = folder(request_id)
    target = directory / (str(document_id) + '.bin')
    if not target.exists():
        raise HTTPException(404, 'مدرک پیدا نشد')
    return {'document_id': str(document_id), 'analysis_version': 'local-triage-001', **analyze(target)}
