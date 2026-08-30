import os
import warnings
import numpy as np
import pandas as pd

from sqlalchemy import create_engine, text

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.impute import SimpleImputer

from sklearn.ensemble import (
    RandomForestRegressor,
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    HistGradientBoostingRegressor,
)

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

import joblib

warnings.filterwarnings("ignore")


# ============================================================
# CONFIG
# ============================================================

DB_URL = os.getenv(
    "DB_URL",
    "postgresql+psycopg://damage:damage@postgres:5432/damage_ai"
)

DATASET_VERSION = "damagefire_001"

TEST_SIZE = 0.20
RANDOM_STATE = 42

MODEL_DIR = "/app/models"
os.makedirs(MODEL_DIR, exist_ok=True)


# ============================================================
# DATABASE
# ============================================================

engine = create_engine(DB_URL)


# ============================================================
# LOAD DATA
# ============================================================

print("=" * 80)
print("LOADING TRAINING DATA")
print("=" * 80)

query = text("""
    SELECT
        id,
        dataset_version,

        province_code,
        city_code,
        coverage_code,

        insurance_type_code,

        event_type_code,
        insured_item_type_code,
        damage_type_code,
        financial_damage_type_code,
        structure_type_code,
        risk_density_code,
        ownership_type_code,
        property_type_code,
        loss_location_code,
        occupation_code,
        occupation_group_code,

        premium,
        item_sum_insured,
        total_sum_insured,
        estimate_amount,

        paid_loss

    FROM vw_claim_ml_training
    WHERE dataset_version = :dataset_version
      AND paid_loss IS NOT NULL
      AND estimate_amount IS NOT NULL
""")

df = pd.read_sql(
    query,
    engine,
    params={"dataset_version": DATASET_VERSION}
)

print(f"Rows loaded: {len(df)}")


if len(df) < 100:
    raise RuntimeError(
        f"Not enough training data: {len(df)} rows"
    )


# ============================================================
# BASIC CLEANING
# ============================================================

df = df.copy()

df = df.replace([np.inf, -np.inf], np.nan)

df = df.dropna(
    subset=[
        "paid_loss",
        "estimate_amount"
    ]
)

df = df[df["paid_loss"] >= 0]
df = df[df["estimate_amount"] >= 0]

print(f"Rows after cleaning: {len(df)}")


# ============================================================
# FEATURES
# ============================================================

FEATURES = [
    "province_code",
    "city_code",
    "coverage_code",

    # IMPORTANT:
    "insurance_type_code",

    "event_type_code",
    "insured_item_type_code",
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

TARGET = "paid_loss"


# ============================================================
# X / y
# ============================================================

X = df[FEATURES].copy()
y = df[TARGET].astype(float).copy()


# ============================================================
# COLUMN TYPES
# ============================================================

CATEGORICAL_FEATURES = [
    "province_code",
    "city_code",
    "coverage_code",
    "insurance_type_code",
    "event_type_code",
    "insured_item_type_code",
    "damage_type_code",
    "financial_damage_type_code",
    "structure_type_code",
    "risk_density_code",
    "ownership_type_code",
    "property_type_code",
    "loss_location_code",
    "occupation_code",
    "occupation_group_code",
]

NUMERIC_FEATURES = [
    "premium",
    "item_sum_insured",
    "total_sum_insured",
    "estimate_amount",
]


# ============================================================
# PREPROCESSOR
# ============================================================

categorical_pipeline = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(
                strategy="most_frequent"
            )
        ),
        (
            "onehot",
            OneHotEncoder(
                handle_unknown="ignore",
                sparse_output=False
            )
        ),
    ]
)


numeric_pipeline = Pipeline(
    steps=[
        (
            "imputer",
            SimpleImputer(
                strategy="median"
            )
        ),
        (
            "scaler",
            StandardScaler()
        ),
    ]
)


