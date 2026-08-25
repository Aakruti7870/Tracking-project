"""Validated request schemas for full RMC plant business operations.

These schemas complement the dispatch/POD models in models.py. They cover the
master data and commercial/plant records that must be persisted for a real RMC
operation rather than represented by hard-coded UI values.
"""
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

GRADE_PATTERN = r"^M(?:10|15|20|25|30|35|40|45|50|55|60)(?:[-_ ]?PILE)?$"
GSTIN_PATTERN = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$"
PHONE_PATTERN = r"^\+?[0-9][0-9 -]{7,19}$"


class PlantBusinessProfileBody(BaseModel):
    legal_name: str = Field(min_length=2, max_length=200)
    trade_name: Optional[str] = Field(default=None, max_length=200)
    gstin: Optional[str] = Field(default=None, pattern=GSTIN_PATTERN)
    pan: Optional[str] = Field(default=None, pattern=r"^[A-Z]{5}[0-9]{4}[A-Z]$")
    billing_address: str = Field(min_length=5, max_length=1000)
    state: Optional[str] = Field(default=None, max_length=100)
    state_code: Optional[str] = Field(default=None, pattern=r"^[0-9]{2}$")
    contact_phone: Optional[str] = Field(default=None, pattern=PHONE_PATTERN)
    contact_email: Optional[str] = Field(default=None, max_length=254)
    bank_name: Optional[str] = Field(default=None, max_length=160)
    bank_account_masked: Optional[str] = Field(default=None, max_length=64)
    ifsc: Optional[str] = Field(default=None, pattern=r"^[A-Z]{4}0[A-Z0-9]{6}$")
    invoice_prefix: str = Field(default="INV", min_length=1, max_length=16)
    challan_prefix: str = Field(default="CH", min_length=1, max_length=16)
    quotation_prefix: str = Field(default="QT", min_length=1, max_length=16)
    terms_and_conditions: Optional[str] = Field(default=None, max_length=10000)


class RateCardBody(BaseModel):
    grade: str = Field(pattern=GRADE_PATTERN)
    rate_per_m3: float = Field(gt=0, le=1_000_000)
    gst_rate: float = Field(default=18.0, ge=0, le=100)
    transport_rate_per_km: float = Field(default=0, ge=0, le=100_000)
    pumping_rate_per_m3: float = Field(default=0, ge=0, le=100_000)
    effective_from: date
    effective_to: Optional[date] = None
    active: bool = True

    @field_validator("effective_to")
    @classmethod
    def validate_dates(cls, value, info):
        start = info.data.get("effective_from")
        if value and start and value < start:
            raise ValueError("effective_to must be on or after effective_from")
        return value


class MixDesignBody(BaseModel):
    grade: str = Field(pattern=GRADE_PATTERN)
    version: int = Field(default=1, ge=1, le=10_000)
    cement_kg: float = Field(ge=0, le=2000)
    fly_ash_kg: float = Field(default=0, ge=0, le=2000)
    c_sand_kg: float = Field(default=0, ge=0, le=3000)
    sand_kg: float = Field(default=0, ge=0, le=3000)
    aggregate_10mm_kg: float = Field(default=0, ge=0, le=3000)
    aggregate_20mm_kg: float = Field(default=0, ge=0, le=3000)
    admixture_kg: float = Field(default=0, ge=0, le=200)
    water_litre: float = Field(default=0, ge=0, le=1000)
    target_slump_mm: Optional[float] = Field(default=None, ge=0, le=1000)
    notes: Optional[str] = Field(default=None, max_length=3000)
    active: bool = True


