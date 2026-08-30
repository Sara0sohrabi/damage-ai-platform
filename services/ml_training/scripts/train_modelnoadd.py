import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sqlalchemy import create_engine, text

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    RandomForestRegressor,
    HistGradientBoostingRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


# ============================================================
# CONFIG
# ============================================================

DATASET_VERSION = os.getenv(
    "DATASET_VERSION",
    "damagefire_001",
)

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://damage:damage_dev@postgres:5432/damage_ai",
)

MODEL_DIR = Path(
    os.getenv(
        "MODEL_DIR",
        "/app/models",
    )
)

MODEL_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

REPORT_DIR = Path(
    os.getenv(
        "REPORT_DIR",
        "/reports",
    )
)

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

RANDOM_STATE = 42
TEST_SIZE = 0.20

TARGET_COLUMN = "paid_loss"

MODEL_VERSION_PREFIX = "damagefire_001"


# ============================================================
# FEATURES
# ============================================================

CATEGORICAL_FEATURES = [
    "province_code",
    "city_code",
    "coverage_code",
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


ALL_FEATURES = (
    CATEGORICAL_FEATURES
    + NUMERIC_FEATURES
)


# ============================================================
# LOAD DATASET
# ============================================================

def load_dataset():

    print()
    print("=" * 100)
    print("LOADING DATA FROM POSTGRESQL")
    print("=" * 100)

    print(
        "Source          : vw_claim_ml_training"
    )

    print(
        f"Dataset version : {DATASET_VERSION}"
    )

    query = text(
        """
        SELECT
            id,
            dataset_version,
            province_code,
            city_code,
            coverage_code,
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
        ORDER BY id
        """
    )

    engine = create_engine(
        DB_URL,
        pool_pre_ping=True,
    )

    with engine.connect() as connection:

        df = pd.read_sql(
            query,
            connection,
            params={
                "dataset_version": DATASET_VERSION
            },
        )

    if df.empty:

        raise RuntimeError(
            "vw_claim_ml_training returned zero rows."
        )

    print(
        f"Rows loaded     : {len(df)}"
    )

    print(
        f"Columns loaded  : {len(df.columns)}"
    )

    print(
        f"Target          : {TARGET_COLUMN}"
    )

    return df


# ============================================================
# DATA QUALITY
# ============================================================

def data_quality_check(df):

    print()
    print("=" * 100)
    print("DATA QUALITY CHECK")
    print("=" * 100)

    target = pd.to_numeric(
        df[TARGET_COLUMN],
        errors="coerce",
    )

    print(
        f"Total rows          : {len(df)}"
    )

    print(
        f"Target missing      : {target.isna().sum()}"
    )

    print(
        f"Target negative     : {(target < 0).sum()}"
    )

    print(
        f"Target zero         : {(target == 0).sum()}"
    )

    print(
        f"Target positive     : {(target > 0).sum()}"
    )

    print()
    print("IMPORTANT:")

    print(
        "paid_loss is TARGET only."
    )

    print(
        "paid_loss is NEVER used as a feature."
    )

    print(
        "Each row represents ONE independent claim."
    )

    print(
        "No GROUP BY."
    )

    print(
        "No SUM between claims."
    )

    print(
        "No aggregation of claim losses."
    )


# ============================================================
# PREPARE DATA
# ============================================================

def prepare_data(df):

    print()
    print("=" * 100)
    print("PREPARING FEATURES")
    print("=" * 100)

    required_columns = (
        ALL_FEATURES
        + [TARGET_COLUMN]
    )

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:

        raise RuntimeError(
            "Missing required columns:\n"
            + "\n".join(missing)
        )

    work = df.copy()

    # --------------------------------------------------------
    # Numeric
    # --------------------------------------------------------

    for column in NUMERIC_FEATURES:

        work[column] = pd.to_numeric(
            work[column],
            errors="coerce",
        )

    # --------------------------------------------------------
    # Categorical
    # --------------------------------------------------------

    for column in CATEGORICAL_FEATURES:

        work[column] = (
            work[column]
            .astype("string")
            .str.strip()
        )

        work[column] = work[column].replace(
            {
                "": np.nan,
                "nan": np.nan,
                "None": np.nan,
                "null": np.nan,
            }
        )

    # --------------------------------------------------------
    # Target
    # --------------------------------------------------------

    work[TARGET_COLUMN] = pd.to_numeric(
        work[TARGET_COLUMN],
        errors="coerce",
    )

    valid = (
        work[TARGET_COLUMN].notna()
        &
        (work[TARGET_COLUMN] >= 0)
    )

    work = (
        work
        .loc[valid]
        .reset_index(drop=True)
    )

    if work.empty:

        raise RuntimeError(
            "No valid training rows after target validation."
        )

    X = work[
        ALL_FEATURES
    ].copy()

    y = work[
        TARGET_COLUMN
    ].copy()

    print(
        f"Usable rows        : {len(work)}"
    )

    print(
        f"Categorical feats  : {len(CATEGORICAL_FEATURES)}"
    )

    print(
        f"Numeric feats      : {len(NUMERIC_FEATURES)}"
    )

    print(
        f"Total features     : {len(ALL_FEATURES)}"
    )

    print()
    print("FEATURES:")

    for feature in ALL_FEATURES:

        print(
            f"  - {feature}"
        )

    print()
    print("TARGET:")

    print(
        f"  - {TARGET_COLUMN}"
    )

    return X, y, work


# ============================================================
# PREPROCESSOR — SPARSE
# ============================================================

def create_sparse_preprocessor():

    numeric_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(
                    strategy="median"
                ),
            ),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(
                    strategy="most_frequent"
                ),
            ),
            (
                "onehot",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=True,
                ),
            ),
        ]
    )

    return ColumnTransformer(
        transformers=[
            (
                "numeric",
                numeric_pipeline,
                NUMERIC_FEATURES,
            ),
            (
                "categorical",
                categorical_pipeline,
                CATEGORICAL_FEATURES,
            ),
        ]
    )


