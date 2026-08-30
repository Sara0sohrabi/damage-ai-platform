# services/ml_training/scripts/train_model.py

import os
import pandas as pd
from sqlalchemy import create_engine, text


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://damage:damage@postgres:5432/damage_ai"
)

DATASET_VERSION = "damagefire_001"


FEATURE_COLUMNS = [
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
    "premium",
    "item_sum_insured",
    "total_sum_insured",
]

TARGET_COLUMN = "estimate_amount"


def main():

    print("=" * 80)
    print("ML TRAINING - POSTGRESQL SOURCE")
    print("=" * 80)

    engine = create_engine(DATABASE_URL)

    # --------------------------------------------------------
    # Read data ONLY from PostgreSQL
    # --------------------------------------------------------

    query = text("""
        SELECT
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
            premium,
            item_sum_insured,
            total_sum_insured,
            estimate_amount,
            paid_loss
        FROM clean_damage_data
        WHERE dataset_version = :dataset_version
    """)

    with engine.connect() as connection:

        df = pd.read_sql(
            query,
            connection,
            params={
                "dataset_version": DATASET_VERSION
            }
        )

    print(f"Rows loaded from PostgreSQL: {len(df)}")

    if df.empty:
        raise RuntimeError(
            "No data found in PostgreSQL for "
            f"dataset_version={DATASET_VERSION}"
        )

    # --------------------------------------------------------
    # Check required columns
    # --------------------------------------------------------

    required_columns = (
        FEATURE_COLUMNS
        + [
            TARGET_COLUMN,
            "paid_loss",
        ]
    )

    missing = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing:

        raise RuntimeError(
            "Missing columns in PostgreSQL: "
            + ", ".join(missing)
        )

    # --------------------------------------------------------
    # IMPORTANT
    #
    # paid_loss is NOT a model feature.
    #
    # It is only retained for later evaluation/analysis.
    # --------------------------------------------------------

    X = df[FEATURE_COLUMNS].copy()

    y = df[TARGET_COLUMN].copy()

    paid_loss = df["paid_loss"].copy()

    # --------------------------------------------------------
    # Dataset integrity
    # --------------------------------------------------------

    print("\nDATASET CHECK")

    print(f"Rows             : {len(df)}")
    print(f"Features         : {len(FEATURE_COLUMNS)}")
    print(f"Target           : {TARGET_COLUMN}")
    print(f"Paid loss column : available for evaluation")

    print("\nNO AGGREGATION.")

    print(
        "Each PostgreSQL row represents "
        "one independent claim."
    )

    # --------------------------------------------------------
    # Continue with train/test split
    # --------------------------------------------------------

    # اینجا مرحله train_test_split
    # و مدل‌ها قرار می‌گیرد.


if __name__ == "__main__":
    main()