from pathlib import Path
from uuid import UUID, uuid4
from contextlib import asynccontextmanager
import os
import logging
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from .schemas import ClaimPredictionRequest, ActualPaymentRequest
from . import db
from .model_loader import load_model

logger = logging.getLogger(__name__)
MODEL = Path(os.getenv('MODEL_DIR', str(Path(__file__).resolve().parents[3] / 'models'))) / os.getenv('MODEL_FILENAME', 'damagefire_001_gradient_boosting_raw_v2.joblib')
artifact = None
model_error = None
REQUIRED = ['item_sum_insured', 'total_sum_insured']


@asynccontextmanager
async def lifespan(app):
    global artifact, model_error
    try:
        artifact = load_model(MODEL)
    except Exception:
        model_error = 'MODEL_LOAD_FAILED'
        logger.exception('Could not load prediction artifact')
    try:
        # The prediction database is provisioned separately. Never mutate its schema
        # during service startup; this keeps deployment read-only with respect to DDL.
        db.init_prediction_schema()
    except SQLAlchemyError:
        logger.exception('Prediction database initialization failed')
    yield


app = FastAPI(title='Damage Prediction Service', version='2.1.0', lifespan=lifespan)


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    logger.error('Database operation failed', exc_info=exc)
    return JSONResponse(status_code=503, content={'detail': 'DATABASE_UNAVAILABLE'})


@app.get('/health')
def health():
    return {'status': 'ok' if artifact else 'degraded', 'model_loaded': artifact is not None,
            'model_version': (artifact.get('model_version') if isinstance(artifact, dict)
                              else os.getenv('MODEL_VERSION', MODEL.stem)) if artifact is not None else None}


@app.get('/api/v1/claim/metadata')
def metadata():
    if artifact is None:
        raise HTTPException(503, 'MODEL_NOT_FOUND')
    model = artifact['model'] if isinstance(artifact, dict) else artifact
    features = artifact.get('features') if isinstance(artifact, dict) else list(getattr(model, 'feature_names_in_', []))
    if not features:
        features = ['province_code','city_code','coverage_code','insurance_type_code','event_type_code',
                    'insured_item_type_code','damage_type_code','financial_damage_type_code','structure_type_code',
                    'risk_density_code','ownership_type_code','property_type_code','loss_location_code',
                    'occupation_code','occupation_group_code','premium','item_sum_insured','total_sum_insured','estimate_amount']
    pre = model.named_steps.get('preprocessor') if hasattr(model, 'named_steps') else None
    # Offer actual training codes even when no human-readable mapping is available.
    options = {}
    for name, transformer, columns in (pre.transformers_ if pre is not None else []):
        if hasattr(transformer, 'named_steps') and 'onehot' in transformer.named_steps:
            for col, codes in zip(columns, transformer.named_steps['onehot'].categories_):
                options[col] = [{'code': str(c), 'title': str(c)} for c in codes if pd.notna(c)]
    mapping_available = True
    try:
        labels = db.mappings()
        # This lookup is copied from damaged_item_mapping and is independent
        # of the model's insured_item_type_code feature.
        for key, choices in options.items():
            titles = {x['code']: x['title'] for x in labels.get(key, [])}
            for choice in choices:
                choice['title'] = titles.get(choice['code'], choice['code'])
        options['damaged_item_code'] = labels.get('insured_item_code', [])
        options['ownership_type_code'] = [o for o in labels.get('ownership_type_code', []) if o['code'] not in ('0', '1')]
    except SQLAlchemyError:
        mapping_available = False
    for key in ('province_code', 'city_code'):
        if key in options and all(item['title'] == item['code'] for item in options[key]):
            options[key] = []
            mapping_available = False
    version = artifact.get('model_version', os.getenv('MODEL_VERSION', 'damagefire_001_gradient_boosting_raw_v2')) if isinstance(artifact, dict) else os.getenv('MODEL_VERSION', 'damagefire_001_gradient_boosting_raw_v2')
    metrics = artifact.get('metrics', {}) if isinstance(artifact, dict) else {'mae': 428347790, 'rmse': 2778282938, 'r2': 0.2816, 'within_10pct': 0.1917, 'within_20pct': 0.301}
    city_province = {x['code']: x['title'] for x in labels.get('city_province_code', [])} if 'labels' in locals() else {}
    return {'features': features, 'required_features': REQUIRED, 'options': options,
            'city_province': city_province,
            'mapping_available': mapping_available,
            'model': {'version': version, 'metrics': metrics},
            'currency': 'IRR'}