# ============================================================
# PREPROCESSOR — DENSE
# FOR HIST GRADIENT BOOSTING
# ============================================================

def create_dense_preprocessor():

    numeric_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(
                    strategy="median"
                ),
            ),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(
                    strategy="most_frequent"
                ),
            ),
            (
                "onehot",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=False,
                ),
            ),
        ]
    )

    return ColumnTransformer(
        transformers=[
            (
                "numeric",
                numeric_pipeline,
                NUMERIC_FEATURES,
            ),
            (
                "categorical",
                categorical_pipeline,
                CATEGORICAL_FEATURES,
            ),
        ],
        sparse_threshold=0,
    )


# ============================================================
# MODELS
# ============================================================

def get_models():

    return {

        "random_forest": RandomForestRegressor(
            n_estimators=500,
            max_depth=12,
            min_samples_leaf=2,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),

        "extra_trees": ExtraTreesRegressor(
            n_estimators=500,
            max_depth=12,
            min_samples_leaf=2,
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),

        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=400,
            learning_rate=0.03,
            max_depth=3,
            min_samples_leaf=3,
            loss="huber",
            random_state=RANDOM_STATE,
        ),

        "hist_gradient_boosting": HistGradientBoostingRegressor(
            max_iter=400,
            learning_rate=0.05,
            max_leaf_nodes=31,
            l2_regularization=1.0,
            random_state=RANDOM_STATE,
        ),
    }


# ============================================================
# PIPELINE
# ============================================================

def create_pipeline(
    model_name,
    model,
):

    if model_name == "hist_gradient_boosting":

        preprocessor = (
            create_dense_preprocessor()
        )

    else:

        preprocessor = (
            create_sparse_preprocessor()
        )

    return Pipeline(
        steps=[
            (
                "preprocessor",
                preprocessor,
            ),
            (
                "model",
                model,
            ),
        ]
    )


