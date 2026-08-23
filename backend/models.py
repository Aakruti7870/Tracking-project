"""Domain models (Pydantic) persisted in MongoDB."""
from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from database import BaseDocument

GRADE_PATTERN = r"^M(?:10|15|20|25|30|35|40|45|50|55|60)(?:[-_ ]?PILE)?$"


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
    identifier_keys: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    primary_role: str
    status: str = AccountStatus.ACTIVE
    plant_id: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class OtpChallenge(BaseDocument):
    identifier_key: str
    channel: str
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
    status: str = "active"
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
    delivery_mode: Literal["DELIVERY", "ONLY_LOADING"] = "DELIVERY"
    status: str = "PENDING"
    payment_status: str = "UNPAID"
    created_at: datetime = Field(default_factory=utcnow)


class KycProfile(BaseDocument):
    user_id: str
    purpose: str
    status: str = KycStatus.NOT_STARTED
    updated_at: datetime = Field(default_factory=utcnow)


class RequestOtpBody(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)


class VerifyOtpBody(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=4, max_length=10, pattern=r"^\d+$")


class CreateOrderBody(BaseModel):
    plant_id: str = Field(min_length=1, max_length=128)
    grade: str = Field(pattern=GRADE_PATTERN)
    quantity: float = Field(gt=0, le=10000)
    site_name: str = Field(min_length=1, max_length=160)
    site_address: str = Field(min_length=1, max_length=500)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)
    delivery_date: str = Field(min_length=8, max_length=32)
    delivery_time: Optional[str] = Field(default=None, max_length=32)
    delivery_mode: Literal["DELIVERY", "ONLY_LOADING"] = "DELIVERY"
    contact_person: Optional[str] = Field(default=None, max_length=160)
    contact_mobile: Optional[str] = Field(default=None, pattern=r"^\+?[0-9][0-9 -]{7,19}$")
    notes: Optional[str] = Field(default=None, max_length=2000)
    save_draft: bool = False


class RejectOrderBody(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class AssignTmBody(BaseModel):
    vehicle_id: str = Field(min_length=1, max_length=128)


class AssignDriverBody(BaseModel):
    driver_id: str = Field(min_length=1, max_length=128)


class ChallanBody(BaseModel):
    batcher: Optional[str] = Field(default=None, max_length=160)
    supervisor: Optional[str] = Field(default=None, max_length=160)
    quality_engineer: Optional[str] = Field(default=None, max_length=160)
    remarks: Optional[str] = Field(default=None, max_length=2000)


class PodBody(BaseModel):
    receiver_name: str = Field(min_length=1, max_length=160)
    delivered_quantity: float = Field(gt=0, le=10000)
    remarks: Optional[str] = Field(default=None, max_length=2000)
    photo_path: Optional[str] = Field(default=None, max_length=512)
    signature: Optional[str] = Field(default=None, max_length=250000)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)


class GeoBody(BaseModel):
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)


class SosBody(BaseModel):
    type: Literal["Emergency", "Accident", "Breakdown", "Safety"]
    remark: Optional[str] = Field(default=None, max_length=2000)
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lng: Optional[float] = Field(default=None, ge=-180, le=180)


class ProductionBatchBody(BaseModel):
    quantity: float = Field(gt=0, le=10000)
    batch_reference: Optional[str] = Field(default=None, max_length=160)
    remarks: Optional[str] = Field(default=None, max_length=2000)
    consume_materials: bool = True


class PaymentBody(BaseModel):
    amount: float = Field(gt=0, le=1000000000)
    method: Literal["cash", "card", "upi", "bank_transfer", "cheque"] = "cash"
    note: Optional[str] = Field(default=None, max_length=1000)


class LocationBody(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy: Optional[float] = Field(default=None, ge=0, le=10000)


class KycDecisionBody(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=1000)


MaterialCode = Literal[
    "CEMENT",
    "FLY_ASH",
    "C_SAND",
    "SAND",
    "AGGREGATE_10MM",
    "AGGREGATE_20MM",
    "ADMIXTURE",
    "WATER",
    "DIESEL",
    "OTHER",
]


class MaterialBody(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    code: Optional[MaterialCode] = None
    unit: str = Field(min_length=1, max_length=32)
    stock: float = Field(ge=0, le=1000000000)
    reorder: float = Field(ge=0, le=1000000000)


class StockAdjustBody(BaseModel):
    delta: float = Field(ge=-1000000000, le=1000000000)
    note: Optional[str] = Field(default=None, max_length=1000)


class VehicleBody(BaseModel):
    tm_number: str = Field(min_length=1, max_length=64)
    capacity_m3: float = Field(gt=0, le=100)


class VehicleStatusBody(BaseModel):
    status: Literal["available", "maintenance"]


class QualityTestBody(BaseModel):
    order_id: str = Field(min_length=1, max_length=128)
    slump_mm: Optional[float] = Field(default=None, ge=0, le=1000)
    cube_7d: Optional[float] = Field(default=None, ge=0, le=1000)
    cube_28d: Optional[float] = Field(default=None, ge=0, le=1000)
    actual_cement: Optional[float] = Field(default=None, ge=0, le=2000)
    actual_water: Optional[float] = Field(default=None, ge=0, le=2000)
    result: Literal["PASS", "FAIL"] = "PASS"
    remarks: Optional[str] = Field(default=None, max_length=2000)
