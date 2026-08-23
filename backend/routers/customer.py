"""Customer role endpoints (server-side authorized to the customer role)."""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from audit import write_audit
from database import (
    challans,
    kyc_profiles,
    notifications,
    order_loads,
    order_status_history,
    orders,
    plants,
    proof_of_delivery,
    vehicle_locations,
    next_sequence,
)
from models import CreateOrderBody
from notifications import record_notification
from order_service import CANCELLED, DRAFT, PENDING, transition_order
from roles import Role
from security import require_role

router = APIRouter(prefix="/api/customer", tags=["customer"])
customer_only = require_role(Role.CUSTOMER.value)


def _serialize_order(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]), "order_number": doc.get("order_number"),
        "plant_id": doc.get("plant_id"), "plant_name": doc.get("plant_name"),
        "grade": doc.get("grade"), "quantity": doc.get("quantity"),
        "delivered_quantity": doc.get("delivered_quantity"),
        "site_name": doc.get("site_name"), "site_address": doc.get("site_address"),
        "delivery_date": doc.get("delivery_date"), "delivery_time": doc.get("delivery_time"),
        "delivery_mode": doc.get("delivery_mode", "DELIVERY"), "status": doc.get("status"),
        "payment_status": doc.get("payment_status"), "tm_number": doc.get("tm_number"),
        "driver_name": doc.get("driver_name"), "driver_mobile": doc.get("driver_mobile"),
        "challan_number": doc.get("challan_number"), "active_load_id": doc.get("active_load_id"),
    }


def _serialize_plant(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]), "name": doc.get("name"), "city": doc.get("city"),
        "district": doc.get("district"), "address": doc.get("address"),
        "lat": doc.get("lat"), "lng": doc.get("lng"), "grades": doc.get("grades", []),
        "contact_phone": doc.get("contact_phone"), "service_area_km": doc.get("service_area_km"),
        "verified": doc.get("verified", False),
    }


def _serialize_load(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]), "load_code": doc.get("load_code"),
        "load_number": doc.get("load_number"), "quantity_m3": doc.get("quantity_m3"),
        "delivered_quantity": doc.get("delivered_quantity"), "status": doc.get("status"),
        "tm_number": doc.get("tm_number"), "driver_name": doc.get("driver_name"),
        "challan_number": doc.get("challan_number"), "gate_pass_number": doc.get("gate_pass_number"),
        "dispatched_at": doc.get("dispatched_at").isoformat() if doc.get("dispatched_at") else None,
        "delivered_at": doc.get("delivered_at").isoformat() if doc.get("delivered_at") else None,
    }


def _serialize_pod(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]), "load_id": doc.get("load_id"), "trip_id": doc.get("trip_id"),
        "receiver_name": doc.get("receiver_name"), "delivered_quantity": doc.get("delivered_quantity"),
        "remarks": doc.get("remarks"), "photo_path": doc.get("photo_path"),
        "signature": doc.get("signature"),
        "at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
    }


def _serialize_challan(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]), "load_id": doc.get("load_id"), "load_code": doc.get("load_code"),
        "challan_number": doc.get("challan_number"), "order_number": doc.get("order_number"),
        "plant_name": doc.get("plant_name"), "customer_name": doc.get("customer_name"),
        "site_name": doc.get("site_name"), "site_address": doc.get("site_address"),
        "grade": doc.get("grade"), "quantity": doc.get("quantity"), "tm_number": doc.get("tm_number"),
        "driver_name": doc.get("driver_name"), "driver_mobile": doc.get("driver_mobile"),
        "batcher": doc.get("batcher"), "supervisor": doc.get("supervisor"),
        "quality_engineer": doc.get("quality_engineer"), "remarks": doc.get("remarks"),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
    }


ACTIVE_STATUSES = {
    "ACCEPTED", "SCHEDULED", "IN_PRODUCTION", "PRODUCTION_COMPLETE", "TM_ASSIGNED",
    "DRIVER_ASSIGNED", "READY_TO_DISPATCH", "DISPATCHED", "EN_ROUTE", "AT_SITE",
    "UNLOADING", "POD_PENDING",
}
ACTIVE_LOAD_STATUSES = {"DISPATCHED", "EN_ROUTE", "ARRIVED", "UNLOADING", "POD_PENDING"}


