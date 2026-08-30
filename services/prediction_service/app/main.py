from pathlib import Path
from uuid import uuid4
import os
import joblib
import pandas as pd

from fastapi import FastAPI

from .schemas import ClaimPredictionRequest
from .db import (
    save_prediction,
    save_rejected_request,
    finalize_prediction,
)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Damage AI Prediction Service",
    version="3.0.1",
    description=(
        "Operational fire/home damage assessment API. "
        "Historical cleaning and model training are separated "
        "from operational prediction."
    ),
)


# ============================================================
# MODEL
# ============================================================

MODEL_DIR = Path(
    os.getenv("MODEL_DIR", "/models")
)

MODEL_FILENAME = os.getenv(
    "MODEL_FILENAME",
    "damagefire_001_gradient_boosting_raw_v2.joblib",
)

MODEL_PATH = MODEL_DIR / MODEL_FILENAME


model = None


try:

    if MODEL_PATH.exists():

        model = joblib.load(MODEL_PATH)

        print("=" * 70)
        print("MODEL LOADED")
        print("=" * 70)
        print(f"Model path    : {MODEL_PATH}")
        print(f"Model type    : {type(model)}")
        print("=" * 70)

    else:

        print("=" * 70)
        print("MODEL NOT FOUND")
        print("=" * 70)
        print(f"Expected path: {MODEL_PATH}")
        print("=" * 70)

except Exception as exc:

    print("=" * 70)
    print("MODEL LOAD ERROR")
    print("=" * 70)
    print(str(exc))
    print("=" * 70)

    model = None


# ============================================================
# MODEL METADATA
# ============================================================

MODEL_VERSION = (
    "damagefire_001_gradient_boosting_raw_v2"
)

MODEL_NAME = "GradientBoostingRegressor"


# ============================================================
# IMPORTANT
#
# مدل فعلی واقعاً با این 21 feature کار می‌کند.
#
# estimate_amount:
# در مدل فعلی Feature است.
#
# paid_loss:
# هرگز وارد Prediction نمی‌شود.
#
# ============================================================

MODEL_FEATURES = [

    "province_code",
    "city_code",
    "coverage_code",

    "insurance_type_code",

    "event_type_code",
    "insured_item_type_code",
    "damaged_item_code",

    "damage_type_code",
    "financial_damage_type_code",

    "structure_type_code",
    "risk_density_code",
    "ownership_type_code",
    "property_type_code",
    "loss_location_code",

    "occupation_code",
    "occupation_group_code",

    "premium",
    "item_sum_insured",
    "total_sum_insured",

    "estimate_amount",
]


# ============================================================
# MODEL METRICS
# ============================================================

MODEL_METRICS = {

    "mae": 428347790,

    "rmse": 2778282938,

    "r2": 0.2816,

    "within_10pct": 0.1917,

    "within_20pct": 0.3010,
}


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {

        "status": "ok",

        "model_loaded": (
            model is not None
        ),

        "model_version": (
            MODEL_VERSION
            if model is not None
            else None
        ),

        "model_name": (
            MODEL_NAME
            if model is not None
            else None
        ),
    }


# ============================================================
# PREDICT CLAIM
# ============================================================

