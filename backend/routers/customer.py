"""Customer role endpoints (server-side authorized to the customer role)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from audit import write_audit
from database import kyc_profiles, notifications, orders, plants
from roles import Role
from security import current_user, require_role

router = APIRouter(prefix="/api/customer", tags=["customer"])

customer_only = require_role(Role.CUSTOMER.value)


def _serialize_order(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "order_number": doc.get("order_number"),
        "plant_id": doc.get("plant_id"),
        "plant_name": doc.get("plant_name"),
        "grade": doc.get("grade"),
        "quantity": doc.get("quantity"),
        "site_name": doc.get("site_name"),
        "site_address": doc.get("site_address"),
        "delivery_date": doc.get("delivery_date"),
        "delivery_time": doc.get("delivery_time"),
        "status": doc.get("status"),
        "payment_status": doc.get("payment_status"),
    }


def _serialize_plant(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "name": doc.get("name"),
        "city": doc.get("city"),
        "district": doc.get("district"),
        "address": doc.get("address"),
        "lat": doc.get("lat"),
        "lng": doc.get("lng"),
        "grades": doc.get("grades", []),
        "contact_phone": doc.get("contact_phone"),
        "service_area_km": doc.get("service_area_km"),
        "verified": doc.get("verified", False),
    }


ACTIVE_STATUSES = {
    "ACCEPTED", "SCHEDULED", "IN_PRODUCTION", "PRODUCTION_COMPLETE",
    "TM_ASSIGNED", "DRIVER_ASSIGNED", "READY_TO_DISPATCH", "DISPATCHED",
    "EN_ROUTE", "AT_SITE", "UNLOADING", "POD_PENDING",
}


@router.get("/home")
async def home(ctx: dict = Depends(customer_only)):
    uid = ctx["user_id"]
    user = ctx["user"]
    kyc = await kyc_profiles.find_one({"user_id": uid, "purpose": "CUSTOMER"})
    my_orders = await orders.find({"customer_id": uid}).sort("created_at", -1).to_list(50)

    active = next((o for o in my_orders if o.get("status") in ACTIVE_STATUSES), None)
    recent = my_orders[:5]
    nearby = await plants.find({"status": "active", "verified": True}).limit(5).to_list(5)
    unread = await notifications.count_documents({"user_id": uid, "read": False})

    return {
        "name": user.get("name"),
        "kyc_status": (kyc or {}).get("status", "NOT_STARTED"),
        "active_order": _serialize_order(active) if active else None,
        "recent_orders": [_serialize_order(o) for o in recent],
        "nearby_plants": [_serialize_plant(p) for p in nearby],
        "unread_notifications": unread,
    }


@router.get("/orders")
async def list_orders(ctx: dict = Depends(customer_only)):
    uid = ctx["user_id"]
    docs = await orders.find({"customer_id": uid}).sort("created_at", -1).to_list(200)
    return {"orders": [_serialize_order(o) for o in docs]}


@router.get("/plants")
async def nearby_plants(ctx: dict = Depends(customer_only)):
    docs = await plants.find({"status": "active", "verified": True}).to_list(200)
    return {"plants": [_serialize_plant(p) for p in docs]}


@router.get("/kyc")
async def get_kyc(ctx: dict = Depends(customer_only)):
    kyc = await kyc_profiles.find_one({"user_id": ctx["user_id"], "purpose": "CUSTOMER"})
    return {"status": (kyc or {}).get("status", "NOT_STARTED")}


@router.post("/kyc/start")
async def start_kyc(ctx: dict = Depends(customer_only)):
    uid = ctx["user_id"]
    existing = await kyc_profiles.find_one({"user_id": uid, "purpose": "CUSTOMER"})
    if existing and existing.get("status") == "VERIFIED":
        raise HTTPException(409, "KYC already verified")
    await kyc_profiles.update_one(
        {"user_id": uid, "purpose": "CUSTOMER"},
        {"$set": {"status": "PENDING", "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    await write_audit(uid, "kyc.start", "kyc_profile", uid, {"purpose": "CUSTOMER"})
    return {"status": "PENDING"}
