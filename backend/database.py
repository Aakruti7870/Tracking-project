"""Mongo connection, base document helpers, collections and indexes."""
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


# Core identity/security collections.
users = db.users
sessions = db.sessions
otps = db.otps
audit_logs = db.audit_logs
notifications = db.notifications
counters = db.counters

# Ordering / dispatch / delivery.
plants = db.plants
orders = db.orders
kyc_profiles = db.kyc_profiles
order_status_history = db.order_status_history
vehicles = db.vehicles
driver_trips = db.driver_trips
trip_status_history = db.trip_status_history
challans = db.challans
proof_of_delivery = db.proof_of_delivery
vehicle_locations = db.vehicle_locations
storage_objects = db.storage_objects

# Plant operations already supported by the application.
attendance = db.attendance
driver_incidents = db.driver_incidents
invoices = db.invoices
payments = db.payments
production_batches = db.production_batches
materials = db.materials
stock_movements = db.stock_movements
quality_tests = db.quality_tests

# Full business/master-data collections. These replace hard-coded/demo-only
# concepts with durable plant-scoped data.
plant_business_profiles = db.plant_business_profiles
rate_cards = db.rate_cards
mix_designs = db.mix_designs
customer_sites = db.customer_sites
quotations = db.quotations
expenses = db.expenses
diesel_transactions = db.diesel_transactions
staff_attendance = db.staff_attendance
payroll_records = db.payroll_records
suppliers = db.suppliers
purchase_receipts = db.purchase_receipts
order_loads = db.order_loads
gate_passes = db.gate_passes


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
    """Create indexes used by auth, tenant scoping, timelines and integrity.

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
    await orders.create_index("order_number", unique=True)
    await order_status_history.create_index([("order_id", 1), ("created_at", 1)])

    # KYC and notifications.
    await kyc_profiles.create_index([("user_id", 1), ("purpose", 1)], unique=True)
    await notifications.create_index([("user_id", 1), ("read", 1), ("created_at", -1)])
    await audit_logs.create_index([("actor_id", 1), ("created_at", -1)])

    # Dispatch / driver / POD.
    await vehicles.create_index([("plant_id", 1), ("status", 1)])
    await vehicles.create_index([("plant_id", 1), ("tm_number", 1)], unique=True)
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
    await challans.create_index("challan_number", unique=True)
    await invoices.create_index("order_id")
    await invoices.create_index("invoice_number", unique=True)
    await payments.create_index([("order_id", 1), ("created_at", -1)])
    await production_batches.create_index([("order_id", 1), ("created_at", 1)])
    await materials.create_index([("plant_id", 1), ("name", 1)], unique=True)
    await stock_movements.create_index([("plant_id", 1), ("created_at", -1)])
    await quality_tests.create_index([("plant_id", 1), ("order_id", 1), ("created_at", -1)])

    # Business profile and pricing/master data.
    await plant_business_profiles.create_index("plant_id", unique=True)
    await rate_cards.create_index(
        [("plant_id", 1), ("grade", 1), ("effective_from", -1)], unique=True
    )
    await rate_cards.create_index([("plant_id", 1), ("active", 1), ("grade", 1)])
    await mix_designs.create_index(
        [("plant_id", 1), ("grade", 1), ("version", 1)], unique=True
    )
    await mix_designs.create_index([("plant_id", 1), ("grade", 1), ("active", 1)])

    # Customer/commercial records.
    await customer_sites.create_index([("customer_id", 1), ("created_at", -1)])
    await customer_sites.create_index([("customer_id", 1), ("is_default", 1)])
    await quotations.create_index("quotation_number", unique=True)
    await quotations.create_index([("plant_id", 1), ("created_at", -1)])
    await quotations.create_index([("customer_id", 1), ("created_at", -1)])

    # Finance, workforce and fleet consumables.
    await expenses.create_index([("plant_id", 1), ("expense_date", -1)])
    await expenses.create_index([("plant_id", 1), ("category", 1), ("expense_date", -1)])
    await diesel_transactions.create_index([("plant_id", 1), ("created_at", -1)])
    await diesel_transactions.create_index([("vehicle_id", 1), ("created_at", -1)])
    await staff_attendance.create_index([("user_id", 1), ("date", 1)], unique=True)
    await staff_attendance.create_index([("plant_id", 1), ("date", -1)])
    await payroll_records.create_index(
        [("plant_id", 1), ("user_id", 1), ("month", 1)], unique=True
    )

    # Procurement / inventory provenance.
    await suppliers.create_index([("plant_id", 1), ("name", 1)], unique=True)
    await purchase_receipts.create_index(
        [("plant_id", 1), ("receipt_number", 1)], unique=True
    )
    await purchase_receipts.create_index([("plant_id", 1), ("receipt_date", -1)])

    # Multi-load planning foundation. Existing dispatch remains backward
    # compatible while load-aware endpoints are introduced and tested.
    await order_loads.create_index([("order_id", 1), ("load_number", 1)], unique=True)
    await order_loads.create_index([("plant_id", 1), ("status", 1), ("created_at", -1)])
    await gate_passes.create_index("load_id", unique=True)
    await gate_passes.create_index("gate_pass_number", unique=True)
    await gate_passes.create_index([("plant_id", 1), ("created_at", -1)])

    # Authenticated object metadata used for POD file authorization.
    await storage_objects.create_index("path", unique=True)
    await storage_objects.create_index([("trip_id", 1), ("purpose", 1)])
    await storage_objects.create_index([("order_id", 1), ("purpose", 1)])
    await storage_objects.create_index([("plant_id", 1), ("created_at", -1)])
