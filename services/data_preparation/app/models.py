from sqlalchemy import Column, Integer, BigInteger, Numeric, String, DateTime, JSON, Boolean, Float, Text, ForeignKey
from sqlalchemy.sql import func
from .db import Base

class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    id = Column(Integer, primary_key=True)
    dataset_version = Column(String(100), unique=True, nullable=False)
    source_file = Column(String(500))
    row_count = Column(Integer)
    mapping_version = Column(String(100))
    cleaning_version = Column(String(100))
    status = Column(String(30), default="ready")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RawDamageData(Base):
    __tablename__ = "raw_damage_data"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    dataset_version = Column(String(100), index=True)
    source_file = Column(String(500))
    source_row = Column(Integer)
    external_identifier = Column(String(255))
    raw_data = Column(JSON, nullable=False)
    imported_at = Column(DateTime(timezone=True), server_default=func.now())

class CleanDamageData(Base):
    __tablename__ = "clean_damage_data"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    dataset_version = Column(String(100), index=True)
    province_code = Column(String(100))
    city_code = Column(String(100))
    coverage_code = Column(String(100), ForeignKey("coverage_mapping.mapped_code"))
    event_type_code = Column(String(100), ForeignKey("event_type_mapping.mapped_code"))
    loss_location_code = Column(String(100), ForeignKey("loss_location_mapping.mapped_code"))
    occupation_code = Column(String(100), ForeignKey("occupation_mapping.mapped_code"))
    occupation_group_code = Column(String(100), ForeignKey("occupation_group_mapping.mapped_code"))
    damaged_item_code = Column(String(100), ForeignKey("damaged_item_mapping.mapped_code"))
    insured_item_type_code = Column(String(100))
    damage_type_code = Column(String(100), ForeignKey("damage_type_mapping.mapped_code"))
    financial_damage_type_code = Column(String(100), ForeignKey("financial_damage_type_mapping.mapped_code"))
    structure_type_code = Column(String(100), ForeignKey("structure_type_mapping.mapped_code"))
    risk_density_code = Column(String(100), ForeignKey("risk_density_mapping.mapped_code"))
    ownership_type_code = Column(String(100), ForeignKey("ownership_type_mapping.mapped_code"))
    property_type_code = Column(String(100), ForeignKey("property_type_mapping.mapped_code"))
    premium = Column(Numeric)
    item_sum_insured = Column(Numeric)
    total_sum_insured = Column(Numeric)
    estimate_amount = Column(Numeric)
    paid_loss = Column(Numeric, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MappingValue(Base):
    __tablename__ = "mapping_values"
    id = Column(Integer, primary_key=True)
    mapping_version = Column(String(100), index=True)
    mapping_name = Column(String(100), index=True)
    source_value = Column(String(500))
    mapped_code = Column(String(100))
    mapped_title = Column(String(500))
    active = Column(Boolean, default=True)

class EdaRun(Base):
    __tablename__ = "eda_runs"
    id = Column(Integer, primary_key=True)
    dataset_version = Column(String(100), index=True)
    report_version = Column(String(100))
    row_count = Column(Integer)
    column_count = Column(Integer)
    missing_cells = Column(Integer)
    duplicate_rows = Column(Integer)
    summary_json = Column(JSON)
    report_path = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ModelRun(Base):
    __tablename__ = "model_runs"
    id = Column(Integer, primary_key=True)
    model_version = Column(String(100), unique=True, nullable=False)
    dataset_version = Column(String(100), index=True)
    algorithm = Column(String(100))
    test_size = Column(Float)
    train_rows = Column(Integer)
    test_rows = Column(Integer)
    mae = Column(Numeric)
    rmse = Column(Numeric)
    r2 = Column(Numeric)
    within_10pct = Column(Float)
    within_20pct = Column(Float)
    cluster_count = Column(Integer)
    status = Column(String(30), default="completed")
    artifact_path = Column(String(500))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ClusterResult(Base):
    __tablename__ = "cluster_results"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    dataset_version = Column(String(100), index=True)
    model_version = Column(String(100), index=True)
    source_row = Column(Integer)
    cluster_id = Column(Integer)
    category = Column(String(100))
    paid_loss = Column(Numeric)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class TestPredictionResult(Base):
    __tablename__ = "test_prediction_results"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    dataset_version = Column(String(100), index=True)
    model_version = Column(String(100), index=True)
    source_row = Column(Integer)
    actual_paid_loss = Column(Numeric)
    predicted_paid_loss = Column(Numeric)
    estimate_amount = Column(Numeric)
    absolute_error = Column(Numeric)
    estimate_absolute_error = Column(Numeric)
    cluster_id = Column(Integer)
    category = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Operational request: one row per web-service prediction, with the complete input and result.
class PredictionRequest(Base):
    __tablename__ = "prediction_requests"
    request_id = Column(String(36), primary_key=True)
    payload = Column(JSON, nullable=False)
    province_code = Column(String(100)); city_code = Column(String(100)); coverage_code = Column(String(100))
    event_type_code = Column(String(100)); loss_location_code = Column(String(100)); occupation_code = Column(String(100))
    occupation_group_code = Column(String(100)); damaged_item_code = Column(String(100)); damage_type_code = Column(String(100))
    financial_damage_type_code = Column(String(100)); structure_type_code = Column(String(100)); risk_density_code = Column(String(100))
    ownership_type_code = Column(String(100)); property_type_code = Column(String(100))
    premium = Column(Numeric); item_sum_insured = Column(Numeric); total_sum_insured = Column(Numeric); estimate_amount = Column(Numeric)
    predicted_loss = Column(Numeric); maximum_payable_loss = Column(Numeric); cluster_id = Column(Integer); category = Column(String(100))
    model_version = Column(String(100)); actual_paid_loss = Column(Numeric, nullable=True)
    prediction_error = Column(Numeric, nullable=True); estimate_error = Column(Numeric, nullable=True)
    status = Column(String(30), default="predicted")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    request_id = Column(String(36), index=True, nullable=False)
    evidence_type = Column(String(50), nullable=False)  # image, invoice, customer_text, expert_report, other
    file_name = Column(String(500))
    storage_key = Column(String(1000))
    content_type = Column(String(200))
    extracted_text = Column(Text)
    metadata_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ClaimInvoiceItem(Base):
    __tablename__ = "claim_invoice_items"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    request_id = Column(String(36), index=True, nullable=False)
    item_name = Column(String(500))
    quantity = Column(Numeric)
    unit_price = Column(Numeric)
    total_price = Column(Numeric)
    metadata_json = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Lookup domains. The same code may exist in different domains (e.g. coverage=1 and damage_type=1).
def _mapping_table(name):
    attrs = {
        '__tablename__': name,
        'id': Column(BigInteger, primary_key=True, autoincrement=True),
        'mapped_code': Column(String(100), unique=True, nullable=False),
        'mapped_title': Column(String(500), nullable=False),
        'source_value': Column(String(500)),
        'category': Column(String(200)),
        'interpretation_description': Column(Text),
        'risk_level': Column(String(30)),
        'mapping_version': Column(String(100), nullable=False, default='excel_001'),
        'active': Column(Boolean, nullable=False, default=True),
    }
    return type(name.title().replace('_',''), (Base,), attrs)

CoverageMapping = _mapping_table('coverage_mapping')
EventTypeMapping = _mapping_table('event_type_mapping')
LossLocationMapping = _mapping_table('loss_location_mapping')
OccupationMapping = _mapping_table('occupation_mapping')
OccupationGroupMapping = _mapping_table('occupation_group_mapping')
DamagedItemMapping = _mapping_table('damaged_item_mapping')
DamageTypeMapping = _mapping_table('damage_type_mapping')
FinancialDamageTypeMapping = _mapping_table('financial_damage_type_mapping')
PropertyTypeMapping = _mapping_table('property_type_mapping')
StructureTypeMapping = _mapping_table('structure_type_mapping')
RiskDensityMapping = _mapping_table('risk_density_mapping')
OwnershipTypeMapping = _mapping_table('ownership_type_mapping')
