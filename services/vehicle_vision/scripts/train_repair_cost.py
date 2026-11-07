"""Train a claim-grouped repair-cost baseline from expert-approved Iranian invoices.

Input CSV columns:
claim_id, make, model, year, city, part, damage_type, severity,
affected_area_pct, labor_hours, total_cost_irr
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

CATEGORICAL = ["make", "model", "city", "part", "damage_type", "severity"]
NUMERIC = ["year", "affected_area_pct", "labor_hours"]
FEATURES = CATEGORICAL + NUMERIC
REQUIRED = ["claim_id", *FEATURES, "total_cost_irr"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="CSV of expert-approved repair invoices")
    parser.add_argument("--output", default="models/vehicle_repair_cost.joblib")
    parser.add_argument("--test-size", type=float, default=0.2)
    args = parser.parse_args()

    data = pd.read_csv(args.input)
    missing = sorted(set(REQUIRED) - set(data.columns))
    if missing:
        raise SystemExit(f"Missing required columns: {missing}")
    data = data[REQUIRED].replace([np.inf, -np.inf], np.nan).dropna()
    data = data[data["total_cost_irr"] > 0]
    if data["claim_id"].nunique() < 10 or len(data) < 30:
        raise SystemExit("Need at least 30 valid rows from 10 distinct claims before training.")

    splitter = GroupShuffleSplit(n_splits=1, test_size=args.test_size, random_state=42)
    train_idx, test_idx = next(splitter.split(data[FEATURES], data["total_cost_irr"], groups=data["claim_id"]))
    x_train, x_test = data.iloc[train_idx][FEATURES], data.iloc[test_idx][FEATURES]
    y_train = np.log1p(data.iloc[train_idx]["total_cost_irr"].astype(float))
    y_test = data.iloc[test_idx]["total_cost_irr"].astype(float)

    preprocessing = ColumnTransformer([
        ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
        ("numeric", "passthrough", NUMERIC),
    ])
    pipeline = Pipeline([
        ("preprocess", preprocessing),
        ("regressor", HistGradientBoostingRegressor(max_iter=250, learning_rate=0.06, l2_regularization=1.0, random_state=42)),
    ])
    pipeline.fit(x_train, y_train)
    predictions = np.maximum(0, np.expm1(pipeline.predict(x_test)))
    metrics = {
        "mae_irr": float(mean_absolute_error(y_test, predictions)),
        "rmse_irr": float(mean_squared_error(y_test, predictions) ** 0.5),
        "r2": float(r2_score(y_test, predictions)),
        "train_rows": int(len(train_idx)),
        "test_rows": int(len(test_idx)),
        "test_claims": int(data.iloc[test_idx]["claim_id"].nunique()),
    }
    version = datetime.now(timezone.utc).strftime("vehicle-cost-%Y%m%dT%H%M%SZ")
    artifact = {"pipeline": pipeline, "features": FEATURES, "metrics": metrics, "model_version": version}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output)
    print(json.dumps({"model_path": str(output), "model_version": version, "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