# ============================================================
# WITHIN PERCENT
# ============================================================

def calculate_within_percentage(
    actual,
    prediction,
    percentage,
):

    actual = np.asarray(
        actual,
        dtype=float,
    )

    prediction = np.asarray(
        prediction,
        dtype=float,
    )

    denominator = np.maximum(
        np.abs(actual),
        1.0,
    )

    relative_error = (
        np.abs(
            actual - prediction
        )
        /
        denominator
    )

    return float(
        np.mean(
            relative_error <= percentage
        )
    )


# ============================================================
# OPERATIONAL ACCURACY
# ============================================================

def calculate_accuracy_percent(
    actual,
    prediction,
):

    actual = np.asarray(
        actual,
        dtype=float,
    )

    prediction = np.asarray(
        prediction,
        dtype=float,
    )

    mean_actual = float(
        np.mean(
            np.abs(actual)
        )
    )

    if mean_actual <= 0:

        return 0.0

    mae = mean_absolute_error(
        actual,
        prediction,
    )

    accuracy = (
        1.0
        -
        mae / mean_actual
    ) * 100.0

    return float(
        max(
            0.0,
            min(
                100.0,
                accuracy,
            ),
        )
    )


# ============================================================
# TRAIN ONE MODEL
# ============================================================

def train_one_model(
    model_name,
    target_mode,
    model,
    X_train,
    X_test,
    y_train,
    y_test,
):

    print()
    print("-" * 100)

    print(
        f"TRAINING MODEL : {model_name}"
    )

    print(
        f"TARGET MODE    : {target_mode}"
    )

    if model_name == "hist_gradient_boosting":

        print(
            "PREPROCESSING   : DENSE"
        )

    else:

        print(
            "PREPROCESSING   : SPARSE"
        )

    print("-" * 100)

    pipeline = create_pipeline(
        model_name=model_name,
        model=model,
    )

    # --------------------------------------------------------
    # Target transformation
    # --------------------------------------------------------

    if target_mode == "log":

        y_train_model = np.log1p(
            y_train
        )

    else:

        y_train_model = y_train.copy()

    # --------------------------------------------------------
    # Fit
    # --------------------------------------------------------

    pipeline.fit(
        X_train,
        y_train_model,
    )

    # --------------------------------------------------------
    # Predict
    # --------------------------------------------------------

    prediction_model = pipeline.predict(
        X_test
    )

    if target_mode == "log":

        prediction = np.expm1(
            prediction_model
        )

    else:

        prediction = prediction_model

    prediction = np.maximum(
        prediction,
        0.0,
    )

    # --------------------------------------------------------
    # Metrics
    # --------------------------------------------------------

    mae = mean_absolute_error(
        y_test,
        prediction,
    )

    rmse = np.sqrt(
        mean_squared_error(
            y_test,
            prediction,
        )
    )

    r2 = r2_score(
        y_test,
        prediction,
    )

    accuracy_percent = (
        calculate_accuracy_percent(
            y_test,
            prediction,
        )
    )

    within_10pct = (
        calculate_within_percentage(
            y_test,
            prediction,
            0.10,
        )
    )

    within_20pct = (
        calculate_within_percentage(
            y_test,
            prediction,
            0.20,
        )
    )

    print(
        f"MAE             : {mae:,.2f}"
    )

    print(
        f"RMSE            : {rmse:,.2f}"
    )

    print(
        f"R2              : {r2:.4f}"
    )

    print(
        f"Accuracy        : {accuracy_percent:.2f}%"
    )

    print(
        f"Within 10%      : "
        f"{within_10pct * 100:.2f}%"
    )

    print(
        f"Within 20%      : "
        f"{within_20pct * 100:.2f}%"
    )

    return {
        "pipeline": pipeline,
        "prediction": prediction,
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
        "accuracy_percent": float(
            accuracy_percent
        ),
        "within_10pct": float(
            within_10pct
        ),
        "within_20pct": float(
            within_20pct
        ),
    }