@app.post('/api/v1/claim/predict')
def predict(req: ClaimPredictionRequest):
    rid = uuid4()
    if artifact is None:
        return {'success': False, 'request_id': str(rid), 'error': 'MODEL_NOT_FOUND'}
    data = req.model_dump()
    data['claim_registered_at'] = datetime.now(timezone.utc).isoformat()
    model = artifact['model'] if isinstance(artifact, dict) else artifact
    features = artifact.get('features') if isinstance(artifact, dict) else list(getattr(model, 'feature_names_in_', []))
    if not features:
        features = list(req.model_fields.keys())
    version = artifact.get('model_version', os.getenv('MODEL_VERSION', 'damagefire_001_gradient_boosting_raw_v2')) if isinstance(artifact, dict) else os.getenv('MODEL_VERSION', 'damagefire_001_gradient_boosting_raw_v2')
    metrics = artifact.get('metrics', {}) if isinstance(artifact, dict) else {'mae': 428347790, 'rmse': 2778282938, 'r2': 0.2816, 'within_10pct': 0.1917, 'within_20pct': 0.301}
    model_data = data.copy()
    unmapped = []
    if data.get('ownership_type_code') in ('2', '3'):
        model_data['ownership_type_code'] = None
        unmapped.append('ownership_type_code')
    missing = [f for f in features if model_data.get(f) is None]
    required_missing = [f for f in REQUIRED if data.get(f) is None]
    quality = {'status': 'insufficient' if required_missing else ('partial' if missing else 'complete'),
               'missing_features': missing, 'required_missing': required_missing,
               'score': round((len(features) - len(missing)) / len(features), 4),
               'imputed_features': [] if required_missing else missing,
               'unmapped_features': unmapped}
    if required_missing:
        return {'success': False, 'request_id': str(rid), 'data_quality': quality, 'error': 'INCOMPLETE_DATA'}
    # Use the fitted training imputers; never treat an empty amount as zero.
    X = pd.DataFrame([{f: model_data.get(f) if model_data.get(f) is not None else np.nan for f in features}])
    try:
        raw = float(model.predict(X)[0])
        if not np.isfinite(raw):
            raise ValueError('Non-finite prediction')
        ceiling = min(data['item_sum_insured'], data['total_sum_insured'])
        predicted = max(0.0, min(raw, ceiling))
        cluster, category = None, 'prediction_model'
        if isinstance(artifact, dict) and artifact.get('kmeans') is not None:
            transformed = model.named_steps['preprocessor'].transform(X)
            cluster = int(artifact['kmeans'].predict(transformed)[0])
            category = artifact['cluster_labels'][cluster]
    except Exception:
        logger.exception('Prediction failed')
        raise HTTPException(503, 'PREDICTION_FAILED')
    db.save_prediction(rid, data, predicted, cluster, category, version, quality, metrics)
    return {'success': True, 'request_id': str(rid), 'data_quality': quality,
            'classification': {'cluster_id': cluster, 'category': category},
            'prediction': {'predicted_loss': predicted, 'currency': 'IRR'},
            'policy_limits': {'item_sum_insured': data['item_sum_insured'],
                              'total_sum_insured': data['total_sum_insured'], 'maximum_payable_loss': ceiling},
            'estimate_amount': data['estimate_amount'],
            'model': {'version': version, 'metrics': metrics}}


@app.get('/api/v1/claim/predictions')
def predictions(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return db.history(limit, offset)


@app.put('/api/v1/claim/predictions/{request_id}/actual')
def actual(request_id: UUID, req: ActualPaymentRequest):
    if not db.save_actual(request_id, req.actual_paid_loss):
        raise HTTPException(404, 'PREDICTION_NOT_FOUND')
    return {'success': True, 'request_id': str(request_id), 'actual_paid_loss': req.actual_paid_loss}


@app.get('/api/v1/claim/reports/bi', tags=['Reports'], summary='گزارش تجمیعی پرونده‌های ذخیره‌شده')
def bi_report():
    return db.bi_report()

from .attachments import router as documents_router
app.include_router(documents_router)
from .annotations import router as annotations_router
app.include_router(annotations_router)
