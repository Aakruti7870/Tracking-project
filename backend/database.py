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
stock_movements = db.stock_movements
quality_tests = db.quality_tests
storage_objects = db.storage_objects


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
    """Create indexes used by auth, tenant scoping, timelines and idempotency.

    Unique indexes intentionally enforce domain invariants. If existing data
    violates an invariant, startup surfaces that integrity problem rather than
    silently permitting ambiguous production behavior.
    """
    # Auth/session lifecycle.
    await otps.create_index("expires_at", expireAfterSeconds=0)
    await sessions.create_index("expires_at", expireAfterSeconds=0)
    await sessions.create_index([("user_id", 1), ("revoked", 1)])
    await otps.create_index([("identifier_key", 1), ("created_at", -1)])
    await otps.create_index(
        "identifier_key",
        unique=True,
        partialFilterExpression={"consumed": False},
        name="one_active_otp_per_identifier",
    )
    await users.create_index("identifier_keys", unique=True, name="unique_login_identifier")
    await users.create_index([("plant_id", 1), ("primary_role", 1), ("status", 1)])

    # Core tenant/order access paths.
    await plants.create_index([("status", 1), ("verified", 1)])
    await plants.create_index("owner_id")
    await orders.create_index([("customer_id", 1), ("created_at", -1)])
    await orders.create_index([("plant_id", 1), ("status", 1), ("created_at", -1)])
    await orders.create_index("order_number")
    await order_status_history.create_index([("order_id", 1), ("created_at", 1)])

    # KYC and notifications.
    await kyc_profiles.create_index([("user_id", 1), ("purpose", 1)], unique=True)
    await notifications.create_index([("user_id", 1), ("read", 1), ("created_at", -1)])
    await audit_logs.create_index([("actor_id", 1), ("created_at", -1)])

    # Dispatch / driver / POD.
    await vehicles.create_index([("plant_id", 1), ("status", 1)])
    await driver_trips.create_index("order_id", unique=True)
    await driver_trips.create_index([("driver_id", 1), ("status", 1), ("updated_at", -1)])
    await trip_status_history.create_index([("trip_id", 1), ("created_at", 1)])
    await proof_of_delivery.create_index("trip_id", unique=True)
    await proof_of_delivery.create_index("order_id", unique=True)
    await vehicle_locations.create_index([("trip_id", 1), ("created_at", -1)])
    await vehicle_locations.create_index([("order_id", 1), ("created_at", -1)])
    await attendance.create_index([("driver_id", 1), ("date", 1)], unique=True)
    await driver_incidents.create_index([("plant_id", 1), ("status", 1), ("created_at", -1)])

    # Commercial / production modules.
    await challans.create_index("order_id", unique=True)
    await invoices.create_index("order_id")
    await payments.create_index([("order_id", 1), ("created_at", -1)])
    await production_batches.create_index([("order_id", 1), ("created_at", 1)])
    await materials.create_index([("plant_id", 1), ("name", 1)])
    await stock_movements.create_index([("plant_id", 1), ("created_at", -1)])
    await quality_tests.create_index([("plant_id", 1), ("order_id", 1), ("created_at", -1)])

    # Authenticated object metadata used for POD file authorization.
    await storage_objects.create_index("path", unique=True)
    await storage_objects.create_index([("trip_id", 1), ("purpose", 1)])
    await storage_objects.create_index([("order_id", 1), ("purpose", 1)])
    await storage_objects.create_index([("plant_id", 1), ("created_at", -1)])