preprocessor = ColumnTransformer(
    transformers=[
        (
            "categorical",
            categorical_pipeline,
            CATEGORICAL_FEATURES,
        ),
        (
            "numeric",
            numeric_pipeline,
            NUMERIC_FEATURES,
        ),
    ]
)


# ============================================================
# TRAIN / TEST SPLIT
# ============================================================

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=TEST_SIZE,
    random_state=RANDOM_STATE,
)

print()
print("=" * 80)
print("TRAIN / TEST SPLIT")
print("=" * 80)

print(f"Train rows: {len(X_train)}")
print(f"Test rows : {len(X_test)}")
print(f"Features  : {len(FEATURES)}")


# ============================================================
# MODELS
# ============================================================

models = {

    "random_forest": RandomForestRegressor(
        n_estimators=500,
        max_depth=None,
        min_samples_leaf=2,
        max_features="sqrt",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    ),

    "extra_trees": ExtraTreesRegressor(
        n_estimators=500,
        max_depth=None,
        min_samples_leaf=2,
        max_features=1.0,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    ),

    "gradient_boosting": GradientBoostingRegressor(
        n_estimators=300,
        learning_rate=0.03,
        max_depth=3,
        min_samples_leaf=5,
        loss="huber",
        random_state=RANDOM_STATE,
    ),

    "hist_gradient_boosting": HistGradientBoostingRegressor(
        max_iter=300,
        learning_rate=0.05,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        random_state=RANDOM_STATE,
    ),
}


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(y_true, y_pred):

    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    mae = mean_absolute_error(
        y_true,
        y_pred
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_true,
            y_pred
        )
    )

    r2 = r2_score(
        y_true,
        y_pred
    )

    # Avoid division by zero
    mask = y_true != 0

    if mask.sum() > 0:

        error_pct = (
            np.abs(
                y_pred[mask] - y_true[mask]
            )
            / np.abs(y_true[mask])
        )

        within_10 = np.mean(
            error_pct <= 0.10
        )

        within_20 = np.mean(
            error_pct <= 0.20
        )

    else:

        within_10 = 0.0
        within_20 = 0.0

    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
        "within_10pct": float(within_10),
        "within_20pct": float(within_20),
    }


# ============================================================
# TRAIN ALL MODELS
# ============================================================

results = []


for algorithm, model in models.items():

    for target_mode in ["raw", "log"]:

        print()
        print("=" * 80)
        print(
            f"TRAINING: {algorithm} | TARGET={target_mode}"
        )
        print("=" * 80)

        if target_mode == "log":

            y_train_model = np.log1p(
                y_train
            )

        else:

            y_train_model = y_train.copy()


        pipeline = Pipeline(
            steps=[
                (
                    "preprocessor",
                    preprocessor
                ),
                (
                    "model",
                    model
                ),
            ]
        )


        # ----------------------------------------------------
        # Train
        # ----------------------------------------------------

        pipeline.fit(
            X_train,
            y_train_model
        )


        # ----------------------------------------------------
        # Predict
        # ----------------------------------------------------

        pred = pipeline.predict(
            X_test
        )


        # ----------------------------------------------------
        # Convert log prediction back
        # ----------------------------------------------------

        if target_mode == "log":

            pred = np.expm1(pred)

        pred = np.maximum(
            pred,
            0
        )


        # ----------------------------------------------------
        # Metrics
        # ----------------------------------------------------

        metrics = calculate_metrics(
            y_test,
            pred
        )


        print(
            f"MAE          : {metrics['mae']:,.0f}"
        )

        print(
            f"RMSE         : {metrics['rmse']:,.0f}"
        )

        print(
            f"R2           : {metrics['r2']:.4f}"
        )

        print(
            f"Within 10%   : "
            f"{metrics['within_10pct'] * 100:.2f}%"
        )

        print(
            f"Within 20%   : "
            f"{metrics['within_20pct'] * 100:.2f}%"
        )


        # ----------------------------------------------------
        # Version
        # ----------------------------------------------------

        model_version = (
            f"{DATASET_VERSION}_"
            f"{algorithm}_"
            f"{target_mode}_v2"
        )


        # ----------------------------------------------------
        # Save model
        # ----------------------------------------------------

        model_path = os.path.join(
            MODEL_DIR,
            f"{model_version}.joblib"
        )

        joblib.dump(
            pipeline,
            model_path
        )


        results.append({
            "model_version": model_version,
            "algorithm": algorithm,
            "target_mode": target_mode,
            "train_rows": len(X_train),
            "test_rows": len(X_test),
            "mae": metrics["mae"],
            "rmse": metrics["rmse"],
            "r2": metrics["r2"],
            "within_10pct": metrics["within_10pct"],
            "within_20pct": metrics["within_20pct"],
            "model_path": model_path,
        })


