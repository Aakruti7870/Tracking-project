"""Domain models (Pydantic) persisted in MongoDB."""
from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from database import BaseDocument


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AccountStatus(str):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DISABLED = "disabled"
    DELETED = "deleted"


class KycStatus(str):
    NOT_STARTED = "NOT_STARTED"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    REQUIRES_REVERIFICATION = "REQUIRES_REVERIFICATION"


class User(BaseDocument):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    # HMAC keys of email/phone for lookup without storing raw sensitive index
    identifier_keys: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    primary_role: str
    status: str = AccountStatus.ACTIVE
    plant_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class OtpChallenge(BaseDocument):
    identifier_key: str
    channel: str  # email | sms
    code_hash: str
    attempts: int = 0
    consumed: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime


class Session(BaseDocument):
    user_id: str
    role: str
    revoked: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime


class Plant(BaseDocument):
    name: str
    owner_id: Optional[str] = None
    city: str
    district: Optional[str] = None
    address: str
    lat: float
    lng: float
    grades: List[str] = Field(default_factory=list)
    contact_phone: str
    service_area_km: float = 25.0
    status: str = "active"        # active | suspended
    verified: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Order(BaseDocument):
    order_number: str
    customer_id: str
    plant_id: str
    plant_name: str
    grade: str
    quantity: float
    site_name: str
    site_address: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    delivery_date: str
    delivery_time: Optional[str] = None
    status: str = "PENDING"
    payment_status: str = "UNPAID"
    created_at: datetime = Field(default_factory=utcnow)


class KycProfile(BaseDocument):
    user_id: str
    purpose: str          # CUSTOMER | DRIVER | PLANT
    status: str = KycStatus.NOT_STARTED
    updated_at: datetime = Field(default_factory=utcnow)


# ---- Request/response schemas ----

class RequestOtpBody(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)


class VerifyOtpBody(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=4, max_length=10, pattern=r"^\d+$")


class CreateOrderBody(BaseModel):
    plant_id: str
    grade: str = Field(pattern=r"^M(?:10|15|20|25|30|35|40|45|50|55|60|65|70|75|80)$")
    quantity: float = Field(gt=0, le=10000)
    site_name: str = Field(min_length=1, max_length=160)
    site_address: str = Field(min_length=1, max_length=500)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    delivery_date: str = Field(min_length=8, max_length=32)
    delivery_time: Optional[str] = Field(default=None, max_length=16)
    contact_person: Optional[str] = Field(default=None, max_length=120)
    contact_mobile: Optional[str] = Field(default=None, pattern=r"^\+?[0-9][0-9 -]{7,19}$")
    notes: Optional[str] = Field(default=None, max_length=1000)
    save_draft: bool = False


class RejectOrderBody(BaseModel):
    reason: str = Field(min_length=1)


class AssignTmBody(BaseModel):
    vehicle_id: str


class AssignDriverBody(BaseModel):
    driver_id: str


class ChallanBody(BaseModel):
    batcher: Optional[str] = None
    supervisor: Optional[str] = None
    quality_engineer: Optional[str] = None
    remarks: Optional[str] = None


class PodBody(BaseModel):
    receiver_name: str = Field(min_length=1, max_length=120)
    delivered_quantity: float = Field(gt=0, le=10000)
    remarks: Optional[str] = Field(default=None, max_length=1000)
    photo_path: Optional[str] = Field(default=None, max_length=500)
    signature: Optional[str] = Field(default=None, max_length=200000)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)


class GeoBody(BaseModel):
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)


class SosBody(BaseModel):
    type: Literal["Emergency", "Accident", "Breakdown", "Safety"]
    remark: Optional[str] = Field(default=None, max_length=1000)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)


class ProductionBatchBody(BaseModel):
    quantity: float = Field(gt=0)
    remarks: Optional[str] = None


class PaymentBody(BaseModel):
    amount: float = Field(gt=0, le=100000000)
    method: Literal["cash", "card", "upi", "bank_transfer", "cheque"] = "cash"
    note: Optional[str] = Field(default=None, max_length=500)


class LocationBody(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy: Optional[float] = Field(default=None, ge=0, le=100000)


class KycDecisionBody(BaseModel):
    reason: Optional[str] = None


class MaterialBody(BaseModel):
    name: str = Field(min_length=1)
    unit: str = Field(min_length=1)
    stock: float = Field(ge=0)
    reorder: float = Field(ge=0)


class StockAdjustBody(BaseModel):
    delta: float  # +ve = stock in, -ve = stock out
    note: Optional[str] = None


class VehicleBody(BaseModel):
    tm_number: str = Field(min_length=1)
    capacity_m3: float = Field(gt=0)


class VehicleStatusBody(BaseModel):
    status: Literal["available", "maintenance"]


class QualityTestBody(BaseModel):
    order_id: str
    slump_mm: Optional[float] = None
    cube_7d: Optional[float] = None
    cube_28d: Optional[float] = None
    actual_cement: Optional[float] = None
    actual_water: Optional[float] = None
    result: Literal["PASS", "FAIL"] = "PASS"
    remarks: Optional[str] = Field(default=None, max_length=1000)
