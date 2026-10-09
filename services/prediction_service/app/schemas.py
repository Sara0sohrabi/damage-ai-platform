from typing import Optional
import re
import jdatetime
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class DamagedItem(BaseModel):
    item_id: Optional[str] = Field(None, pattern=r"^[a-zA-Z0-9-]{1,64}$")
    model_config = ConfigDict(allow_inf_nan=False, extra='forbid')
    title: str = Field(min_length=1, max_length=200)
    quantity: float = Field(default=1, gt=0)
    value_before: Optional[float] = Field(None, ge=0)
    age_years: Optional[float] = Field(None, ge=0)
    condition: Optional[str] = Field(None, max_length=1000)
    damage_description: Optional[str] = Field(None, max_length=2000)
    damage_percent: Optional[float] = Field(None, ge=0, le=100)
    repair_cost: Optional[float] = Field(None, ge=0)
    replacement_cost: Optional[float] = Field(None, ge=0)
    depreciation_amount: Optional[float] = Field(None, ge=0)
    salvage_value: Optional[float] = Field(None, ge=0)


class ClaimPredictionRequest(BaseModel):
    incident_cause: Optional[str] = Field(None, max_length=2000)
    policy_conditions: Optional[str] = Field(None, max_length=4000)
    coverage_limit: Optional[float] = Field(None, ge=0)
    expert_report: Optional[str] = Field(None, max_length=10000)
    damaged_items: list[DamagedItem] = Field(default_factory=list, max_length=100)
    model_config = ConfigDict(allow_inf_nan=False, extra='forbid')
    province_code: Optional[str] = None
    city_code: Optional[str] = None
    coverage_code: Optional[str] = None
    insurance_type_code: Optional[str] = None
    damage_scope: Optional[str] = Field(None, pattern='^(financial|bodily)$')
    event_type_code: Optional[str] = None
    loss_location_code: Optional[str] = None
    loss_location_address: Optional[str] = Field(None, max_length=200, description='آدرس محل مورد خسارت؛ متن پرونده و مستقل از کد محل در مدل')
    occupation_code: Optional[str] = None
    occupation_group_code: Optional[str] = None
    damaged_item_code: Optional[str] = None
    insured_item_type_code: Optional[str] = None
    damage_type_code: Optional[str] = None
    financial_damage_type_code: Optional[str] = None
    structure_type_code: Optional[str] = None
    risk_density_code: Optional[str] = None
    ownership_type_code: Optional[str] = None
    property_type_code: Optional[str] = None
    premium: Optional[float] = Field(None, ge=0)
    item_sum_insured: Optional[float] = Field(None, ge=0)
    total_sum_insured: Optional[float] = Field(None, ge=0)
    estimate_amount: Optional[float] = Field(None, ge=0)
    incident_year: Optional[int] = Field(None, ge=1200, le=1600)
    incident_date: Optional[str] = Field(None, description='تاریخ کامل شمسی حادثه، YYYY/MM/DD')
    policyholder_national_id: Optional[str] = Field(None, pattern=r'^\d{10}$', description='کد ملی بیمه‌گذار')
    policyholder_birth_year: Optional[int] = Field(None, ge=1200, le=1600, description='سال تولد شمسی بیمه‌گذار')
    policyholder_birth_date: Optional[str] = Field(None, pattern=r'^\d{4}/\d{2}/\d{2}$', description='تاریخ تولد شمسی بیمه‌گذار به صورت سال/ماه/روز')
    policyholder_code: Optional[str] = Field(None, max_length=100, description='کد بیمه‌گذار')
    policyholder_name: Optional[str] = Field(None, max_length=200, pattern=r'^[\u0600-\u06FF\s‌]+$')
    policy_number: Optional[str] = Field(None, max_length=100, description='کد رایانه بیمه‌نامه')
    postal_code: Optional[str] = Field(None, pattern=r'^\d{10}$')
    deductible_percent: Optional[float] = Field(None, ge=0, le=100)
    incident_month: Optional[int] = Field(None, ge=1, le=12)
    insured_item_type: Optional[str] = Field(None, max_length=200)

    @model_validator(mode='after')
    def validate_incident_date(self):
        if self.incident_date:
            value = self.incident_date.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789'))
            if not re.fullmatch(r'\d{4}/\d{2}/\d{2}', value):
                raise ValueError('تاریخ حادثه باید به صورت YYYY/MM/DD شمسی باشد')
            year, month, day = map(int, value.split('/'))
            if not 1200 <= year <= 1600:
                raise ValueError('سال حادثه باید بین ۱۲۰۰ و ۱۶۰۰ باشد')
            jdatetime.date(year, month, day)
            self.incident_date = value
            self.incident_year, self.incident_month = year, month
        return self

    @field_validator('*', mode='before')
    @classmethod
    def empty_to_none(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator('policyholder_national_id', mode='before')
    @classmethod
    def normalize_national_id(cls, value):
        if isinstance(value, str):
            return value.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')).strip()
        return value

    @field_validator('postal_code', mode='before')
    @classmethod
    def normalize_postal_code(cls, value):
        if isinstance(value, str):
            return value.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')).strip()
        return value


class ActualPaymentRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra='forbid')
    actual_paid_loss: float = Field(ge=0)