# ============================================================
# RESULTS
# ============================================================

results_df = pd.DataFrame(results)


print()
print("=" * 100)
print("MODEL COMPARISON")
print("=" * 100)

print(
    results_df[
        [
            "algorithm",
            "target_mode",
            "mae",
            "rmse",
            "r2",
            "within_10pct",
            "within_20pct",
        ]
    ].to_string(index=False)
)


# ============================================================
# BEST MODEL
# ============================================================

# Primary criterion:
# lower MAE
#
# Secondary:
# higher R2
# higher within_20pct

results_df = results_df.sort_values(
    by=[
        "mae",
        "r2",
        "within_20pct",
    ],
    ascending=[
        True,
        False,
        False,
    ]
)


best = results_df.iloc[0]


print()
print("=" * 100)
print("BEST MODEL")
print("=" * 100)

print(
    f"Model       : {best['model_version']}"
)

print(
    f"Algorithm   : {best['algorithm']}"
)

print(
    f"Target mode : {best['target_mode']}"
)

print(
    f"MAE         : {best['mae']:,.0f}"
)

print(
    f"RMSE        : {best['rmse']:,.0f}"
)

print(
    f"R2          : {best['r2']:.4f}"
)

print(
    f"Within 10%  : "
    f"{best['within_10pct'] * 100:.2f}%"
)

print(
    f"Within 20%  : "
    f"{best['within_20pct'] * 100:.2f}%"
)


# ============================================================
# SAVE TO model_runs
# ============================================================

with engine.begin() as conn:

    # deactivate previous active models
    conn.execute(
        text("""
            UPDATE model_runs
            SET status = 'candidate'
            WHERE dataset_version = :dataset_version
        """),
        {
            "dataset_version": DATASET_VERSION
        }
    )


    for _, row in results_df.iterrows():

        conn.execute(
            text("""
                INSERT INTO model_runs (
                    model_version,
                    algorithm,
                    train_rows,
                    test_rows,
                    mae,
                    rmse,
                    r2,
                    accuracy_percent,
                    within_10pct,
                    within_20pct,
                    status
                )
                VALUES (
                    :model_version,
                    :algorithm,
                    :train_rows,
                    :test_rows,
                    :mae,
                    :rmse,
                    :r2,
                    :accuracy_percent,
                    :within_10pct,
                    :within_20pct,
                    :status
                )
            """),
            {
                "model_version": row["model_version"],
                "algorithm": row["algorithm"],
                "train_rows": int(row["train_rows"]),
                "test_rows": int(row["test_rows"]),
                "mae": row["mae"],
                "rmse": row["rmse"],
                "r2": row["r2"],

                # Keep this field for compatibility.
                # We do not use it as a real accuracy metric.
                "accuracy_percent": 0.0,

                "within_10pct": row["within_10pct"],
                "within_20pct": row["within_20pct"],

                "status": (
                    "active"
                    if row["model_version"]
                    == best["model_version"]
                    else "candidate"
                ),
            }
        )


print()
print("=" * 80)
print("TRAINING COMPLETED")
print("=" * 80)

print(
    f"Best model saved: {best['model_path']}"
)

print(
    f"Active model: {best['model_version']}"
)