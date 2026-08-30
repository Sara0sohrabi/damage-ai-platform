import argparse
import json
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://damage:damage@postgres:5432/damage_ai"
)


# ============================================================
# Excel column -> PostgreSQL clean_damage_data column
# ============================================================

COLUMN_MAP = {
    "ProvinceName_Code": "province_code",
    "CityName_Code": "city_code",
    "Coverage_Code": "coverage_code",
    "FireHadeseKindTitle_Code": "event_type_code",
    "Moredbime_Code": "insured_item_type_code",
    "HadesePlace_Code": "loss_location_code",

    "کد شغل / فعالیت": "occupation_code",
    "کد گروه فعالیت": "occupation_group_code",

    "کد نوع خسارت": "damage_type_code",
    "کد نوع خسارت مالی": "financial_damage_type_code",

    "نوع سازه_Code": "structure_type_code",
    "تراکم ریسک_Code": "risk_density_code",
    "نوع مالکیت_Code": "ownership_type_code",
    "نوع ملک_Code": "property_type_code",

    "حق بیمه مورد": "premium",
    "سرمایه مورد": "item_sum_insured",
    "سرمایه کل": "total_sum_insured",

    "EstimateAmount": "estimate_amount",
    "PayAmount": "paid_loss",
}


CODE_COLUMNS = [
    "province_code",
    "city_code",
    "coverage_code",
    "event_type_code",
    "insured_item_type_code",
    "loss_location_code",
    "occupation_code",
    "occupation_group_code",
    "damage_type_code",
    "financial_damage_type_code",
    "structure_type_code",
    "risk_density_code",
    "ownership_type_code",
    "property_type_code",
]


NUMERIC_COLUMNS = [
    "premium",
    "item_sum_insured",
    "total_sum_insured",
    "estimate_amount",
    "paid_loss",
]


def clean_code(value):
    """Normalize code values such as 152.0 -> 152."""

    if pd.isna(value):
        return None

    value = str(value).strip()

    if value.lower() in {"", "nan", "none"}:
        return None

    try:
        number = float(value)

        if number.is_integer():
            return str(int(number))

    except (ValueError, TypeError):
        pass

    return value