# ============================================================
# SAVE MODEL
# ============================================================

def save_model(
    result,
    model_name,
    target_mode,
):

    filename = (
        f"damage_prediction_"
        f"{model_name}_"
        f"{target_mode}.joblib"
    )

    path = (
        MODEL_DIR
        /
        filename
    )

    model_version = (
        f"{MODEL_VERSION_PREFIX}_"
        f"{model_name}_"
        f"{target_mode}_v1"
    )

    artifact = {

        "model":
            result["pipeline"],

        "model_name":
            model_name,

        "model_version":
            model_version,

        "dataset_version":
            DATASET_VERSION,

        "target":
            TARGET_COLUMN,

        "features":
            ALL_FEATURES,

        "categorical_features":
            CATEGORICAL_FEATURES,

        "numeric_features":
            NUMERIC_FEATURES,

        "metrics": {

            "mae":
                result["mae"],

            "rmse":
                result["rmse"],

            "r2":
                result["r2"],

            "accuracy_percent":
                result["accuracy_percent"],

            "within_10pct":
                result["within_10pct"],

            "within_20pct":
                result["within_20pct"],
        },

        "architecture": {

            "independent_claims":
                True,

            "aggregation":
                False,

            "group_by":
                False,

            "sum_claim_losses":
                False,

            "target_leakage":
                False,
        },
    }

    joblib.dump(
        artifact,
        path,
    )

    print(
        f"Model saved: {path}"
    )

    return str(path)


# ============================================================
# SAVE TEST PREDICTIONS
# ============================================================

def save_test_predictions(
    valid_df,
    test_indices,
    y_test,
    prediction,
    model_name,
    target_mode,
):

    result_df = valid_df.iloc[
        test_indices
    ].copy()

    result_df[
        "actual_paid_loss"
    ] = y_test.to_numpy()

    result_df[
        "predicted_paid_loss"
    ] = prediction

    result_df[
        "absolute_error"
    ] = (
        result_df[
            "actual_paid_loss"
        ]
        -
        result_df[
            "predicted_paid_loss"
        ]
    ).abs()

    result_df[
        "error_percent"
    ] = np.where(

        result_df[
            "actual_paid_loss"
        ].abs() > 0,

        (
            result_df[
                "absolute_error"
            ]
            /
            result_df[
                "actual_paid_loss"
            ].abs()
            * 100
        ),

        np.nan,
    )

    result_df[
        "accuracy_percent_claim"
    ] = np.where(

        result_df[
            "actual_paid_loss"
        ].abs() > 0,

        (
            1
            -
            (
                result_df[
                    "absolute_error"
                ]
                /
                result_df[
                    "actual_paid_loss"
                ].abs()
            )
        )
        * 100,

        np.nan,
    )

    result_df[
        "within_10pct"
    ] = (
        result_df[
            "error_percent"
        ]
        <= 10
    )

    result_df[
        "within_20pct"
    ] = (
        result_df[
            "error_percent"
        ]
        <= 20
    )

    filename = (
        f"test_predictions_"
        f"{model_name}_"
        f"{target_mode}.csv"
    )

    output = (
        MODEL_DIR
        /
        filename
    )

    result_df.to_csv(
        output,
        index=False,
    )

    return result_df


# ============================================================
# TOP ERRORS
# ============================================================