@router.get("/home")
async def home(ctx: dict = Depends(customer_only)):
    uid = ctx["user_id"]
    user = ctx["user"]
    kyc = await kyc_profiles.find_one({"user_id": uid, "purpose": "CUSTOMER"})
    my_orders = await orders.find({"customer_id": uid}).sort("created_at", -1).to_list(50)
    active = next((o for o in my_orders if o.get("status") in ACTIVE_STATUSES), None)
    nearby = await plants.find({"status": "active", "verified": True}).limit(5).to_list(5)
    unread = await notifications.count_documents({"user_id": uid, "read": False})
    return {
        "name": user.get("name"), "kyc_status": (kyc or {}).get("status", "NOT_STARTED"),
        "active_order": _serialize_order(active) if active else None,
        "recent_orders": [_serialize_order(o) for o in my_orders[:5]],
        "nearby_plants": [_serialize_plant(p) for p in nearby], "unread_notifications": unread,
    }


@router.get("/orders")
async def list_orders(ctx: dict = Depends(customer_only)):
    docs = await orders.find({"customer_id": ctx["user_id"]}).sort("created_at", -1).to_list(200)
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
        {"$set": {"status": "PENDING", "updated_at": datetime.now(timezone.utc)}}, upsert=True,
    )
    await write_audit(uid, "kyc.start", "kyc_profile", uid, {"purpose": "CUSTOMER"})
    return {"status": "PENDING"}


async def _oid(value: str):
    try:
        return ObjectId(value)
    except Exception:
        return value


@router.post("/orders")
async def create_order(body: CreateOrderBody, ctx: dict = Depends(customer_only)):
    uid = ctx["user_id"]
    if not body.save_draft:
        kyc = await kyc_profiles.find_one({"user_id": uid, "purpose": "CUSTOMER"})
        if (kyc or {}).get("status") != "VERIFIED":
            raise HTTPException(403, "KYC_REQUIRED")
    plant = await plants.find_one({"_id": await _oid(body.plant_id)})
    if not plant or plant.get("status") != "active" or not plant.get("verified"):
        raise HTTPException(404, "Plant not available")
    if body.grade not in plant.get("grades", []):
        raise HTTPException(422, "Selected grade not offered by this plant")

    seq = await next_sequence("order_number")
    order_number = f"RMC-{1000 + seq}"
    now = datetime.now(timezone.utc)
    status = DRAFT if body.save_draft else PENDING
    doc = {
        "order_number": order_number, "customer_id": uid, "customer_name": ctx["user"].get("name"),
        "plant_id": str(plant["_id"]), "plant_name": plant.get("name"), "grade": body.grade,
        "quantity": body.quantity, "site_name": body.site_name, "site_address": body.site_address,
        "lat": body.lat, "lng": body.lng, "delivery_date": body.delivery_date,
        "delivery_time": body.delivery_time, "delivery_mode": body.delivery_mode,
        "contact_person": body.contact_person, "contact_mobile": body.contact_mobile, "notes": body.notes,
        "status": status, "payment_status": "UNPAID", "created_at": now, "updated_at": now,
    }
    res = await orders.insert_one(doc)
    oid = str(res.inserted_id)
    await order_status_history.insert_one(
        {"order_id": oid, "from_status": None, "to_status": status, "actor_id": uid,
         "note": "Order created", "created_at": now}
    )
    await write_audit(uid, "order.create", "order", oid, {"status": status, "delivery_mode": body.delivery_mode})
    if status == PENDING and plant.get("owner_id"):
        await record_notification(
            plant["owner_id"], "new_order", f"New order {order_number}",
            f"{ctx['user'].get('name')} ordered {body.quantity} m³ of {body.grade}.",
        )
    doc["_id"] = res.inserted_id
    return {"id": oid, "order": _serialize_order(doc)}