def clean_numeric(value):
    """Convert numeric Excel values safely."""

    if pd.isna(value):
        return None

    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def main():

    parser = argparse.ArgumentParser(
        description="Import source Excel into raw and clean damage data"
    )

    parser.add_argument(
        "--input",
        required=True
    )

    parser.add_argument(
        "--dataset-version",
        default="damagefire_001"
    )

    parser.add_argument(
        "--sheet",
        default="Sheet1"
    )

    parser.add_argument(
        "--cleaning-version",
        default="clean_v2"
    )

    args = parser.parse_args()

    excel_path = Path(args.input)

    if not excel_path.exists():
        raise FileNotFoundError(
            f"Excel file not found: {excel_path}"
        )

    print("=" * 80)
    print("IMPORT / CLEAN DATA")
    print("=" * 80)

    print(f"Input: {excel_path}")
    print(f"Sheet: {args.sheet}")
    print(f"Dataset version: {args.dataset_version}")

    # ============================================================
    # Read Excel
    # ============================================================

    raw_df = pd.read_excel(
        excel_path,
        sheet_name=args.sheet
    )

    print(f"Excel rows: {len(raw_df):,}")
    print(f"Excel columns: {len(raw_df.columns):,}")

    # ============================================================
    # Validate source columns
    # ============================================================

    missing_source_columns = [
        source_col
        for source_col in COLUMN_MAP
        if source_col not in raw_df.columns
    ]

    if missing_source_columns:
        raise RuntimeError(
            "Required Excel columns are missing:\n"
            + "\n".join(
                f"- {col}"
                for col in missing_source_columns
            )
        )

    # ============================================================
    # Preserve complete raw data
    # ============================================================

    raw_records = raw_df.copy()

    # ============================================================
    # Build clean dataset
    # ============================================================

    clean_df = (
        raw_df[list(COLUMN_MAP.keys())]
        .rename(columns=COLUMN_MAP)
        .copy()
    )

    # ============================================================
    # Normalize code fields
    # ============================================================

    for col in CODE_COLUMNS:
        clean_df[col] = clean_df[col].apply(clean_code)

    # ============================================================
    # Normalize numeric fields
    # ============================================================

    for col in NUMERIC_COLUMNS:
        clean_df[col] = clean_df[col].apply(clean_numeric)

    # ============================================================
    # Target quality
    # ============================================================

    missing_paid = int(
        clean_df["paid_loss"].isna().sum()
    )

    zero_paid = int(
        (clean_df["paid_loss"].fillna(0) == 0).sum()
    )

    negative_paid = int(
        (
            clean_df["paid_loss"].notna()
            & (clean_df["paid_loss"] < 0)
        ).sum()
    )

    print()
    print("TARGET QUALITY")
    print("-" * 80)
    print(f"Missing paid_loss : {missing_paid:,}")
    print(f"Zero paid_loss    : {zero_paid:,}")
    print(f"Negative paid_loss: {negative_paid:,}")

    # ============================================================
    # Remove invalid target rows from CLEAN data only.
    # Raw data remains untouched.
    # ============================================================

    clean_df = clean_df[
        clean_df["paid_loss"].notna()
        & (clean_df["paid_loss"] >= 0)
    ].copy()

    # ============================================================
    # Business validation
    # We report violations instead of destroying raw data.
    # ============================================================

    item_cap_violation = (
        clean_df["item_sum_insured"].notna()
        & (
            clean_df["paid_loss"]
            > clean_df["item_sum_insured"]
        )
    )

    total_cap_violation = (
        clean_df["total_sum_insured"].notna()
        & (
            clean_df["paid_loss"]
            > clean_df["total_sum_insured"]
        )
    )

    cap_violations = int(
        (
            item_cap_violation
            | total_cap_violation
        ).sum()
    )

    print()
    print("BUSINESS VALIDATION")
    print("-" * 80)
    print(
        "Paid loss above available insured capital:",
        cap_violations
    )

    # ============================================================
    # PostgreSQL
    # ============================================================

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True
    )

    # ============================================================
    # Safe rerun: delete current dataset version
    # ============================================================

    with engine.begin() as conn:

        conn.execute(
            text("""
                DELETE FROM raw_damage_data
                WHERE dataset_version = :v
            """),
            {
                "v": args.dataset_version
            }
        )

        conn.execute(
            text("""
                DELETE FROM clean_damage_data
                WHERE dataset_version = :v
            """),
            {
                "v": args.dataset_version
            }
        )

        conn.execute(
            text("""
                DELETE FROM dataset_versions
                WHERE dataset_version = :v
            """),
            {
                "v": args.dataset_version
            }
        )

    # ============================================================
    # Store ALL source rows in raw_damage_data
    # ============================================================

    print()
    print("Writing raw_damage_data...")

    raw_insert_sql = text("""
        INSERT INTO raw_damage_data (
            dataset_version,
            source_file,
            source_row,
            external_identifier,
            raw_data
        )
        VALUES (
            :dataset_version,
            :source_file,
            :source_row,
            :external_identifier,
            CAST(:raw_data AS json)
        )
    """)

    raw_inserted = 0

    with engine.begin() as conn:

        for excel_index, row in raw_records.iterrows():

            record = row.where(
                pd.notna(row),
                None
            ).to_dict()

            external_identifier = None

            if "FireHvID" in record:
                value = record.get("FireHvID")

                if value is not None:
                    external_identifier = str(value)

            conn.execute(
                raw_insert_sql,
                {
                    "dataset_version": args.dataset_version,
                    "source_file": str(excel_path),
                    "source_row": int(excel_index + 2),
                    "external_identifier": external_identifier,
                    "raw_data": json.dumps(
                        record,
                        ensure_ascii=False,
                        default=str
                    ),
                }
            )

            raw_inserted += 1

    # ============================================================
    # Prepare clean table
    # ============================================================

    clean_df.insert(
        0,
        "dataset_version",
        args.dataset_version
    )

    clean_columns = [
        "dataset_version",
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
        "premium",
        "item_sum_insured",
        "total_sum_insured",
        "estimate_amount",
        "paid_loss",
    ]

    clean_df = clean_df[
        clean_columns
    ]

    # ============================================================
    # Store clean data
    # ============================================================

    print("Writing clean_damage_data...")

    clean_df.to_sql(
        "clean_damage_data",
        engine,
        if_exists="append",
        index=False,
        method="multi",
        chunksize=500
    )

    # ============================================================
    # Dataset version registry
    # ============================================================

    with engine.begin() as conn:

        conn.execute(
            text("""
                INSERT INTO dataset_versions (
                    dataset_version,
                    source_file,
                    row_count,
                    mapping_version,
                    cleaning_version,
                    status
                )
                VALUES (
                    :v,
                    :f,
                    :n,
                    'mapping_001',
                    :cv,
                    'ready'
                )
            """),
            {
                "v": args.dataset_version,
                "f": str(excel_path),
                "n": len(clean_df),
                "cv": args.cleaning_version,
            }
        )

    engine.dispose()

    print()
    print("=" * 80)
    print("IMPORT COMPLETED")
    print("=" * 80)
    print(f"Raw rows stored  : {raw_inserted:,}")
    print(f"Clean rows stored: {len(clean_df):,}")
    print(f"Dataset version  : {args.dataset_version}")
    print("=" * 80)


if __name__ == "__main__":
    main()