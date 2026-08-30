import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://damage:damage@postgres:5432/damage_ai"
)

DATASET_VERSION = "damagefire_001"


def main():
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True
    )

    with engine.begin() as conn:

        # ------------------------------------------------------
        # Safe rerun
        # ------------------------------------------------------
        conn.execute(
            text("""
                DELETE FROM claim_payment_data
                WHERE dataset_version = :v
            """),
            {"v": DATASET_VERSION},
        )

        # ------------------------------------------------------
        # Build unique payments
        # ------------------------------------------------------
        sql = text("""
            WITH source_rows AS (
                SELECT
                    raw_data->>'FireHvID' AS fire_hv_id,
                    raw_data->>'PayDate' AS pay_date,
                    raw_data->>'PayAmount' AS pay_amount,

                    raw_data->>'PolicyID' AS policy_id,

                    NULLIF(
                        raw_data->>'claim_سال تشكيل پرونده',
                        ''
                    ) AS claim_year,

                    NULLIF(
                        raw_data->>'claim_شماره پرونده',
                        ''
                    ) AS claim_number,

                    COUNT(*) OVER (
                        PARTITION BY
                            raw_data->>'FireHvID',
                            raw_data->>'PayDate',
                            raw_data->>'PayAmount'
                    ) AS raw_row_count

                FROM raw_damage_data

                WHERE dataset_version = :v

                  AND NULLIF(
                        raw_data->>'FireHvID',
                        ''
                  ) IS NOT NULL
            ),

            unique_payments AS (
                SELECT DISTINCT ON (
                    fire_hv_id,
                    pay_date,
                    pay_amount
                )
                    fire_hv_id,
                    pay_date,
                    pay_amount,
                    policy_id,
                    claim_year,
                    claim_number,
                    raw_row_count

                FROM source_rows

                ORDER BY
                    fire_hv_id,
                    pay_date,
                    pay_amount
            )

            INSERT INTO claim_payment_data (
                dataset_version,
                payment_key,
                fire_hv_id,
                policy_id,
                claim_key,
                claim_year,
                claim_number,
                pay_date,
                pay_amount,
                raw_row_count
            )

            SELECT
                :v AS dataset_version,

                CONCAT(
                    fire_hv_id,
                    '|',
                    COALESCE(pay_date, ''),
                    '|',
                    COALESCE(pay_amount, '')
                ) AS payment_key,

                fire_hv_id,

                policy_id,

                CASE
                    WHEN claim_year IS NOT NULL
                     AND claim_number IS NOT NULL
                    THEN
                        claim_year || '-' || claim_number
                    ELSE NULL
                END AS claim_key,

                claim_year,
                claim_number,
                pay_date,

                CASE
                    WHEN pay_amount ~ '^[0-9]+(\\.[0-9]+)?$'
                    THEN pay_amount::numeric
                    ELSE NULL
                END AS pay_amount,

                raw_row_count

            FROM unique_payments
        """)

        conn.execute(
            sql,
            {"v": DATASET_VERSION}
        )

        # ------------------------------------------------------
        # Result
        # ------------------------------------------------------
        result = conn.execute(
            text("""
                SELECT
                    COUNT(*) AS payments,

                    COUNT(*) FILTER (
                        WHERE claim_key IS NOT NULL
                    ) AS payments_with_claim,

                    COUNT(*) FILTER (
                        WHERE claim_key IS NULL
                    ) AS payments_without_claim,

                    COALESCE(
                        SUM(raw_row_count),
                        0
                    ) AS source_rows

                FROM claim_payment_data

                WHERE dataset_version = :v
            """),
            {"v": DATASET_VERSION}
        ).mappings().one()

    print("=" * 70)
    print("CLAIM PAYMENT BUILD COMPLETED")
    print("=" * 70)
    print(f"Unique payments       : {result['payments']}")
    print(f"Payments with claim   : {result['payments_with_claim']}")
    print(f"Payments without claim: {result['payments_without_claim']}")
    print(f"Source raw rows       : {result['source_rows']}")
    print("=" * 70)


if __name__ == "__main__":
    main()