"""Inference adapter for the separately trained Iranian vehicle repair-cost model."""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

MODEL_PATH = Path(os.getenv("VEHICLE_REPAIR_COST_MODEL", "models/vehicle_vision/vehicle_repair_cost.joblib"))


class CostModelNotConfigured(RuntimeError):
    pass


def predict_repair_cost(features: dict[str, Any]) -> dict[str, Any]:
    if not MODEL_PATH.is_file():
        raise CostModelNotConfigured(f"Repair-cost model not found at {MODEL_PATH}")
    artifact = joblib.load(MODEL_PATH)
    pipeline = artifact["pipeline"]
    frame = pd.DataFrame([{name: features.get(name) for name in artifact["features"]}])
    log_prediction = float(pipeline.predict(frame)[0])
    amount = max(0, round(float(math.expm1(log_prediction))))
    return {
        "estimated_cost_irr": amount,
        "model_version": artifact.get("model_version", "unknown"),
        "metrics": artifact.get("metrics", {}),
    }
