import os
import pandas as pd
from sqlalchemy import create_engine, text


EXCEL_PATH = "/data/damagefire_fully_encoded.xlsx"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://damage:damage@postgres:5432/damage_ai"
)


def clean_value(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if value.lower() in {"nan", "none", ""}:
        return None

    return value


def main():

    print("=" * 70)
    print("LOADING OCCUPATION / ACTIVITY MAPPINGS")
    print("=" * 70)

    print(f"Reading Excel: {EXCEL_PATH}")

    df = pd.read_excel(
        EXCEL_PATH,
        sheet_name="Sheet1"
    )

    required_columns = [
        "فعالیت شغلی",
        "کد شغل / فعالیت",
        "گروه کلان فعالیت",
        "کد گروه فعالیت",
    ]

    missing = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

    mapping_df = df[required_columns].copy()

    # تمیز کردن مقادیر
    for col in required_columns:
        mapping_df[col] = mapping_df[col].apply(clean_value)

    # فقط رکوردهایی که کد فعالیت دارند
    mapping_df = mapping_df[
        mapping_df["کد شغل / فعالیت"].notna()
    ].copy()

    # یک رکورد برای هر کد فعالیت
    mapping_df = mapping_df.drop_duplicates(
        subset=["کد شغل / فعالیت"],
        keep="first"
    )

    print(f"Excel rows: {len(df)}")
    print(f"Unique occupation/activity codes: {len(mapping_df)}")

    engine = create_engine(DATABASE_URL)

    insert_sql = text("""
        INSERT INTO occupation_activity_mapping (
            activity_code,
            activity_title,
            source_value,
            macro_group,
            macro_group_code,
            mapping_version,
            active
        )
        VALUES (
            :activity_code,
            :activity_title,
            :source_value,
            :macro_group,
            :macro_group_code,
            'mapping_001',
            TRUE
        )
        ON CONFLICT (activity_code, mapping_version)
        DO UPDATE SET
            activity_title = EXCLUDED.activity_title,
            source_value = EXCLUDED.source_value,
            macro_group = EXCLUDED.macro_group,
            macro_group_code = EXCLUDED.macro_group_code,
            active = TRUE
    """)

    inserted = 0

    with engine.begin() as conn:

        for _, row in mapping_df.iterrows():

            activity_code = clean_value(
                row["کد شغل / فعالیت"]
            )

            activity_title = clean_value(
                row["فعالیت شغلی"]
            )

            macro_group = clean_value(
                row["گروه کلان فعالیت"]
            )

            macro_group_code = clean_value(
                row["کد گروه فعالیت"]
            )

            if activity_code is None:
                continue

            if activity_title is None:
                activity_title = f"Activity {activity_code}"

            conn.execute(
                insert_sql,
                {
                    "activity_code": activity_code,
                    "activity_title": activity_title,
                    "source_value": activity_title,
                    "macro_group": macro_group,
                    "macro_group_code": macro_group_code,
                }
            )

            inserted += 1

    print("-" * 70)
    print(f"Mappings processed: {inserted}")
    print("Occupation/activity mapping loaded successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()
    