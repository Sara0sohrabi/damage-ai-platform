from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


# ============================================================
# EVIDENCE
# ============================================================

class Evidence(BaseModel):
    evidence_type: str = Field(
        ...,
        description="image | invoice | customer_text | expert_report | other"
    )

    file_name: Optional[str] = None
    storage_key: Optional[str] = None
    content_type: Optional[str] = None
    extracted_text: Optional[str] = None

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )


# ============================================================
# INVOICE ITEM
# ============================================================

class InvoiceItem(BaseModel):
    item_name: str

    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None

    metadata: Dict[str, Any] = Field(
        default_factory=dict
    )


# ============================================================
# CLAIM PREDICTION REQUEST
# ============================================================

class ClaimPredictionRequest(BaseModel):

    # --------------------------------------------------------
    # Geographical
    # --------------------------------------------------------

    province_code: Optional[str] = None
    city_code: Optional[str] = None

    # --------------------------------------------------------
    # Policy / Insurance
    # --------------------------------------------------------

    coverage_code: Optional[str] = None

    insurance_type_code: str = Field(
        ...,
        description="1=مسکونی, 2=صنعتی, 3=غیرصنعتی"
    )

    # --------------------------------------------------------
    # Claim characteristics
    # --------------------------------------------------------

    event_type_code: Optional[str] = None

    insured_item_type_code: Optional[str] = None

    damaged_item_code: Optional[str] = None

    damage_type_code: Optional[str] = None

    financial_damage_type_code: Optional[str] = None

    # --------------------------------------------------------
    # Property / Risk
    # --------------------------------------------------------

    structure_type_code: Optional[str] = None

    risk_density_code: Optional[str] = None

    ownership_type_code: Optional[str] = None

    property_type_code: Optional[str] = None

    loss_location_code: Optional[str] = None

    # --------------------------------------------------------
    # Occupation
    # --------------------------------------------------------

    occupation_code: Optional[str] = None

    occupation_group_code: Optional[str] = None

    # --------------------------------------------------------
    # Financial
    # --------------------------------------------------------

    premium: Optional[float] = Field(
        None,
        ge=0,
        description="حق بیمه"
    )

    item_sum_insured: Optional[float] = Field(
        None,
        ge=0,
        description="سرمایه مورد بیمه"
    )

    total_sum_insured: Optional[float] = Field(
        None,
        ge=0,
        description="کل سرمایه بیمه‌نامه"
    )

    # --------------------------------------------------------
    # Estimate Amount
    # --------------------------------------------------------
    # این مقدار برای مقایسه با Prediction نگهداری می‌شود.
    # Target مدل نیست و نباید باعث leakage شود.

    estimate_amount: Optional[float] = Field(
        None,
        ge=0,
        description="مبلغ برآورد خسارت جهت مقایسه با پیش‌بینی"
    )

    # --------------------------------------------------------
    # Supporting information
    # --------------------------------------------------------

    customer_description: Optional[str] = None

    expert_report_text: Optional[str] = None

    # --------------------------------------------------------
    # Invoice / Evidence
    # --------------------------------------------------------

    invoice_items: List[InvoiceItem] = Field(
        default_factory=list
    )

    evidence: List[Evidence] = Field(
        default_factory=list
    )