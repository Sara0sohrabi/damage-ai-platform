import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import (
    RandomForestRegressor,
    GradientBoostingRegressor,
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
from sklearn.preprocessing import StandardScaler


# ============================================================
# CONFIG
# ============================================================

DATASET_VERSION = "damagefire_001"

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://damage:damage@postgres:5432/damage_ai"
)

MODEL_DIR = Path("/app/models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# CATEGORICAL JSON FEATURES
# ============================================================

LOW_CARDINALITY_JSON = [
    "province_codes",
    "event_type_codes",
    "coverage_codes",
    "occupation_group_codes",
    "damage_type_codes",
    "financial_damage_type_codes",
    "structure_codes",
    "risk_density_codes",
    "ownership_codes",
    "property_codes",
]


# ============================================================
# NUMERIC FEATURES
# ============================================================

BASE_NUMERIC_FEATURES = [
    "voucher_count",
    "province_count",
    "city_count",
    "event_type_count",
    "coverage_count",
    "occupation_count",
    "insured_item_count",
    "location_count",
    "structure_count",

    "premium_min",
    "premium_max",

    "item_sum_insured_min",
    "item_sum_insured_max",

    "total_sum_insured_min",
    "total_sum_insured_max",

    "has_unknown_structure",
    "has_unknown_risk_density",
    "has_unknown_ownership",
    "has_unknown_property",
]


# ============================================================
# ESTIMATE FEATURES
# ============================================================

ESTIMATE_FEATURES = [
    "estimate_amount_min",
    "estimate_amount_max",
]


# ============================================================
# JSON PARSER
# ============================================================

def parse_json_list(value):

    if value is None:
        return []

    if isinstance(value, list):
        return value

    try:

        value = json.loads(value)

        if isinstance(value, list):
            return value

    except Exception:
        pass

    return []


# ============================================================
# MULTI HOT ENCODING
# ============================================================

def make_multi_hot(df, column):

    values = sorted(
        {
            str(v)
            for row in df[column]
            for v in parse_json_list(row)
        }
    )

    result = pd.DataFrame(
        0,
        index=df.index,
        columns=[
            f"{column}__{v}"
            for v in values
        ],
        dtype=np.int8,
    )

    for idx, row in df[column].items():

        for value in parse_json_list(row):

            value = str(value)

            col = f"{column}__{value}"

            if col in result.columns:

                result.loc[idx, col] = 1

    return result


# ============================================================
# LOAD DATASET
# ============================================================

def load_dataset():

    query = f"""
        SELECT *
        FROM claim_ml_features
        WHERE dataset_version = '{DATASET_VERSION}'
        ORDER BY id
    """

    df = pd.read_sql(
        query,
        DB_URL,
    )

    if df.empty:

        raise RuntimeError(
            "claim_ml_features is empty."
        )

    return df


# ============================================================
# BUILD FEATURE MATRIX
# ============================================================

def build_feature_matrix(
    df,
    use_estimate,
):

    parts = []

    numeric_cols = list(
        BASE_NUMERIC_FEATURES
    )

    if use_estimate:

        numeric_cols += ESTIMATE_FEATURES

    numeric_df = df[
        numeric_cols
    ].copy()

    for col in numeric_df.columns:

        numeric_df[col] = pd.to_numeric(
            numeric_df[col],
            errors="coerce",
        )

    parts.append(
        numeric_df.reset_index(
            drop=True
        )
    )

    # --------------------------------------------------------
    # Multi-hot categorical features
    # --------------------------------------------------------

    for column in LOW_CARDINALITY_JSON:

        encoded = make_multi_hot(
            df,
            column,
        )

        parts.append(
            encoded.reset_index(
                drop=True
            )
        )

    X = pd.concat(
        parts,
        axis=1,
    )

    # --------------------------------------------------------
    # Target
    # --------------------------------------------------------

    y = pd.to_numeric(
        df["paid_loss"],
        errors="coerce",
    )

    # --------------------------------------------------------
    # Valid rows
    # --------------------------------------------------------

    valid = (
        y.notna()
        &
        (y >= 0)
    )

    X = X.loc[
        valid
    ].reset_index(
        drop=True
    )

    y = y.loc[
        valid
    ].reset_index(
        drop=True
    )

    # VERY IMPORTANT:
    # Keep original claim information aligned
    # with X and y.

    valid_df = df.loc[
        valid
    ].reset_index(
        drop=True
    )

    return X, y, valid_df


# ============================================================
# MODELS
# ============================================================

def get_models(seed):

    models = {

        "random_forest":

            RandomForestRegressor(
                n_estimators=400,
                max_depth=8,
                min_samples_leaf=3,
                random_state=seed,
                n_jobs=-1,
            ),

        "gradient_boosting":

            GradientBoostingRegressor(
                n_estimators=300,
                learning_rate=0.03,
                max_depth=3,
                min_samples_leaf=3,
                loss="huber",
                random_state=seed,
            ),

        "hist_gradient_boosting":

            HistGradientBoostingRegressor(
                max_iter=300,
                learning_rate=0.05,
                max_leaf_nodes=15,
                min_samples_leaf=10,
                l2_regularization=1.0,
                random_state=seed,
            ),
    }

    return models


# ============================================================
# EVALUATE MODEL
# ============================================================

def evaluate_model(
    model,
    X_train,
    y_train_log,
    X_test,
    y_test_log,
    y_test,
):

    pipeline = Pipeline(
        steps=[

            (
                "imputer",

                SimpleImputer(
                    strategy="median"
                ),
            ),

            (
                "scaler",

                StandardScaler(
                    with_mean=False
                ),
            ),

            (
                "model",

                model,
            ),
        ]
    )

    # --------------------------------------------------------
    # Train
    # --------------------------------------------------------

    pipeline.fit(
        X_train,
        y_train_log,
    )

    # --------------------------------------------------------
    # Predict
    # --------------------------------------------------------

    prediction_log = pipeline.predict(
        X_test
    )

    # --------------------------------------------------------
    # Convert log prediction back
    # --------------------------------------------------------

    prediction = np.expm1(
        prediction_log
    )

    prediction = np.maximum(
        prediction,
        0,
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

    return (
        pipeline,
        prediction,
        mae,
        rmse,
        r2,
    )


# ============================================================
# PRINT TEST PREDICTIONS
# ============================================================

def print_test_predictions(
    valid_df,
    test_indices,
    y_test,
    prediction,
    model_name,
    scenario_name,
    limit=20,
):

    print()
    print("=" * 180)

    print(
        f"TOP TEST ERRORS | "
        f"{scenario_name} | "
        f"{model_name}"
    )

    print("=" * 180)

    # --------------------------------------------------------
    # Build result
    # --------------------------------------------------------

    result_df = valid_df.iloc[
        test_indices
    ].copy()

    result_df[
        "actual_paid_loss"
    ] = y_test.values

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
    ] = (
        result_df[
            "absolute_error"
        ]
        /
        result_df[
            "actual_paid_loss"
        ].replace(
            0,
            np.nan,
        )
    ) * 100

    result_df[
        "prediction_direction"
    ] = np.where(

        result_df[
            "predicted_paid_loss"
        ]
        <
        result_df[
            "actual_paid_loss"
        ],

        "UNDER",

        np.where(

            result_df[
                "predicted_paid_loss"
            ]
            >
            result_df[
                "actual_paid_loss"
            ],

            "OVER",

            "EXACT",
        ),
    )

    # --------------------------------------------------------
    # Sort by biggest absolute error
    # --------------------------------------------------------

    result_df = result_df.sort_values(
        "absolute_error",
        ascending=False,
    )

    # --------------------------------------------------------
    # Columns we want to see
    # --------------------------------------------------------

    columns = [

        "claim_key",

        "actual_paid_loss",

        "predicted_paid_loss",

        "absolute_error",

        "error_percent",

        "prediction_direction",

        "province_codes",

        "city_count",

        "coverage_codes",

        "damage_type_codes",

        "financial_damage_type_codes",

        "event_type_codes",

        "occupation_group_codes",

        "structure_codes",

        "risk_density_codes",

        "ownership_codes",

        "property_codes",

        "premium_min",

        "premium_max",

        "item_sum_insured_min",

        "item_sum_insured_max",

        "total_sum_insured_min",

        "total_sum_insured_max",

        "estimate_amount_min",

        "estimate_amount_max",

        "voucher_count",

        "insured_item_count",
    ]

    columns = [

        col
        for col in columns
        if col in result_df.columns

    ]

    display_df = result_df[
        columns
    ].head(
        limit
    ).copy()

    # --------------------------------------------------------
    # Format money
    # --------------------------------------------------------

    money_columns = [

        "actual_paid_loss",

        "predicted_paid_loss",

        "absolute_error",

        "premium_min",

        "premium_max",

        "item_sum_insured_min",

        "item_sum_insured_max",

        "total_sum_insured_min",

        "total_sum_insured_max",

        "estimate_amount_min",

        "estimate_amount_max",
    ]

    for col in money_columns:

        if col in display_df.columns:

            display_df[col] = (
                display_df[col]
                .apply(
                    lambda x:
                    f"{x:,.0f}"
                    if pd.notna(x)
                    else "-"
                )
            )

    # --------------------------------------------------------
    # Format percentage
    # --------------------------------------------------------

    if "error_percent" in display_df.columns:

        display_df[
            "error_percent"
        ] = (
            display_df[
                "error_percent"
            ]
            .apply(
                lambda x:
                f"{x:.1f}%"
                if pd.notna(x)
                else "-"
            )
        )

    # --------------------------------------------------------
    # Print
    # --------------------------------------------------------

    print(
        display_df.to_string(
            index=False
        )
    )

    print("=" * 180)


# ============================================================
# RUN SCENARIO
# ============================================================

def run_scenario(
    df,
    use_estimate,
    seed=42,
):

    scenario_name = (

        "with_estimate"

        if use_estimate

        else "without_estimate"
    )

    print()
    print("=" * 100)

    print(
        f"SCENARIO: {scenario_name}"
    )

    print("=" * 100)

    # --------------------------------------------------------
    # Features
    # --------------------------------------------------------

    (
        X,
        y,
        valid_df,
    ) = build_feature_matrix(
        df,
        use_estimate=use_estimate,
    )

    print(
        f"Rows: {len(X)}"
    )

    print(
        f"Features: {X.shape[1]}"
    )

    # --------------------------------------------------------
    # Log target
    # --------------------------------------------------------

    y_log = np.log1p(
        y
    )

    # --------------------------------------------------------
    # RANDOM 80/20 SPLIT
    #
    # IMPORTANT:
    # claim_year is NOT used.
    # All years are mixed.
    # --------------------------------------------------------

    (
        X_train,
        X_test,

        y_train_log,
        y_test_log,

        y_train,
        y_test,

        train_indices,
        test_indices,

    ) = train_test_split(

        X,

        y_log,

        y,

        np.arange(
            len(X)
        ),

        test_size=0.20,

        random_state=seed,

        shuffle=True,
    )

    print(
        f"Train rows: {len(X_train)}"
    )

    print(
        f"Test rows: {len(X_test)}"
    )

    # --------------------------------------------------------
    # Models
    # --------------------------------------------------------

    models = get_models(
        seed
    )

    scenario_results = []

    # --------------------------------------------------------
    # Train every model
    # --------------------------------------------------------

    for (
        model_name,
        model
    ) in models.items():

        print()
        print("-" * 80)

        print(
            f"Training: {model_name}"
        )

        print("-" * 80)

        (
            pipeline,
            prediction,
            mae,
            rmse,
            r2,
        ) = evaluate_model(

            model,

            X_train,

            y_train_log,

            X_test,

            y_test_log,

            y_test,
        )

        # ----------------------------------------------------
        # Metrics
        # ----------------------------------------------------

        print()
        print(
            "TEST RESULTS"
        )

        print(
            f"MAE  : {mae:,.2f}"
        )

        print(
            f"RMSE : {rmse:,.2f}"
        )

        print(
            f"R2   : {r2:.4f}"
        )

        # ----------------------------------------------------
        # Print detailed test predictions
        # ----------------------------------------------------

        print_test_predictions(

            valid_df=valid_df,

            test_indices=test_indices,

            y_test=y_test,

            prediction=prediction,

            model_name=model_name,

            scenario_name=scenario_name,

            limit=20,
        )

        # ----------------------------------------------------
        # Save model
        # ----------------------------------------------------

        model_path = (

            MODEL_DIR

            /
            (
                f"damage_model_"
                f"{scenario_name}_"
                f"{model_name}.joblib"
            )
        )

        bundle = {

            "model": pipeline,

            "features": list(
                X.columns
            ),

            "dataset_version":
                DATASET_VERSION,

            "scenario":
                scenario_name,

            "model_name":
                model_name,

            "target":
                "paid_loss",

            "target_transform":
                "log1p",

            "split":
                "random_80_20",

            "random_state":
                seed,
        }

        joblib.dump(
            bundle,
            model_path,
        )

        print()
        print(
            f"Model saved: {model_path}"
        )

        # ----------------------------------------------------
        # Save complete Test predictions
        # ----------------------------------------------------

        result_df = valid_df.iloc[
            test_indices
        ].copy()

        result_df[
            "actual_paid_loss"
        ] = y_test.values

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
        ] = (
            result_df[
                "absolute_error"
            ]
            /
            result_df[
                "actual_paid_loss"
            ].replace(
                0,
                np.nan,
            )
        ) * 100

        result_df[
            "prediction_direction"
        ] = np.where(

            result_df[
                "predicted_paid_loss"
            ]
            <
            result_df[
                "actual_paid_loss"
            ],

            "UNDER",

            np.where(

                result_df[
                    "predicted_paid_loss"
                ]
                >
                result_df[
                    "actual_paid_loss"
                ],

                "OVER",

                "EXACT",
            ),
        )

        prediction_path = (

            MODEL_DIR

            /
            (
                f"test_predictions_"
                f"{scenario_name}_"
                f"{model_name}.csv"
            )
        )

        result_df.to_csv(
            prediction_path,
            index=False,
        )

        print(
            f"Predictions saved: "
            f"{prediction_path}"
        )

        # ----------------------------------------------------
        # Save results
        # ----------------------------------------------------

        scenario_results.append(

            {
                "scenario":
                    scenario_name,

                "model":
                    model_name,

                "features":
                    X.shape[1],

                "train_rows":
                    len(X_train),

                "test_rows":
                    len(X_test),

                "mae":
                    mae,

                "rmse":
                    rmse,

                "r2":
                    r2,
            }
        )

    return scenario_results


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 100)

    print(
        "DAMAGE LOSS MODEL TRAINING"
    )

    print("=" * 100)

    # --------------------------------------------------------
    # Load
    # --------------------------------------------------------

    df = load_dataset()

    print(
        f"Claim rows loaded: {len(df)}"
    )

    all_results = []

    # --------------------------------------------------------
    # WITHOUT ESTIMATE
    # --------------------------------------------------------

    results_without_estimate = (
        run_scenario(
            df,
            use_estimate=False,
        )
    )

    all_results.extend(
        results_without_estimate
    )

    # --------------------------------------------------------
    # WITH ESTIMATE
    # --------------------------------------------------------

    results_with_estimate = (
        run_scenario(
            df,
            use_estimate=True,
        )
    )

    all_results.extend(
        results_with_estimate
    )

    # ========================================================
    # FINAL COMPARISON
    # ========================================================

    print()
    print("=" * 110)

    print(
        "FINAL MODEL COMPARISON"
    )

    print("=" * 110)

    print(
        f"{'Scenario':20} "
        f"{'Model':25} "
        f"{'MAE':15} "
        f"{'RMSE':15} "
        f"{'R2':10}"
    )

    print(
        "-" * 110
    )

    for result in all_results:

        print(

            f"{result['scenario']:20} "

            f"{result['model']:25} "

            f"{result['mae']:15,.0f} "

            f"{result['rmse']:15,.0f} "

            f"{result['r2']:10.4f}"
        )

    # ========================================================
    # SAVE COMPARISON
    # ========================================================

    results_df = pd.DataFrame(
        all_results
    )

    results_path = (
        MODEL_DIR
        /
        "model_comparison.csv"
    )

    results_df.to_csv(
        results_path,
        index=False,
    )

    print()
    print(
        f"Comparison saved: "
        f"{results_path}"
    )

    # ========================================================
    # BEST MODELS
    # ========================================================

    print()
    print("=" * 110)

    print(
        "BEST MODELS"
    )

    print("=" * 110)

    best_mae = results_df.loc[
        results_df[
            "mae"
        ].idxmin()
    ]

    best_rmse = results_df.loc[
        results_df[
            "rmse"
        ].idxmin()
    ]

    best_r2 = results_df.loc[
        results_df[
            "r2"
        ].idxmax()
    ]

    print()

    print(
        "Best MAE:"
    )

    print(

        f"  {best_mae['scenario']} / "

        f"{best_mae['model']} = "

        f"{best_mae['mae']:,.2f}"
    )

    print()

    print(
        "Best RMSE:"
    )

    print(

        f"  {best_rmse['scenario']} / "

        f"{best_rmse['model']} = "

        f"{best_rmse['rmse']:,.2f}"
    )

    print()

    print(
        "Best R2:"
    )

    print(

        f"  {best_r2['scenario']} / "

        f"{best_r2['model']} = "

        f"{best_r2['r2']:.4f}"
    )

    print()

    print("=" * 110)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()