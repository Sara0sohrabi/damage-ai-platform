import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


EXCEL_PATH = "/data/damagefire_fully_encoded.xlsx"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://damage:damage@postgres:5432/damage_ai"
)

MAPPING_VERSION = "mapping_001"


def clean(value):
    if pd.isna(value):
        return None

    value = str(value).strip()

    if value.lower() in {"", "nan", "none"}:
        return None

    return value


def load_mapping(
    conn,
    df,
    table,
    code_col,
    title_col,
    source_col=None,
    category_col=None,
    group_col=None,
    group_code_col=None,
):
    """
    Generic mapping loader.
    """

    cols = [code_col, title_col]

    for c in [
        source_col,
        category_col,
        group_col,
        group_code_col,
    ]:
        if c and c not in cols:
            cols.append(c)

    available = [c for c in cols if c in df.columns]

    if code_col not in available:
        print(f"SKIP {table}: missing code column {code_col}")
        return 0

    if title_col and title_col not in available:
        print(f"SKIP {table}: missing title column {title_col}")
        return 0

    temp = df[available].copy()

    temp = temp.drop_duplicates(subset=[code_col])

    count = 0

    for _, row in temp.iterrows():

        code = clean(row[code_col])

        if code is None:
            continue

        title = clean(row[title_col]) if title_col else code

        if title is None:
            title = f"Value {code}"

        source_value = (
            clean(row[source_col])
            if source_col and source_col in row.index
            else title
        )

        category = (
            clean(row[category_col])
            if category_col and category_col in row.index
            else None
        )

        interpretation = None
        risk_level = None

        macro_group = (
            clean(row[group_col])
            if group_col and group_col in row.index
            else None
        )

        macro_group_code = (
            clean(row[group_code_col])
            if group_code_col and group_code_col in row.index
            else None
        )

        # occupation_activity has a different schema
        if table == "occupation_activity_mapping":

            conn.execute(
                text("""
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
                        :code,
                        :title,
                        :source,
                        :group,
                        :group_code,
                        :version,
                        TRUE
                    )
                    ON CONFLICT (activity_code, mapping_version)
                    DO UPDATE SET
                        activity_title = EXCLUDED.activity_title,
                        source_value = EXCLUDED.source_value,
                        macro_group = EXCLUDED.macro_group,
                        macro_group_code = EXCLUDED.macro_group_code,
                        active = TRUE
                """),
                {
                    "code": code,
                    "title": title,
                    "source": source_value,
                    "group": macro_group,
                    "group_code": macro_group_code,
                    "version": MAPPING_VERSION,
                },
            )

        else:

            conn.execute(
                text(f"""
                    INSERT INTO {table} (
                        mapped_code,
                        mapped_title,
                        source_value,
                        category,
                        interpretation_description,
                        risk_level,
                        mapping_version,
                        active
                    )
                    VALUES (
                        :code,
                        :title,
                        :source,
                        :category,
                        :interpretation,
                        :risk_level,
                        :version,
                        TRUE
                    )
                    ON CONFLICT (mapped_code)
                    DO UPDATE SET
                        mapped_title = EXCLUDED.mapped_title,
                        source_value = EXCLUDED.source_value,
                        category = EXCLUDED.category,
                        interpretation_description =
                            EXCLUDED.interpretation_description,
                        risk_level = EXCLUDED.risk_level,
                        mapping_version = EXCLUDED.mapping_version,
                        active = TRUE
                """),
                {
                    "code": code,
                    "title": title,
                    "source": source_value,
                    "category": category,
                    "interpretation": interpretation,
                    "risk_level": risk_level,
                    "version": MAPPING_VERSION,
                },
            )

        count += 1

    return count