def save_top_errors(
    result_df,
    model_name,
    target_mode,
):

    filename = (
        f"top_test_errors_"
        f"{model_name}_"
        f"{target_mode}.csv"
    )

    output = (
        MODEL_DIR
        /
        filename
    )

    top = (
        result_df
        .sort_values(
            by="absolute_error",
            ascending=False,
        )
        .head(100)
    )

    top.to_csv(
        output,
        index=False,
    )

    print()
    print("=" * 100)
    print("TOP TEST ERRORS")
    print("=" * 100)

    display_columns = [
        "id",
        "province_code",
        "city_code",
        "coverage_code",
        "damage_type_code",
        "estimate_amount",
        "actual_paid_loss",
        "predicted_paid_loss",
        "absolute_error",
        "error_percent",
        "accuracy_percent_claim",
    ]

    display_columns = [
        column
        for column in display_columns
        if column in top.columns
    ]

    print(
        top[
            display_columns
        ]
        .head(20)
        .to_string(
            index=False
        )
    )

    print()
    print(
        f"Saved: {output}"
    )


# ============================================================
# SAVE COMPARISON
# ============================================================

def save_comparison(results):

    comparison = pd.DataFrame(
        results
    )

    if comparison.empty:

        raise RuntimeError(
            "No successful models to compare."
        )

    comparison = (
        comparison
        .sort_values(
            by=[
                "accuracy_percent",
                "within_20pct",
                "R2",
                "MAE",
            ],
            ascending=[
                False,
                False,
                False,
                True,
            ],
        )
        .reset_index(
            drop=True
        )
    )

    output = (
        MODEL_DIR
        /
        "model_comparison.csv"
    )

    comparison.to_csv(
        output,
        index=False,
    )

    print()
    print("=" * 100)
    print("MODEL COMPARISON")
    print("=" * 100)

    print(
        comparison.to_string(
            index=False
        )
    )

    print()
    print(
        f"Comparison saved: {output}"
    )

    return comparison


# ============================================================
# DATABASE ENGINE
# ============================================================

def get_engine():

    return create_engine(
        DB_URL,
        pool_pre_ping=True,
    )


# ============================================================
# SAVE MODEL RUN
# ============================================================

def save_model_run(
    engine,
    model_version,
    algorithm,
    test_size,
    train_rows,
    test_rows,
    mae,
    rmse,
    r2,
    accuracy_percent,
    within_10pct,
    within_20pct,
    artifact_path,
    status="candidate",
):

    query = text(
        """
        INSERT INTO model_runs
        (
            model_version,
            dataset_version,
            algorithm,
            test_size,
            train_rows,
            test_rows,
            mae,
            rmse,
            r2,
            accuracy_percent,
            within_10pct,
            within_20pct,
            cluster_count,
            status,
            artifact_path
        )
        VALUES
        (
            :model_version,
            :dataset_version,
            :algorithm,
            :test_size,
            :train_rows,
            :test_rows,
            :mae,
            :rmse,
            :r2,
            :accuracy_percent,
            :within_10pct,
            :within_20pct,
            :cluster_count,
            :status,
            :artifact_path
        )
        """
    )

    with engine.begin() as connection:

        connection.execute(
            query,
            {
                "model_version":
                    model_version,

                "dataset_version":
                    DATASET_VERSION,

                "algorithm":
                    algorithm,

                "test_size":
                    test_size,

                "train_rows":
                    train_rows,

                "test_rows":
                    test_rows,

                "mae":
                    mae,

                "rmse":
                    rmse,

                "r2":
                    r2,

                "accuracy_percent":
                    accuracy_percent,

                "within_10pct":
                    within_10pct,

                "within_20pct":
                    within_20pct,

                "cluster_count":
                    None,

                "status":
                    status,

                "artifact_path":
                    artifact_path,
            },
        )

    print(
        f"DB model_runs saved: {model_version}"
    )


# ============================================================
# ACTIVATE BEST MODEL
# ============================================================

def activate_best_model(
    engine,
    model_version,
):

    print()
    print("=" * 100)
    print("ACTIVATING BEST MODEL")
    print("=" * 100)

    with engine.begin() as connection:

        connection.execute(
            text(
                """
                UPDATE model_runs
                SET status = 'inactive'
                WHERE status = 'active'
                """
            )
        )

        result = connection.execute(
            text(
                """
                UPDATE model_runs
                SET status = 'active'
                WHERE model_version = :model_version
                """
            ),
            {
                "model_version":
                    model_version
            },
        )

        if result.rowcount != 1:

            raise RuntimeError(
                "Could not activate selected model."
            )

    print(
        f"ACTIVE MODEL: {model_version}"
    )


