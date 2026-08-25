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


users = db.users
sessions = db.sessions
otps = db.otps
audit_logs = db.audit_logs
notifications = db.notifications
counters = db.counters
account_deletion_requests = db.account_deletion_requests

plants = db.plants
plant_listing_requests = db.plant_listing_requests
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

attendance = db.attendance
driver_incidents = db.driver_incidents
invoices = db.invoices
payments = db.payments
plant_plan_subscriptions = db.plant_plan_subscriptions
plant_promotions = db.plant_promotions
promotion_codes = db.promotion_codes
plan_payment_orders = db.plan_payment_orders
production_batches = db.production_batches
materials = db.materials
stock_movements = db.stock_movements
quality_tests = db.quality_tests

plant_business_profiles = db.plant_business_profiles
rate_cards = db.rate_cards
mix_designs = db.mix_designs
customer_sites = db.customer_sites
quotations = db.quotations
quotation_requests = db.quotation_requests
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


async def _drop_legacy_unique_index(collection, name: str) -> None:
    info = await collection.index_information()
    spec = info.get(name)
    if spec and spec.get("unique"):
        await collection.drop_index(name)


async def ensure_indexes() -> None:
    # Auth/session lifecycle.
    await otps.create_index("expires_at", expireAfterSeconds=0)
    await sessions.create_index("expires_at", expireAfterSeconds=0)
    await sessions.create_index([("user_id", 1), ("revoked", 1)])
    await otps.create_index([("identifier_key", 1), ("created_at", -1)])
    await otps.create_index(
        "identifier_key", unique=True,
        partialFilterExpression={"consumed": False},
        name="one_active_otp_per_identifier",
    )
    await users.create_index("identifier_keys", unique=True, name="unique_login_identifier")
    await users.create_index([("plant_id", 1), ("primary_role", 1), ("status", 1)])
    await account_deletion_requests.create_index([("user_id", 1), ("status", 1), ("created_at", -1)])
    await account_deletion_requests.create_index(
        "user_id", unique=True,
        partialFilterExpression={"status": "PENDING"},
        name="one_pending_account_deletion_per_user",
    )

    # Core tenant/order access paths.
    await plants.create_index([("status", 1), ("verified", 1)])
    await plants.create_index("owner_id")
    await plants.create_index(
        "google_place_id",
        unique=True,
        partialFilterExpression={"google_place_id": {"$type": "string"}},
        name="unique_google_place_per_plant",
    )
    await plant_listing_requests.create_index(
        "google_place_id", unique=True, name="unique_google_place_listing_request"
    )
    await plant_listing_requests.create_index([("status", 1), ("updated_at", -1)])
    await plant_listing_requests.create_index([("requested_by", 1), ("updated_at", -1)])
    await orders.create_index([("customer_id", 1), ("created_at", -1)])
    await orders.create_index([("plant_id", 1), ("status", 1), ("created_at", -1)])
    await orders.create_index("order_number", unique=True)
    await orders.create_index(
        "quotation_id", unique=True,
        partialFilterExpression={"quotation_id": {"$type": "string"}},
        name="unique_order_per_quotation",
    )
    await order_status_history.create_index([("order_id", 1), ("created_at", 1)])

    await kyc_profiles.create_index([("user_id", 1), ("purpose", 1)], unique=True)
    await notifications.create_index([("user_id", 1), ("read", 1), ("created_at", -1)])
    await audit_logs.create_index([("actor_id", 1), ("created_at", -1)])

    # Multi-load migration: old builds enforced one trip, one POD and one
    # challan per order. Drop only those legacy unique order_id indexes, then
    # recreate them as non-unique. Trip/POD/load identities remain unique.
    await _drop_legacy_unique_index(driver_trips, "order_id_1")
    await _drop_legacy_unique_index(proof_of_delivery, "order_id_1")
    await _drop_legacy_unique_index(challans, "order_id_1")

    await vehicles.create_index([("plant_id", 1), ("status", 1)])
    await vehicles.create_index([("plant_id", 1), ("tm_number", 1)], unique=True)
    await driver_trips.create_index("order_id")
    await driver_trips.create_index(
        "load_id", unique=True,
        partialFilterExpression={"load_id": {"$type": "string"}},
        name="unique_driver_trip_per_load",
    )
    await driver_trips.create_index([("driver_id", 1), ("status", 1), ("updated_at", -1)])
    await trip_status_history.create_index([("trip_id", 1), ("created_at", 1)])
    await proof_of_delivery.create_index("trip_id", unique=True)
    await proof_of_delivery.create_index("order_id")
    await proof_of_delivery.create_index(
        "load_id", unique=True,
        partialFilterExpression={"load_id": {"$type": "string"}},
        name="unique_pod_per_load",
    )
    await vehicle_locations.create_index([("trip_id", 1), ("created_at", -1)])
    await vehicle_locations.create_index([("order_id", 1), ("created_at", -1)])
    await attendance.create_index([("driver_id", 1), ("date", 1)], unique=True)
    await driver_incidents.create_index([("plant_id", 1), ("status", 1), ("created_at", -1)])

    # Commercial / production modules.
    await challans.create_index("order_id")
    await challans.create_index(
        "load_id", unique=True,
        partialFilterExpression={"load_id": {"$type": "string"}},
        name="unique_challan_per_load",
    )
    await challans.create_index("challan_number", unique=True)
    await invoices.create_index("order_id")
    await invoices.create_index("invoice_number", unique=True)
    await payments.create_index([("order_id", 1), ("created_at", -1)])
    await plant_plan_subscriptions.create_index([("plant_id", 1), ("status", 1), ("ends_at", -1)])
    await plant_promotions.create_index([("plant_id", 1), ("status", 1), ("ends_at", -1)])
    await promotion_codes.create_index("code", unique=True)
    await promotion_codes.create_index([("active", 1), ("starts_at", 1), ("ends_at", 1)])
    await plan_payment_orders.create_index("order_number", unique=True)
    await plan_payment_orders.create_index([("plant_id", 1), ("status", 1), ("created_at", -1)])
    await production_batches.create_index([("order_id", 1), ("created_at", 1)])
    await production_batches.create_index(
        [("plant_id", 1), ("batch_reference", 1)], unique=True,
        partialFilterExpression={"batch_reference": {"$type": "string"}},
        name="unique_batch_reference_per_plant",
    )
    await materials.create_index([("plant_id", 1), ("name", 1)], unique=True)
    await materials.create_index(
        [("plant_id", 1), ("code", 1)], unique=True,
        partialFilterExpression={"code": {"$type": "string"}},
        name="unique_material_code_per_plant",
    )
    await stock_movements.create_index([("plant_id", 1), ("created_at", -1)])
    await stock_movements.create_index([("batch_id", 1), ("material_id", 1)])
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

    await customer_sites.create_index([("customer_id", 1), ("created_at", -1)])
    await customer_sites.create_index([("customer_id", 1), ("is_default", 1)])
    await quotations.create_index("quotation_number", unique=True)
    await quotations.create_index([("plant_id", 1), ("created_at", -1)])
    await quotations.create_index([("customer_id", 1), ("created_at", -1)])
    await quotation_requests.create_index([("customer_id", 1), ("created_at", -1)])
    await quotation_requests.create_index([("plant_id", 1), ("status", 1), ("created_at", -1)])

    await expenses.create_index([("plant_id", 1), ("expense_date", -1)])
    await expenses.create_index([("plant_id", 1), ("category", 1), ("expense_date", -1)])
    await diesel_transactions.create_index([("plant_id", 1), ("created_at", -1)])
    await diesel_transactions.create_index([("vehicle_id", 1), ("created_at", -1)])
    await staff_attendance.create_index([("user_id", 1), ("date", 1)], unique=True)
    await staff_attendance.create_index([("plant_id", 1), ("date", -1)])
    await payroll_records.create_index(
        [("plant_id", 1), ("user_id", 1), ("month", 1)], unique=True
    )

    await suppliers.create_index([("plant_id", 1), ("name", 1)], unique=True)
    await purchase_receipts.create_index(
        [("plant_id", 1), ("receipt_number", 1)], unique=True
    )
    await purchase_receipts.create_index([("plant_id", 1), ("receipt_date", -1)])

    await order_loads.create_index([("order_id", 1), ("load_number", 1)], unique=True)
    await order_loads.create_index([("plant_id", 1), ("status", 1), ("created_at", -1)])
    await order_loads.create_index([("driver_id", 1), ("status", 1), ("updated_at", -1)])
    await gate_passes.create_index("load_id", unique=True)
    await gate_passes.create_index("gate_pass_number", unique=True)
    await gate_passes.create_index([("plant_id", 1), ("created_at", -1)])

    await storage_objects.create_index("path", unique=True)
    await storage_objects.create_index([("trip_id", 1), ("purpose", 1)])
    await storage_objects.create_index([("order_id", 1), ("purpose", 1)])
    await storage_objects.create_index([("plant_id", 1), ("created_at", -1)])
