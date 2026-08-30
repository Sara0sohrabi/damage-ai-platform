import json
import os

import pandas as pd
from sqlalchemy import create_engine, text


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://damage:damage@postgres:5432/damage_ai",
)

DATASET_VERSION = "damagefire_001"


def clean_str(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if value.lower() in {"", "nan", "none"}:
        return None

    return value


def clean_num(value):
    if pd.isna(value):
        return None

    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def unique_values(series):
    values = set()

    for value in series:
        value = clean_str(value)

        if value is not None:
            values.add(value)

    return sorted(values)


def numeric_values(series):
    values = set()

    for value in series:
        value = clean_num(value)

        if value is not None:
            values.add(value)

    return sorted(values)


def main():

    print("=" * 80)
    print("BUILD CLAIM TRAINING DATA")
    print("=" * 80)

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
    )

    # =========================================================
    # 1. Read Raw Data
    # =========================================================

    with engine.connect() as conn:

        rows = conn.execute(
            text(
                """
                SELECT
                    source_row,
                    raw_data
                FROM raw_damage_data
                WHERE dataset_version = :v
                ORDER BY source_row
                """
            ),
            {"v": DATASET_VERSION},
        ).mappings().all()

    print(f"Raw rows loaded: {len(rows):,}")

    if not rows:
        raise RuntimeError(
            f"No raw rows found for dataset {DATASET_VERSION}"
        )

    records = []

    for row in rows:

        records.append(
            {
                "source_row": row["source_row"],
                **row["raw_data"],
            }
        )

    df = pd.DataFrame(records)

    # =========================================================
    # 2. Claim Key
    # =========================================================

    df["claim_year"] = (
        df["claim_سال تشكيل پرونده"]
        .apply(clean_str)
    )

    df["claim_number"] = (
        df["claim_شماره پرونده"]
        .apply(clean_str)
    )

    valid_claim_mask = (
        df["claim_year"].notna()
        & df["claim_number"].notna()
    )

    claim_df = df.loc[
        valid_claim_mask
    ].copy()

    claim_df["claim_key"] = (
        claim_df["claim_year"]
        + "-"
        + claim_df["claim_number"]
    )

    print(
        f"Rows with Claim Key: "
        f"{len(claim_df):,}"
    )

    print(
        f"Unique Claims: "
        f"{claim_df['claim_key'].nunique():,}"
    )

    # =========================================================
    # 3. Payment-level Target
    #
    # IMPORTANT:
    # paid_loss comes ONLY from unique payments.
    # No insurance capital / premium is added to target.
    # =========================================================

    with engine.connect() as conn:

        payment_rows = conn.execute(
            text(
                """
                SELECT
                    claim_key,
                    COUNT(*) AS voucher_count,
                    SUM(pay_amount) AS paid_loss
                FROM claim_payment_data
                WHERE dataset_version = :v
                  AND claim_key IS NOT NULL
                GROUP BY claim_key
                """
            ),
            {"v": DATASET_VERSION},
        ).mappings().all()

    payments = pd.DataFrame(payment_rows)

    if payments.empty:
        raise RuntimeError(
            "No claim payment data found."
        )

    # =========================================================
    # 4. Build Claim-level Dataset
    # =========================================================

    output_rows = []

    for claim_key, group in claim_df.groupby(
        "claim_key",
        sort=False,
    ):

        payment = payments[
            payments["claim_key"] == claim_key
        ]

        if payment.empty:
            continue

        payment_row = payment.iloc[0]

        # -----------------------------------------------------
        # Financial values:
        # DO NOT SUM them.
        # Preserve the distinct source values.
        # -----------------------------------------------------

        premium_values = numeric_values(
            group["Prm"]
        )

        item_sum_values = numeric_values(
            group["سرمایه مورد"]
        )

        total_sum_values = numeric_values(
            group["سرمایه کل"]
        )

        estimate_values = numeric_values(
            group["EstimateAmount"]
        )

        # -----------------------------------------------------
        # Claim record
        # -----------------------------------------------------

        row = {

            "dataset_version":
                DATASET_VERSION,

            "claim_key":
                claim_key,

            "claim_year":
                clean_str(
                    group["claim_year"].iloc[0]
                ),

            "claim_number":
                clean_str(
                    group["claim_number"].iloc[0]
                ),

            # -------------------------------------------------
            # Policy information
            # -------------------------------------------------

            "policy_id_count":
                group["PolicyID"]
                .apply(clean_str)
                .dropna()
                .nunique(),

            # -------------------------------------------------
            # Payment information
            # -------------------------------------------------

            "voucher_count":
                int(
                    payment_row["voucher_count"]
                ),

            # -------------------------------------------------
            # Feature counts
            # -------------------------------------------------

            "coverage_count":
                group["Coverage_Code"]
                .apply(clean_str)
                .dropna()
                .nunique(),

            "occupation_count":
                group["کد شغل / فعالیت"]
                .apply(clean_str)
                .dropna()
                .nunique(),

            "insured_item_count":
                group["مورد بیمه_Code"]
                .apply(clean_str)
                .dropna()
                .nunique(),

            "location_count":
                group["HadesePlace_Code"]
                .apply(clean_str)
                .dropna()
                .nunique(),

            "structure_count":
                group["نوع سازه_Code"]
                .apply(clean_str)
                .dropna()
                .nunique(),

            "province_count":
                group["ProvinceName_Code"]
                .apply(clean_str)
                .dropna()
                .nunique(),

            "city_count":
                group["CityName_Code"]
                .apply(clean_str)
                .dropna()
                .nunique(),

            "event_type_count":
                group["FireHadeseKindTitle_Code"]
                .apply(clean_str)
                .dropna()
                .nunique(),

            # -------------------------------------------------
            # Code collections
            # -------------------------------------------------

            "province_codes":
                json.dumps(
                    unique_values(
                        group["ProvinceName_Code"]
                    ),
                    ensure_ascii=False,
                ),

            "city_codes":
                json.dumps(
                    unique_values(
                        group["CityName_Code"]
                    ),
                    ensure_ascii=False,
                ),

            "event_type_codes":
                json.dumps(
                    unique_values(
                        group[
                            "FireHadeseKindTitle_Code"
                        ]
                    ),
                    ensure_ascii=False,
                ),

            "coverage_codes":
                json.dumps(
                    unique_values(
                        group["Coverage_Code"]
                    ),
                    ensure_ascii=False,
                ),

            "occupation_codes":
                json.dumps(
                    unique_values(
                        group["کد شغل / فعالیت"]
                    ),
                    ensure_ascii=False,
                ),

            "occupation_group_codes":
                json.dumps(
                    unique_values(
                        group["کد گروه فعالیت"]
                    ),
                    ensure_ascii=False,
                ),

            "insured_item_codes":
                json.dumps(
                    unique_values(
                        group["مورد بیمه_Code"]
                    ),
                    ensure_ascii=False,
                ),

            "loss_location_codes":
                json.dumps(
                    unique_values(
                        group["HadesePlace_Code"]
                    ),
                    ensure_ascii=False,
                ),

            "damage_type_codes":
                json.dumps(
                    unique_values(
                        group["کد نوع خسارت"]
                    ),
                    ensure_ascii=False,
                ),

            "financial_damage_type_codes":
                json.dumps(
                    unique_values(
                        group["کد نوع خسارت مالی"]
                    ),
                    ensure_ascii=False,
                ),

            "structure_codes":
                json.dumps(
                    unique_values(
                        group["نوع سازه_Code"]
                    ),
                    ensure_ascii=False,
                ),

            "risk_density_codes":
                json.dumps(
                    unique_values(
                        group["تراکم ریسک_Code"]
                    ),
                    ensure_ascii=False,
                ),

            "ownership_codes":
                json.dumps(
                    unique_values(
                        group["نوع مالکیت_Code"]
                    ),
                    ensure_ascii=False,
                ),

            "property_codes":
                json.dumps(
                    unique_values(
                        group["نوع ملک_Code"]
                    ),
                    ensure_ascii=False,
                ),

            # -------------------------------------------------
            # Financial source values
            # No aggregation
            # -------------------------------------------------

            "premium_values":
                json.dumps(
                    premium_values
                ),

            "item_sum_insured_values":
                json.dumps(
                    item_sum_values
                ),

            "total_sum_insured_values":
                json.dumps(
                    total_sum_values
                ),

            "estimate_amount_values":
                json.dumps(
                    estimate_values
                ),

            # -------------------------------------------------
            # TARGET
            #
            # ONLY:
            # sum of unique payment amounts for this Claim
            # -------------------------------------------------

            "paid_loss":
                float(
                    payment_row["paid_loss"]
                ),
        }

        output_rows.append(row)

    result_df = pd.DataFrame(output_rows)

    print(
        f"Claim-level rows created: "
        f"{len(result_df):,}"
    )

    if result_df.empty:
        raise RuntimeError(
            "No claim-level rows were created."
        )

    # =========================================================
    # 5. Replace Dataset Version
    # =========================================================

    with engine.begin() as conn:

        conn.execute(
            text(
                """
                DELETE FROM claim_training_data
                WHERE dataset_version = :v
                """
            ),
            {"v": DATASET_VERSION},
        )

    # =========================================================
    # 6. Insert
    # =========================================================

    insert_sql = text(
        """
        INSERT INTO claim_training_data (
            dataset_version,
            claim_key,
            claim_year,
            claim_number,

            policy_id_count,
            voucher_count,

            coverage_count,
            occupation_count,
            insured_item_count,
            location_count,
            structure_count,

            province_count,
            city_count,
            event_type_count,

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

            premium_values,
            item_sum_insured_values,
            total_sum_insured_values,
            estimate_amount_values,

            paid_loss
        )
        VALUES (
            :dataset_version,
            :claim_key,
            :claim_year,
            :claim_number,

            :policy_id_count,
            :voucher_count,

            :coverage_count,
            :occupation_count,
            :insured_item_count,
            :location_count,
            :structure_count,

            :province_count,
            :city_count,
            :event_type_count,

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

            CAST(:premium_values AS jsonb),
            CAST(:item_sum_insured_values AS jsonb),
            CAST(:total_sum_insured_values AS jsonb),
            CAST(:estimate_amount_values AS jsonb),

            :paid_loss
        )
        """
    )

    with engine.begin() as conn:

        for _, row in result_df.iterrows():

            conn.execute(
                insert_sql,
                row.to_dict(),
            )

    # =========================================================
    # 7. Final Verification
    # =========================================================

    with engine.connect() as conn:

        result = conn.execute(
            text(
                """
                SELECT
                    COUNT(*) AS claims,
                    COUNT(DISTINCT claim_key)
                        AS unique_claims,
                    COUNT(*) FILTER (
                        WHERE paid_loss IS NULL
                    ) AS missing_target,
                    MIN(paid_loss)
                        AS min_paid_loss,
                    MAX(paid_loss)
                        AS max_paid_loss,
                    AVG(paid_loss)
                        AS avg_paid_loss
                FROM claim_training_data
                WHERE dataset_version = :v
                """
            ),
            {"v": DATASET_VERSION},
        ).mappings().one()

    engine.dispose()

    print("=" * 80)
    print("CLAIM TRAINING DATA BUILD COMPLETED")
    print("=" * 80)

    print(
        f"Claims             : {result['claims']}"
    )

    print(
        f"Unique claims      : {result['unique_claims']}"
    )

    print(
        f"Missing target     : {result['missing_target']}"
    )

    print(
        f"Min paid loss      : {result['min_paid_loss']}"
    )

    print(
        f"Max paid loss      : {result['max_paid_loss']}"
    )

    print(
        f"Average paid loss  : {result['avg_paid_loss']}"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()