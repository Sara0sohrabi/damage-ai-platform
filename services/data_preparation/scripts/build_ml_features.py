import json
import os

import pandas as pd
from sqlalchemy import create_engine, text


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://damage:damage@postgres:5432/damage_ai",
)

DATASET_VERSION = "damagefire_001"


JSON_COLUMNS = [
    "province_codes",
    "city_codes",
    "event_type_codes",
    "coverage_codes",
    "occupation_codes",
    "occupation_group_codes",
    "insured_item_codes",
    "loss_location_codes",
    "damage_type_codes",
    "financial_damage_type_codes",
    "structure_codes",
    "risk_density_codes",
    "ownership_codes",
    "property_codes",
]


NUMERIC_ARRAY_COLUMNS = [
    "premium_values",
    "item_sum_insured_values",
    "total_sum_insured_values",
    "estimate_amount_values",
]


def parse_json_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    try:
        result = json.loads(value)

        if isinstance(result, list):
            return result

    except (TypeError, ValueError, json.JSONDecodeError):
        pass

    return []


def numeric_list(value):
    values = parse_json_list(value)
    result = []

    for item in values:
        try:
            number = float(item)

            if pd.notna(number):
                result.append(number)

        except (TypeError, ValueError):
            continue

    return sorted(set(result))


def code_list(value):
    values = parse_json_list(value)

    result = []

    for item in values:
        if item is None:
            continue

        value = str(item).strip()

        if value and value.lower() not in {
            "nan",
            "none",
            "",
        }:
            result.append(value)

    return sorted(set(result))