# ============================================================
# VERIFY REGISTRY
# ============================================================

def verify_model_registry(
    engine,
):

    print()
    print("=" * 100)
    print("MODEL REGISTRY")
    print("=" * 100)

    query = text(
        """
        SELECT
            id,
            model_version,
            dataset_version,
            algorithm,
            train_rows,
            test_rows,
            mae,
            rmse,
            r2,
            accuracy_percent,
            within_10pct,
            within_20pct,
            status,
            artifact_path,
            created_at
        FROM model_runs
        ORDER BY created_at DESC, id DESC
        """
    )

    with engine.connect() as connection:

        rows = (
            connection
            .execute(query)
            .mappings()
            .all()
        )

    if not rows:

        raise RuntimeError(
            "model_runs is empty after training."
        )

    for row in rows:

        print()
        print(
            f"ID              : {row['id']}"
        )

        print(
            f"Model Version   : {row['model_version']}"
        )

        print(
            f"Dataset         : {row['dataset_version']}"
        )

        print(
            f"Algorithm       : {row['algorithm']}"
        )

        print(
            f"Train Rows      : {row['train_rows']}"
        )

        print(
            f"Test Rows       : {row['test_rows']}"
        )

        print(
            f"MAE             : {row['mae']}"
        )

        print(
            f"RMSE            : {row['rmse']}"
        )

        print(
            f"R2              : {row['r2']}"
        )

        print(
            f"Accuracy        : "
            f"{row['accuracy_percent']}%"
        )

        print(
            f"Within 10%      : "
            f"{float(row['within_10pct']) * 100:.2f}%"
        )

        print(
            f"Within 20%      : "
            f"{float(row['within_20pct']) * 100:.2f}%"
        )

        print(
            f"Status          : {row['status']}"
        )

        print(
            f"Artifact        : {row['artifact_path']}"
        )

    with engine.connect() as connection:

        active_count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM model_runs
                WHERE status = 'active'
                """
            )
        ).scalar_one()

    if active_count != 1:

        raise RuntimeError(
            f"Expected exactly 1 active model, "
            f"found {active_count}."
        )

    print()
    print(
        f"Active model count: {active_count}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 110)
    print("DAMAGE AI — CLAIM LOSS MODEL TRAINING")
    print("=" * 110)

    print()
    print("ARCHITECTURE")

    print(
        "Each PostgreSQL row = ONE independent claim."
    )

    print(
        "No GROUP BY."
    )

    print(
        "No SUM between claims."
    )

    print(
        "No aggregation of claim losses."
    )

    print()
    print("TARGET:")
    print("paid_loss")

    print()
    print("FEATURE:")
    print("estimate_amount")

    print()
    print("TARGET LEAKAGE:")
    print("paid_loss is NEVER included in X.")

    # --------------------------------------------------------
    # LOAD
    # --------------------------------------------------------

    df = load_dataset()

    # --------------------------------------------------------
    # QUALITY
    # --------------------------------------------------------

    data_quality_check(
        df
    )

    # --------------------------------------------------------
    # PREPARE
    # --------------------------------------------------------

    X, y, valid_df = prepare_data(
        df
    )

    # --------------------------------------------------------
    # SPLIT
    # --------------------------------------------------------

    print()
    print("=" * 100)
    print("TRAIN / TEST SPLIT")
    print("=" * 100)

    indices = np.arange(
        len(X)
    )

    (
        X_train,
        X_test,
        y_train,
        y_test,
        train_indices,
        test_indices,
    ) = train_test_split(
        X,
        y,
        indices,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    print(
        f"Total : {len(X)}"
    )

    print(
        f"Train : {len(X_train)}"
    )

    print(
        f"Test  : {len(X_test)}"
    )

    # --------------------------------------------------------
    # MODELS
    # --------------------------------------------------------

    models = get_models()

    all_results = []

    detailed_results = []

    # --------------------------------------------------------
    # TRAIN
    # --------------------------------------------------------

    for target_mode in [
        "raw",
        "log",
    ]:

        for model_name, model in models.items():

            try:

                result = train_one_model(
                    model_name=model_name,
                    target_mode=target_mode,
                    model=model,
                    X_train=X_train,
                    X_test=X_test,
                    y_train=y_train,
                    y_test=y_test,
                )

                artifact_path = save_model(
                    result=result,
                    model_name=model_name,
                    target_mode=target_mode,
                )

                test_predictions = (
                    save_test_predictions(
                        valid_df=valid_df,
                        test_indices=test_indices,
                        y_test=y_test,
                        prediction=result[
                            "prediction"
                        ],
                        model_name=model_name,
                        target_mode=target_mode,
                    )
                )

                detailed_results.append(
                    {
                        "model":
                            model_name,

                        "target_mode":
                            target_mode,

                        "pipeline":
                            result[
                                "pipeline"
                            ],

                        "prediction":
                            result[
                                "prediction"
                            ],

                        "mae":
                            result["mae"],

                        "rmse":
                            result["rmse"],

                        "r2":
                            result["r2"],

                        "accuracy_percent":
                            result[
                                "accuracy_percent"
                            ],

                        "within_10pct":
                            result[
                                "within_10pct"
                            ],

                        "within_20pct":
                            result[
                                "within_20pct"
                            ],

                        "artifact_path":
                            artifact_path,

                        "test_predictions":
                            test_predictions,
                    }
                )

                all_results.append(
                    {
                        "model":
                            model_name,

                        "target_mode":
                            target_mode,

                        "MAE":
                            result["mae"],

                        "RMSE":
                            result["rmse"],

                        "R2":
                            result["r2"],

                        "accuracy_percent":
                            result[
                                "accuracy_percent"
                            ],

                        "within_10pct":
                            result[
                                "within_10pct"
                            ],

                        "within_20pct":
                            result[
                                "within_20pct"
                            ],
                    }
                )

            except Exception as error:

                print()
                print("!" * 100)

                print(
                    f"MODEL FAILED: "
                    f"{model_name} / "
                    f"{target_mode}"
                )

                print(
                    f"ERROR: {error}"
                )

                print(
                    "Training will continue "
                    "with the remaining models."
                )

                print("!" * 100)

                continue

    # --------------------------------------------------------
    # CHECK
    # --------------------------------------------------------

    if not detailed_results:

        raise RuntimeError(
            "ALL MODELS FAILED. "
            "No model was successfully trained."
        )

    # --------------------------------------------------------
    # COMPARISON
    # --------------------------------------------------------

    comparison = save_comparison(
        all_results
    )

    # --------------------------------------------------------
    # BEST
    # --------------------------------------------------------

    best_row = comparison.iloc[0]

    best_model_name = (
        best_row["model"]
    )

    best_target_mode = (
        best_row["target_mode"]
    )

    best_detail = next(
        item
        for item in detailed_results
        if (
            item["model"]
            == best_model_name
            and
            item["target_mode"]
            == best_target_mode
        )
    )

    print()
    print("=" * 100)
    print("BEST MODEL")
    print("=" * 100)

    print(
        f"Model       : {best_model_name}"
    )

    print(
        f"Target mode : {best_target_mode}"
    )

    print(
        f"MAE         : "
        f"{best_detail['mae']:,.2f}"
    )

    print(
        f"RMSE        : "
        f"{best_detail['rmse']:,.2f}"
    )

    print(
        f"R2          : "
        f"{best_detail['r2']:.4f}"
    )

    print(
        f"Accuracy    : "
        f"{best_detail['accuracy_percent']:.2f}%"
    )

    print(
        f"Within 10%  : "
        f"{best_detail['within_10pct'] * 100:.2f}%"
    )

    print(
        f"Within 20%  : "
        f"{best_detail['within_20pct'] * 100:.2f}%"
    )

    # --------------------------------------------------------
    # TOP ERRORS
    # --------------------------------------------------------

    save_top_errors(
        result_df=best_detail[
            "test_predictions"
        ],
        model_name=best_model_name,
        target_mode=best_target_mode,
    )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    engine = get_engine()

    print()
    print("=" * 100)
    print("SAVING MODEL RUNS TO POSTGRESQL")
    print("=" * 100)

    for item in detailed_results:

        model_version = (
            f"{MODEL_VERSION_PREFIX}_"
            f"{item['model']}_"
            f"{item['target_mode']}_"
            f"v1"
        )

        # Remove previous run of same version

        with engine.begin() as connection:

            connection.execute(
                text(
                    """
                    DELETE FROM model_runs
                    WHERE model_version =
                          :model_version
                    """
                ),
                {
                    "model_version":
                        model_version
                },
            )

        save_model_run(
            engine=engine,

            model_version=
                model_version,

            algorithm=
                item["model"],

            test_size=
                TEST_SIZE,

            train_rows=
                len(X_train),

            test_rows=
                len(X_test),

            mae=
                item["mae"],

            rmse=
                item["rmse"],

            r2=
                item["r2"],

            accuracy_percent=
                item[
                    "accuracy_percent"
                ],

            within_10pct=
                item[
                    "within_10pct"
                ],

            within_20pct=
                item[
                    "within_20pct"
                ],

            artifact_path=
                item[
                    "artifact_path"
                ],

            status=
                "candidate",
        )

    # --------------------------------------------------------
    # ACTIVATE BEST
    # --------------------------------------------------------

    best_model_version = (
        f"{MODEL_VERSION_PREFIX}_"
        f"{best_model_name}_"
        f"{best_target_mode}_"
        f"v1"
    )

    activate_best_model(
        engine=engine,
        model_version=
            best_model_version,
    )

    # --------------------------------------------------------
    # VERIFY
    # --------------------------------------------------------

    verify_model_registry(
        engine
    )

    # --------------------------------------------------------
    # FINAL
    # --------------------------------------------------------

    print()
    print("=" * 100)
    print("TRAINING COMPLETED SUCCESSFULLY")
    print("=" * 100)

    print(
        f"Best model       : "
        f"{best_model_name}"
    )

    print(
        f"Target           : "
        f"{TARGET_COLUMN}"
    )

    print(
        f"Target mode      : "
        f"{best_target_mode}"
    )

    print(
        f"Accuracy         : "
        f"{best_detail['accuracy_percent']:.2f}%"
    )

    print(
        f"R2               : "
        f"{best_detail['r2']:.4f}"
    )

    print(
        f"MAE              : "
        f"{best_detail['mae']:,.2f}"
    )

    print(
        f"RMSE             : "
        f"{best_detail['rmse']:,.2f}"
    )

    print(
        f"Within 10%       : "
        f"{best_detail['within_10pct'] * 100:.2f}%"
    )

    print(
        f"Within 20%       : "
        f"{best_detail['within_20pct'] * 100:.2f}%"
    )

    print(
        f"Model file       : "
        f"{best_detail['artifact_path']}"
    )

    print(
        f"Model DB version : "
        f"{best_model_version}"
    )

    print(
        f"Train rows       : "
        f"{len(X_train)}"
    )

    print(
        f"Test rows        : "
        f"{len(X_test)}"
    )

    print()
    print(
        "Each claim was evaluated independently."
    )

    print(
        "paid_loss was used ONLY as the target."
    )

    print(
        "The best model is now ACTIVE."
    )


if __name__ == "__main__":

    main()