def main():

    print("=" * 70)
    print("LOADING ALL MAPPINGS")
    print("=" * 70)

    print(f"Excel: {EXCEL_PATH}")

    path = Path(EXCEL_PATH)

    if not path.exists():
        raise FileNotFoundError(EXCEL_PATH)

    df = pd.read_excel(
        path,
        sheet_name="Sheet1"
    )

    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")

    engine = create_engine(DATABASE_URL)

    results = {}

    with engine.begin() as conn:

        # ------------------------------------------------------------
        # OCCUPATION / ACTIVITY
        # ------------------------------------------------------------

        results["occupation_activity_mapping"] = load_mapping(
            conn,
            df,
            "occupation_activity_mapping",
            "کد شغل / فعالیت",
            "فعالیت شغلی",
            source_col="فعالیت شغلی",
            group_col="گروه کلان فعالیت",
            group_code_col="کد گروه فعالیت",
        )

        # ------------------------------------------------------------
        # OCCUPATION GROUP
        # ------------------------------------------------------------

        results["occupation_group_mapping"] = load_mapping(
            conn,
            df,
            "occupation_group_mapping",
            "کد گروه فعالیت",
            "گروه کلان فعالیت",
            source_col="گروه کلان فعالیت",
        )

        # ------------------------------------------------------------
        # DAMAGED ITEM
        # ------------------------------------------------------------

        results["damaged_item_mapping"] = load_mapping(
            conn,
            df,
            "damaged_item_mapping",
            "مورد بیمه_Code",
            "مورد بیمه",
            source_col="مورد بیمه",
        )

        # ------------------------------------------------------------
        # EVENT TYPE
        # ------------------------------------------------------------

        results["event_type_mapping"] = load_mapping(
            conn,
            df,
            "event_type_mapping",
            "FireHadeseKindTitle_Code",
            "FireHadeseKindTitle",
            source_col="FireHadeseKindTitle",
        )

        # ------------------------------------------------------------
        # FINANCIAL DAMAGE TYPE
        # ------------------------------------------------------------

        results["financial_damage_type_mapping"] = load_mapping(
            conn,
            df,
            "financial_damage_type_mapping",
            "کد نوع خسارت مالی",
            "نوع خسارت مالی",
            source_col="نوع خسارت مالی",
        )

        # ------------------------------------------------------------
        # LOSS LOCATION
        # ------------------------------------------------------------

        results["loss_location_mapping"] = load_mapping(
            conn,
            df,
            "loss_location_mapping",
            "HadesePlace_Code",
            "HadesePlace",
            source_col="HadesePlace",
        )

        # ------------------------------------------------------------
        # OWNERSHIP
        # ------------------------------------------------------------

        results["ownership_type_mapping"] = load_mapping(
            conn,
            df,
            "ownership_type_mapping",
            "نوع مالکیت_Code",
            "نوع مالکیت",
            source_col="نوع مالکیت",
        )

        # ------------------------------------------------------------
        # PROPERTY TYPE
        # ------------------------------------------------------------

        results["property_type_mapping"] = load_mapping(
            conn,
            df,
            "property_type_mapping",
            "نوع ملک_Code",
            "نوع ملک",
            source_col="نوع ملک",
        )

        # ------------------------------------------------------------
        # RISK DENSITY
        # ------------------------------------------------------------

        results["risk_density_mapping"] = load_mapping(
            conn,
            df,
            "risk_density_mapping",
            "تراکم ریسک_Code",
            "تراکم ریسک",
            source_col="تراکم ریسک",
        )

        # ------------------------------------------------------------
        # STRUCTURE
        # ------------------------------------------------------------

        results["structure_type_mapping"] = load_mapping(
            conn,
            df,
            "structure_type_mapping",
            "نوع سازه_Code",
            "نوع سازه",
            source_col="نوع سازه",
        )

        # ------------------------------------------------------------
        # DAMAGE TYPE
        # ------------------------------------------------------------

        results["damage_type_mapping"] = load_mapping(
            conn,
            df,
            "damage_type_mapping",
            "کد نوع خسارت",
            "نوع خسارت",
            source_col="نوع خسارت",
        )

        # ------------------------------------------------------------
        # COVERAGE
        # ------------------------------------------------------------

        results["coverage_mapping"] = load_mapping(
            conn,
            df,
            "coverage_mapping",
            "Coverage_Code",
            "CoverageTitel",
            source_col="CoverageTitel",
        )

    print()
    print("=" * 70)
    print("MAPPING LOAD RESULT")
    print("=" * 70)

    for table, count in results.items():
        print(f"{table:40} {count:6}")

    print("=" * 70)
    print("DONE")


if __name__ == "__main__":
    main()