@app.post("/api/v1/claim/predict")
def predict(
    req: ClaimPredictionRequest
):

    request_id = uuid4()

    # ========================================================
    # MODEL CHECK
    # ========================================================

    if model is None:

        return {

            "success": False,

            "request_id": str(
                request_id
            ),

            "error": "MODEL_NOT_FOUND",

            "message": (
                f"Model not found: "
                f"{MODEL_PATH}"
            ),
        }

    # ========================================================
    # REQUEST DATA
    # ========================================================

    data = req.model_dump()

    # ========================================================
    # REQUIRED FEATURES
    # ========================================================

    missing = [

        feature

        for feature in MODEL_FEATURES

        if data.get(feature) is None
    ]

    if missing:

        save_rejected_request(

            request_id,

            data,

            "INCOMPLETE_DATA",
        )

        score = (

            (
                len(MODEL_FEATURES)
                - len(missing)
            )
            / len(MODEL_FEATURES)
        )

        return {

            "success": False,

            "request_id": str(
                request_id
            ),

            "data_quality": {

                "status": "insufficient",

                "missing_features": missing,

                "score": round(
                    score,
                    4
                ),
            },

            "error": "INCOMPLETE_DATA",

            "message": (
                "Required prediction "
                "features are missing."
            ),
        }

    # ========================================================
    # POLICY VALIDATION
    # ========================================================

    item_sum_insured = float(
        data["item_sum_insured"]
    )

    total_sum_insured = float(
        data["total_sum_insured"]
    )

    if item_sum_insured <= 0:

        save_rejected_request(

            request_id,

            data,

            "INVALID_POLICY_LIMIT",
        )

        return {

            "success": False,

            "request_id": str(
                request_id
            ),

            "error": (
                "INVALID_POLICY_LIMIT"
            ),

            "message": (
                "item_sum_insured "
                "must be greater than zero."
            ),
        }

    if total_sum_insured <= 0:

        save_rejected_request(

            request_id,

            data,

            "INVALID_POLICY_LIMIT",
        )

        return {

            "success": False,

            "request_id": str(
                request_id
            ),

            "error": (
                "INVALID_POLICY_LIMIT"
            ),

            "message": (
                "total_sum_insured "
                "must be greater than zero."
            ),
        }

    if item_sum_insured > total_sum_insured:

        save_rejected_request(

            request_id,

            data,

            "INVALID_POLICY_LIMIT",
        )

        return {

            "success": False,

            "request_id": str(
                request_id
            ),

            "error": (
                "INVALID_POLICY_LIMIT"
            ),

            "message": (
                "item_sum_insured "
                "cannot be greater than "
                "total_sum_insured."
            ),
        }

    # ========================================================
    # BUILD MODEL INPUT
    # ========================================================

    X = pd.DataFrame(
        [
            {
                feature: data[feature]

                for feature in MODEL_FEATURES
            }
        ]
    )

    # ========================================================
    # ENSURE FEATURE ORDER
    # ========================================================

    X = X[
        MODEL_FEATURES
    ]

    # ========================================================
    # PREDICTION
    # ========================================================

    try:

        raw_prediction = float(
            model.predict(X)[0]
        )

    except Exception as exc:

        return {

            "success": False,

            "request_id": str(
                request_id
            ),

            "error": (
                "MODEL_PREDICTION_ERROR"
            ),

            "message": str(exc),
        }

    # ========================================================
    # POLICY CEILING
    # ========================================================

    maximum_payable_loss = min(

        item_sum_insured,

        total_sum_insured,
    )

    # ========================================================
    # FINAL PREDICTION
    #
    # Prediction cannot exceed policy ceiling.
    # ========================================================

    predicted_loss = max(

        0.0,

        min(

            raw_prediction,

            maximum_payable_loss,
        ),
    )

    # ========================================================
    # SAVE PREDICTION
    # ========================================================

    save_prediction(
    request_id=request_id,
    payload=data,
    predicted_loss=predicted_loss,
    maximum_payable_loss=maximum_payable_loss,
    cluster=None,
    category=None,
    model_version=MODEL_VERSION,
    model_metrics=MODEL_METRICS,
)
    # ========================================================
    # RESPONSE
    # ========================================================

    return {

        "success": True,

        "request_id": str(
            request_id
        ),

        # ----------------------------------------------------
        # PREDICTION
        # ----------------------------------------------------

        "prediction": {

            "raw_prediction": (
                raw_prediction
            ),

            "predicted_loss": (
                predicted_loss
            ),

            "currency": "IRR",
        },

        # ----------------------------------------------------
        # POLICY
        # ----------------------------------------------------

        "policy_limits": {

            "item_sum_insured": (
                item_sum_insured
            ),

            "total_sum_insured": (
                total_sum_insured
            ),

            "maximum_payable_loss": (
                maximum_payable_loss
            ),
        },

        # ----------------------------------------------------
        # ESTIMATE
        #
        # EstimateAmount در این مدل Feature است
        # و همچنین در Response نگهداری می‌شود.
        # ----------------------------------------------------

        "estimate_amount": data.get(
            "estimate_amount"
        ),

        # ----------------------------------------------------
        # MODEL
        # ----------------------------------------------------

        "model": {

            "name": MODEL_NAME,

            "version": MODEL_VERSION,

            "metrics": MODEL_METRICS,
        },

        # ----------------------------------------------------
        # DATA QUALITY
        # ----------------------------------------------------

        "data_quality": {

            "status": "good",

            "missing_features": [],

            "score": 1.0,
        },
    }


# ============================================================
# FINALIZE CLAIM
# ============================================================

@app.post(
    "/api/v1/claim/{request_id}/finalize"
)
def finalize(

    request_id: str,

    actual_paid_loss: float,
):

    # ========================================================
    # VALIDATE ACTUAL LOSS
    # ========================================================

    if actual_paid_loss < 0:

        return {

            "success": False,

            "request_id": request_id,

            "error": (
                "INVALID_PAID_LOSS"
            ),
        }

    # ========================================================
    # FINALIZE IN DATABASE
    # ========================================================

    try:

        ok = finalize_prediction(

            request_id,

            actual_paid_loss,
        )

    except ValueError as exc:

        return {

            "success": False,

            "request_id": request_id,

            "error": (
                "INVALID_POLICY_LIMIT"
            ),

            "message": str(exc),
        }

    # ========================================================
    # NOT FOUND
    # ========================================================

    if not ok:

        return {

            "success": False,

            "request_id": request_id,

            "error": (
                "REQUEST_NOT_FOUND"
            ),
        }

    # ========================================================
    # SUCCESS
    # ========================================================

    return {

        "success": True,

        "request_id": request_id,

        "actual_paid_loss": (
            actual_paid_loss
        ),

        "message": (
            "Prediction finalized. "
            "Predicted loss, EstimateAmount "
            "and actual paid loss are now "
            "available for comparison."
        ),
    }


# ============================================================
# MODEL METRICS
# ============================================================

@app.get(
    "/api/v1/model/metrics"
)
def metrics():

    if model is None:

        return {

            "error": (
                "MODEL_NOT_FOUND"
            )
        }

    return {

        "model_name": MODEL_NAME,

        "model_version": MODEL_VERSION,

        "metrics": MODEL_METRICS,

        "features": MODEL_FEATURES,
    }