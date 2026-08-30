from app.db import SessionLocal
from app.models import MappingValue
from scripts.mapping_seed import MAPPINGS

DOMAIN_TABLES = {
    "coverage": "CoverageMapping",
    "event_type": "EventTypeMapping",
    "loss_location": "LossLocationMapping",
    "occupation": "OccupationMapping",
    "occupation_group": "OccupationGroupMapping",
    "damaged_item": "DamagedItemMapping",
    "damage_type": "DamageTypeMapping",
    "financial_damage_type": "FinancialDamageTypeMapping",
    "property_type": "PropertyTypeMapping",
    "structure_type": "StructureTypeMapping",
    "risk_density": "RiskDensityMapping",
    "ownership_type": "OwnershipTypeMapping",
}

def main():
    db = SessionLocal()
    try:
        # Generic registry is useful for interpretation/reporting.
        db.query(MappingValue).delete()
        for item in MAPPINGS:
            db.add(MappingValue(**item))

        # Also populate domain-specific lookup tables used by FK columns.
        from app import models
        for mapping_name, class_name in DOMAIN_TABLES.items():
            cls = getattr(models, class_name)
            db.query(cls).delete()
        for item in MAPPINGS:
            cls_name = DOMAIN_TABLES.get(item["mapping_name"])
            if not cls_name:
                continue
            cls = getattr(models, cls_name)
            db.add(cls(mapped_code=item["mapped_code"], mapped_title=item["mapped_title"],
                       source_value=item.get("source_value"), mapping_version=item["mapping_version"]))
        db.commit()
        print(f"Loaded {len(MAPPINGS)} mappings into generic and domain lookup tables.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
