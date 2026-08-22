"""Domain models (Pydantic) persisted in MongoDB."""
from datetime import datetime, timezone
from typing import List, Optional

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
    identifier: str


class VerifyOtpBody(BaseModel):
    identifier: str
    code: str