class CustomerSiteBody(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    address: str = Field(min_length=5, max_length=1000)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    contact_person: Optional[str] = Field(default=None, max_length=160)
    contact_mobile: Optional[str] = Field(default=None, pattern=PHONE_PATTERN)
    notes: Optional[str] = Field(default=None, max_length=2000)
    is_default: bool = False


class QuotationBody(BaseModel):
    customer_id: Optional[str] = Field(default=None, max_length=128)
    customer_name: str = Field(min_length=1, max_length=200)
    customer_mobile: Optional[str] = Field(default=None, pattern=PHONE_PATTERN)
    site_name: str = Field(min_length=1, max_length=180)
    site_address: str = Field(min_length=5, max_length=1000)
    grade: str = Field(pattern=GRADE_PATTERN)
    quantity_m3: float = Field(gt=0, le=100_000)
    rate_per_m3: float = Field(gt=0, le=1_000_000)
    gst_rate: float = Field(default=18.0, ge=0, le=100)
    transport_amount: float = Field(default=0, ge=0, le=100_000_000)
    pumping_amount: float = Field(default=0, ge=0, le=100_000_000)
    valid_until: date
    notes: Optional[str] = Field(default=None, max_length=5000)


class QuotationRequestResponseBody(BaseModel):
    action: Literal["SEND", "DECLINE"]
    rate_per_m3: Optional[float] = Field(default=None, gt=0, le=1_000_000)
    gst_rate: float = Field(default=18.0, ge=0, le=100)
    transport_amount: float = Field(default=0, ge=0, le=100_000_000)
    pumping_amount: float = Field(default=0, ge=0, le=100_000_000)
    valid_until: Optional[date] = None
    notes: Optional[str] = Field(default=None, max_length=5000)
    decline_reason: Optional[str] = Field(default=None, max_length=1000)


class ExpenseBody(BaseModel):
    category: Literal[
        "diesel", "salary", "maintenance", "electricity", "rent", "material",
        "transport", "office", "tax", "other"
    ]
    amount: float = Field(gt=0, le=1_000_000_000)
    expense_date: date
    vendor: Optional[str] = Field(default=None, max_length=200)
    reference: Optional[str] = Field(default=None, max_length=160)
    payment_method: Literal["cash", "upi", "bank_transfer", "cheque", "card"] = "cash"
    notes: Optional[str] = Field(default=None, max_length=3000)


class DieselTransactionBody(BaseModel):
    transaction_type: Literal["IN", "OUT", "ADJUSTMENT"]
    litres: float = Field(gt=0, le=1_000_000)
    rate_per_litre: Optional[float] = Field(default=None, ge=0, le=100_000)
    vehicle_id: Optional[str] = Field(default=None, max_length=128)
    supplier_id: Optional[str] = Field(default=None, max_length=128)
    odometer_km: Optional[float] = Field(default=None, ge=0, le=100_000_000)
    reference: Optional[str] = Field(default=None, max_length=160)
    notes: Optional[str] = Field(default=None, max_length=3000)


class AttendanceActionBody(BaseModel):
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    note: Optional[str] = Field(default=None, max_length=1000)


class PayrollRecordBody(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    month: str = Field(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")
    basic_amount: float = Field(ge=0, le=100_000_000)
    allowances: float = Field(default=0, ge=0, le=100_000_000)
    overtime_amount: float = Field(default=0, ge=0, le=100_000_000)
    deductions: float = Field(default=0, ge=0, le=100_000_000)
    paid_days: float = Field(default=0, ge=0, le=31)
    status: Literal["DRAFT", "APPROVED", "PAID"] = "DRAFT"
    notes: Optional[str] = Field(default=None, max_length=3000)


class SupplierBody(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    gstin: Optional[str] = Field(default=None, pattern=GSTIN_PATTERN)
    phone: Optional[str] = Field(default=None, pattern=PHONE_PATTERN)
    email: Optional[str] = Field(default=None, max_length=254)
    address: Optional[str] = Field(default=None, max_length=1000)
    active: bool = True


class PurchaseLineBody(BaseModel):
    material_id: str = Field(min_length=1, max_length=128)
    quantity: float = Field(gt=0, le=1_000_000_000)
    rate: float = Field(ge=0, le=1_000_000_000)


class PurchaseReceiptBody(BaseModel):
    supplier_id: str = Field(min_length=1, max_length=128)
    receipt_number: str = Field(min_length=1, max_length=160)
    receipt_date: date
    lines: list[PurchaseLineBody] = Field(min_length=1, max_length=100)
    gst_amount: float = Field(default=0, ge=0, le=1_000_000_000)
    freight_amount: float = Field(default=0, ge=0, le=1_000_000_000)
    notes: Optional[str] = Field(default=None, max_length=3000)


class OrderLoadBody(BaseModel):
    quantity_m3: float = Field(gt=0, le=100)
    vehicle_id: Optional[str] = Field(default=None, max_length=128)
    driver_id: Optional[str] = Field(default=None, max_length=128)
    scheduled_at: Optional[str] = Field(default=None, max_length=64)
    notes: Optional[str] = Field(default=None, max_length=2000)


class GatePassBody(BaseModel):
    load_id: str = Field(min_length=1, max_length=128)
    security_name: Optional[str] = Field(default=None, max_length=160)
    remarks: Optional[str] = Field(default=None, max_length=2000)