def main():

    print("=" * 80)
    print("BUILD ML FEATURES")
    print("=" * 80)

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
    )

    # ---------------------------------------------------------
    # Read Claim-level dataset
    # ---------------------------------------------------------

    with engine.connect() as conn:

        rows = conn.execute(
            text(
                """
                SELECT *
                FROM claim_training_data
                WHERE dataset_version = :v
                ORDER BY id
                """
            ),
            {
                "v": DATASET_VERSION,
            },
        ).mappings().all()

    print(
        f"Claim rows loaded: {len(rows):,}"
    )

    if not rows:
        raise RuntimeError(
            f"No claim_training_data found for "
            f"{DATASET_VERSION}"
        )

    df = pd.DataFrame(rows)

    # ---------------------------------------------------------
    # Parse JSON code collections
    # ---------------------------------------------------------

    for column in JSON_COLUMNS:

        if column in df.columns:

            df[column] = df[column].apply(
                code_list
            )

        else:

            df[column] = [[] for _ in range(len(df))]

    # ---------------------------------------------------------
    # Parse financial arrays
    # ---------------------------------------------------------

    for column in NUMERIC_ARRAY_COLUMNS:

        if column in df.columns:

            df[column] = df[column].apply(
                numeric_list
            )

        else:

            df[column] = [[] for _ in range(len(df))]

    # ---------------------------------------------------------
    # Create feature dataframe
    # ---------------------------------------------------------

    out = pd.DataFrame()

    out["dataset_version"] = df[
        "dataset_version"
    ]

    out["claim_key"] = df[
        "claim_key"
    ]

    out["claim_year"] = df[
        "claim_year"
    ].astype("string")

    # Useful for time-aware validation.
    out["claim_year_numeric"] = pd.to_numeric(
        df["claim_year"],
        errors="coerce",
    )

    out["claim_number"] = df[
        "claim_number"
    ].astype("string")

    # ---------------------------------------------------------
    # Claim / payment counts
    # ---------------------------------------------------------

    count_columns = [
        "policy_id_count",
        "voucher_count",
        "province_count",
        "city_count",
        "event_type_count",
        "coverage_count",
        "occupation_count",
        "insured_item_count",
        "location_count",
        "structure_count",
    ]

    for column in count_columns:

        out[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    # ---------------------------------------------------------
    # Premium
    #
    # IMPORTANT:
    # We DO NOT sum premium.
    # ---------------------------------------------------------

    out["premium_count"] = df[
        "premium_values"
    ].apply(len)

    out["premium_min"] = df[
        "premium_values"
    ].apply(
        lambda x: min(x) if x else None
    )

    out["premium_max"] = df[
        "premium_values"
    ].apply(
        lambda x: max(x) if x else None
    )

    # ---------------------------------------------------------
    # Item sum insured
    #
    # IMPORTANT:
    # We DO NOT sum this.
    # ---------------------------------------------------------

    out["item_sum_insured_count"] = df[
        "item_sum_insured_values"
    ].apply(len)

    out["item_sum_insured_min"] = df[
        "item_sum_insured_values"
    ].apply(
        lambda x: min(x) if x else None
    )

    out["item_sum_insured_max"] = df[
        "item_sum_insured_values"
    ].apply(
        lambda x: max(x) if x else None
    )

    # ---------------------------------------------------------
    # Total sum insured
    #
    # Keep range; do not sum.
    # ---------------------------------------------------------

    out["total_sum_insured_count"] = df[
        "total_sum_insured_values"
    ].apply(len)

    out["total_sum_insured_min"] = df[
        "total_sum_insured_values"
    ].apply(
        lambda x: min(x) if x else None
    )

    out["total_sum_insured_max"] = df[
        "total_sum_insured_values"
    ].apply(
        lambda x: max(x) if x else None
    )

    # ---------------------------------------------------------
    # Estimate
    #
    # Kept as optional features.
    # Whether they enter Production model will be decided later.
    # ---------------------------------------------------------

    out["estimate_amount_count"] = df[
        "estimate_amount_values"
    ].apply(len)

    out["estimate_amount_min"] = df[
        "estimate_amount_values"
    ].apply(
        lambda x: min(x) if x else None
    )

    out["estimate_amount_max"] = df[
        "estimate_amount_values"
    ].apply(
        lambda x: max(x) if x else None
    )

    # ---------------------------------------------------------
    # Unknown indicators
    # ---------------------------------------------------------

    out["has_unknown_structure"] = df[
        "structure_codes"
    ].apply(
        lambda x: "0" in x
    )

    out["has_unknown_risk_density"] = df[
        "risk_density_codes"
    ].apply(
        lambda x: "0" in x
    )

    out["has_unknown_ownership"] = df[
        "ownership_codes"
    ].apply(
        lambda x: "0" in x
    )

    out["has_unknown_property"] = df[
        "property_codes"
    ].apply(
        lambda x: "0" in x
    )

    # ---------------------------------------------------------
    # Preserve categorical code sets
    # ---------------------------------------------------------

    for column in JSON_COLUMNS:

        out[column] = df[column].apply(
            lambda x: json.dumps(
                x,
                ensure_ascii=False,
            )
        )

    # ---------------------------------------------------------
    # TARGET
    #
    # This is the ONLY loss amount used as target.
    # ---------------------------------------------------------

    out["paid_loss"] = pd.to_numeric(
        df["paid_loss"],
        errors="coerce",
    )

    out = out[
        out["paid_loss"].notna()
        & (out["paid_loss"] >= 0)
    ].copy()

    if out.empty:
        raise RuntimeError(
            "No valid ML rows after target validation."
        )

    # ---------------------------------------------------------
    # Safe rerun
    # ---------------------------------------------------------

    with engine.begin() as conn:

        conn.execute(
            text(
                """
                DELETE FROM claim_ml_features
                WHERE dataset_version = :v
                """
            ),
            {
                "v": DATASET_VERSION,
            },
        )

    # ---------------------------------------------------------
    # Insert SQL
    # ---------------------------------------------------------

    insert_sql = text(
        """
        INSERT INTO claim_ml_features (
            dataset_version,
            claim_key,
            claim_year,
            claim_year_numeric,
            claim_number,

            policy_id_count,
            voucher_count,

            province_count,
            city_count,
            event_type_count,
            coverage_count,
            occupation_count,
            insured_item_count,
            location_count,
            structure_count,

            premium_count,
            premium_min,
            premium_max,

            item_sum_insured_count,
            item_sum_insured_min,
            item_sum_insured_max,

            total_sum_insured_count,
            total_sum_insured_min,
            total_sum_insured_max,

            estimate_amount_count,
            estimate_amount_min,
            estimate_amount_max,

            has_unknown_structure,
            has_unknown_risk_density,
            has_unknown_ownership,
            has_unknown_property,

            province_codes,
            city_codes,
            event_type_codes,
            coverage_codes,
            occupation_codes,
            occupation_group_codes,
            insured_item_codes,
            loss_location_codes,
            damage_type_codes,
            financial_damage_type_codes,
            structure_codes,
            risk_density_codes,
            ownership_codes,
            property_codes,

            paid_loss
        )
        VALUES (
            :dataset_version,
            :claim_key,
            :claim_year,
            :claim_year_numeric,
            :claim_number,

            :policy_id_count,
            :voucher_count,

            :province_count,
            :city_count,
            :event_type_count,
            :coverage_count,
            :occupation_count,
            :insured_item_count,
            :location_count,
            :structure_count,

            :premium_count,
            :premium_min,
            :premium_max,

            :item_sum_insured_count,
            :item_sum_insured_min,
            :item_sum_insured_max,

            :total_sum_insured_count,
            :total_sum_insured_min,
            :total_sum_insured_max,

            :estimate_amount_count,
            :estimate_amount_min,
            :estimate_amount_max,

            :has_unknown_structure,
            :has_unknown_risk_density,
            :has_unknown_ownership,
            :has_unknown_property,

            CAST(:province_codes AS jsonb),
            CAST(:city_codes AS jsonb),
            CAST(:event_type_codes AS jsonb),
            CAST(:coverage_codes AS jsonb),
            CAST(:occupation_codes AS jsonb),
            CAST(:occupation_group_codes AS jsonb),
            CAST(:insured_item_codes AS jsonb),
            CAST(:loss_location_codes AS jsonb),
            CAST(:damage_type_codes AS jsonb),
            CAST(:financial_damage_type_codes AS jsonb),
            CAST(:structure_codes AS jsonb),
            CAST(:risk_density_codes AS jsonb),
            CAST(:ownership_codes AS jsonb),
            CAST(:property_codes AS jsonb),

            :paid_loss
        )
        """
    )

    # ---------------------------------------------------------
    # Insert
    # ---------------------------------------------------------

    rows_to_insert = (
        out.where(
            pd.notna(out),
            None,
        )
        .to_dict(orient="records")
    )

    with engine.begin() as conn:

        for row in rows_to_insert:

            conn.execute(
                insert_sql,
                row,
            )

    # ---------------------------------------------------------
    # Final verification
    # ---------------------------------------------------------

    with engine.connect() as conn:

        result = conn.execute(
            text(
                """
                SELECT
                    COUNT(*) AS rows,
                    COUNT(DISTINCT claim_key)
                        AS claims,
                    COUNT(*) FILTER (
                        WHERE paid_loss IS NULL
                    ) AS missing_target,
                    MIN(paid_loss)
                        AS min_loss,
                    MAX(paid_loss)
                        AS max_loss
                FROM claim_ml_features
                WHERE dataset_version = :v
                """
            ),
            {
                "v": DATASET_VERSION,
            },
        ).mappings().one()

    engine.dispose()

    print("=" * 80)
    print("ML FEATURE BUILD COMPLETED")
    print("=" * 80)

    print(
        f"Rows            : {result['rows']}"
    )

    print(
        f"Unique Claims   : {result['claims']}"
    )

    print(
        f"Missing Target  : {result['missing_target']}"
    )

    print(
        f"Min Paid Loss   : {result['min_loss']}"
    )

    print(
        f"Max Paid Loss   : {result['max_loss']}"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()