@router.get("/orders/{order_id}")
async def order_detail(order_id: str, ctx: dict = Depends(customer_only)):
    order = await orders.find_one({"_id": await _oid(order_id), "customer_id": ctx["user_id"]})
    if not order:
        raise HTTPException(404, "Order not found")
    history = await order_status_history.find({"order_id": order_id}).sort("created_at", 1).to_list(200)
    loads = await order_loads.find({"order_id": order_id}).sort("load_number", 1).to_list(500)
    pods = await proof_of_delivery.find({"order_id": order_id}).sort("created_at", 1).to_list(500)
    pod_rows = [_serialize_pod(p) for p in pods]
    return {
        "order": _serialize_order(order), "contact_person": order.get("contact_person"),
        "contact_mobile": order.get("contact_mobile"), "notes": order.get("notes"),
        "loads": [_serialize_load(x) for x in loads], "pods": pod_rows,
        "pod": pod_rows[-1] if pod_rows else None,
        "history": [
            {"from": h.get("from_status"), "to": h.get("to_status"), "note": h.get("note"),
             "at": h.get("created_at").isoformat() if h.get("created_at") else None}
            for h in history
        ],
    }


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, ctx: dict = Depends(customer_only)):
    order = await orders.find_one({"_id": await _oid(order_id), "customer_id": ctx["user_id"]})
    if not order:
        raise HTTPException(404, "Order not found")
    active_loads = await order_loads.count_documents(
        {"order_id": order_id, "status": {"$nin": ["PLANNED", "ASSIGNED", "CANCELLED"]}}
    )
    if active_loads:
        raise HTTPException(409, "Order cannot be cancelled after a delivery load is prepared")
    plant = await plants.find_one({"_id": await _oid(order["plant_id"])})
    notify = [plant["owner_id"]] if plant and plant.get("owner_id") else []
    await transition_order(order_id, CANCELLED, ctx["user_id"], note="Cancelled by customer",
                           notify_user_ids=notify, event="order_cancelled")
    await order_loads.update_many(
        {"order_id": order_id, "status": {"$in": ["PLANNED", "ASSIGNED"]}},
        {"$set": {"status": "CANCELLED", "cancelled_at": datetime.now(timezone.utc)}},
    )
    return {"status": CANCELLED}


@router.get("/plants/{plant_id}")
async def plant_detail(plant_id: str, ctx: dict = Depends(customer_only)):
    plant = await plants.find_one({"_id": await _oid(plant_id)})
    if not plant or plant.get("status") != "active" or not plant.get("verified"):
        raise HTTPException(404, "Plant not found")
    return _serialize_plant(plant)


ACTIVE_TRACK = {"DISPATCHED", "EN_ROUTE", "AT_SITE", "UNLOADING", "POD_PENDING"}


@router.get("/orders/{order_id}/tracking")
async def track_order(order_id: str, ctx: dict = Depends(customer_only)):
    order = await orders.find_one({"_id": await _oid(order_id), "customer_id": ctx["user_id"]})
    if not order:
        raise HTTPException(404, "Order not found")
    loads = await order_loads.find({"order_id": order_id}).sort("load_number", 1).to_list(500)
    active_loads = [x for x in loads if x.get("status") in ACTIVE_LOAD_STATUSES]
    tracked_loads = []
    for load in active_loads:
        latest = await vehicle_locations.find({"load_id": str(load["_id"])}).sort("created_at", -1).to_list(1)
        location = None
        route_info = None
        if latest:
            location = {"lat": latest[0]["lat"], "lng": latest[0]["lng"],
                        "at": latest[0]["created_at"].isoformat() if latest[0].get("created_at") else None}
            if order.get("lat") is not None and order.get("lng") is not None:
                from routers.maps import compute_route
                route_info = await compute_route(location["lat"], location["lng"], order["lat"], order["lng"])
        tracked_loads.append({**_serialize_load(load), "location": location, "route": route_info})

    # Legacy compatibility fields use the latest location across the order.
    active = bool(active_loads) or order.get("status") in ACTIVE_TRACK
    latest_order = await vehicle_locations.find({"order_id": order_id}).sort("created_at", -1).to_list(1) if active else []
    loc = None
    route_info = None
    if latest_order:
        loc = {"lat": latest_order[0]["lat"], "lng": latest_order[0]["lng"],
               "at": latest_order[0]["created_at"].isoformat() if latest_order[0].get("created_at") else None}
        if order.get("lat") is not None and order.get("lng") is not None:
            from routers.maps import compute_route
            route_info = await compute_route(loc["lat"], loc["lng"], order["lat"], order["lng"])
    return {
        "active": active, "status": order.get("status"), "tm_number": order.get("tm_number"),
        "driver_name": order.get("driver_name"), "driver_mobile": order.get("driver_mobile"),
        "destination": {"lat": order.get("lat"), "lng": order.get("lng"),
                        "site_name": order.get("site_name"), "address": order.get("site_address")},
        "location": loc, "route": route_info, "active_loads": tracked_loads,
        "loads": [_serialize_load(x) for x in loads],
    }


@router.get("/orders/{order_id}/challan")
async def customer_challan(order_id: str, ctx: dict = Depends(customer_only)):
    order = await orders.find_one({"_id": await _oid(order_id), "customer_id": ctx["user_id"]})
    if not order:
        raise HTTPException(404, "Order not found")
    docs = await challans.find({"order_id": order_id}).sort("created_at", -1).to_list(500)
    if not docs:
        raise HTTPException(404, "Challan not available yet")
    rows = [_serialize_challan(d) for d in docs]
    return {"challan": rows[0], "challans": rows}
