"""Local, human-reviewed polygon annotations; predictions are never labels by default."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4
from threading import Lock
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field, ConfigDict
from .attachments import folder

router = APIRouter(prefix='/api/v1/claim/predictions', tags=['Image annotations'])
lock = Lock()
model = None

class Point(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)

class Region(BaseModel):
    label: Literal['burn', 'soot', 'breakage', 'deformation', 'other']
    points: list[Point] = Field(min_length=3, max_length=2000)

class Annotation(BaseModel):
    regions: list[Region] = Field(min_length=1, max_length=100)
    reviewed: Literal[True]

class Box(BaseModel):
    start: Point
    end: Point

def read_image(request_id, document_id):
    import cv2
    directory = folder(request_id)
    image = cv2.imread(str(directory / (str(document_id) + '.bin')))
    if image is None:
        raise HTTPException(422, 'مدرک باید تصویر قابل خواندن باشد')
    if image.shape[0] * image.shape[1] > 25000000:
        raise HTTPException(413, 'ابعاد تصویر بیش از حد بزرگ است')
    return directory, image

@router.get('/{request_id}/documents/{document_id}/preview')
def preview(request_id: UUID, document_id: UUID):
    import cv2
    _, image = read_image(request_id, document_id)
    ok, encoded = cv2.imencode('.jpg', image)
    if not ok:
        raise HTTPException(422, 'تبدیل تصویر ناموفق بود')
    return Response(encoded.tobytes(), media_type='image/jpeg')

@router.post('/{request_id}/documents/{document_id}/segment')
def segment(request_id: UUID, document_id: UUID, box: Box):
    global model
    _, image = read_image(request_id, document_id)
    weights = Path(os.getenv('SAM_MODEL_PATH', 'models/sam2.1_t.pt'))
    if not weights.is_file():
        raise HTTPException(503, 'وزن مدل SAM محلی هنوز آماده نیست؛ علامت‌گذاری دستی در دسترس است')
    h, w = image.shape[:2]
    x1,x2 = sorted([box.start.x*w,box.end.x*w]); y1,y2 = sorted([box.start.y*h,box.end.y*h])
    if x2-x1 < 3 or y2-y1 < 3:
        raise HTTPException(422, 'کادر انتخاب‌شده بسیار کوچک است')
    with lock:
        from ultralytics import SAM
        if model is None:
            model = SAM(str(weights))
        result = model(image, bboxes=[x1,y1,x2,y2], device='cpu', verbose=False)[0]
        polygons = [] if result.masks is None else [p.tolist() for p in result.masks.xyn]
    return {'polygons':polygons, 'reviewed':False, 'model':weights.name}

@router.post('/{request_id}/documents/{document_id}/annotations')
def save(request_id: UUID, document_id: UUID, annotation: Annotation):
    directory, image = read_image(request_id, document_id)
    metadata = json.loads((directory / (str(document_id)+'.json')).read_text())
    version = str(uuid4())
    record = {**annotation.model_dump(), 'version':version, 'request_id':str(request_id),
              'document_id':str(document_id), 'item_id':metadata.get('item_id'),
              'created_at':datetime.now(timezone.utc).isoformat(),
              'width':image.shape[1], 'height':image.shape[0], 'coordinate_system':'normalized_xy'}
    destination = directory / 'annotations' / str(document_id)
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / (version+'.json')).open('x') as stream:
        json.dump(record, stream, ensure_ascii=False)
    return record
