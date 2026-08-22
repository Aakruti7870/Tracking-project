"""Mongo connection + Pydantic base document with ObjectId handling."""
from typing import Annotated, Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from config import settings

client = AsyncIOMotorClient(settings.MONGO_URL)
db = client[settings.DB_NAME]


def _coerce_object_id(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, ObjectId):
        return str(value)
    return str(value)


PyObjectId = Annotated[Optional[str], BeforeValidator(_coerce_object_id)]


class BaseDocument(BaseModel):
    """All persisted models extend this. Maps Mongo `_id` <-> `id` (str)."""

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    id: PyObjectId = Field(default=None, alias="_id")

    @classmethod
    def from_mongo(cls, doc: Optional[dict]):
        if not doc:
            return None
        return cls(**doc)

    def to_mongo(self, exclude_id: bool = True) -> dict:
        data = self.model_dump(by_alias=True, exclude_none=True)
        if exclude_id:
            data.pop("_id", None)
        return data


# Collection handles
users = db.users
sessions = db.sessions
otps = db.otps
audit_logs = db.audit_logs
notifications = db.notifications
plants = db.plants
orders = db.orders
kyc_profiles = db.kyc_profiles
order_status_history = db.order_status_history
counters = db.counters
vehicles = db.vehicles
driver_trips = db.driver_trips
trip_status_history = db.trip_status_history
challans = db.challans
proof_of_delivery = db.proof_of_delivery
attendance = db.attendance
driver_incidents = db.driver_incidents
invoices = db.invoices
payments = db.payments
production_batches = db.production_batches
vehicle_locations = db.vehicle_locations
materials = db.materials


async def next_sequence(name: str) -> int:
    from pymongo import ReturnDocument

    doc = await counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc["seq"]


async def ensure_indexes() -> None:
    await otps.create_index("expires_at", expireAfterSeconds=0)
    await sessions.create_index("expires_at", expireAfterSeconds=0)
    await otps.create_index([("identifier_key", 1), ("created_at", -1)])
    await users.create_index("identifier_keys")
