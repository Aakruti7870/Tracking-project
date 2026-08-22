"""Driver endpoints: trips, trip state machine, POD, attendance."""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from database import attendance, driver_incidents, driver_trips, orders, plants, proof_of_delivery, trip_status_history, vehicle_locations, vehicles
from models import GeoBody, LocationBody, PodBody, SosBody
from notifications import record_notification
from order_service import (
    AT_SITE,
    DELIVERED,
    DISPATCHED,
    EN_ROUTE,
    POD_PENDING,
    UNLOADING,
    transition_order,
)
from roles import Role
from security import current_user, require_role

router = APIRouter(prefix="/api/driver", tags=["driver"])
driver_only = require_role(Role.DRIVER.value)


async def _oid(v: str):
    try:
        return ObjectId(v)
    except Exception:
        return v


def _serialize_trip(t: dict) -> dict:
    return {
        "id": str(t["_id"]),
        "order_id": t.get("order_id"),
        "order_number": t.get("order_number"),
        "status": t.get("status"),
        "grade": t.get("grade"),
        "quantity": t.get("quantity"),
        "tm_number": t.get("tm_number"),
        "site_name": t.get("site_name"),
        "site_address": t.get("site_address"),
    }


# trip status -> (allowed current trip statuses, next order status)
STEP_MAP = {
    "start": (["DISPATCHED", "ASSIGNED", "ACCEPTED", "LOADING"], EN_ROUTE, "EN_ROUTE"),
    "arrive": (["EN_ROUTE"], AT_SITE, "ARRIVED"),
    "unload": (["ARRIVED"], UNLOADING, "UNLOADING"),
}


async def _my_trip(ctx: dict, trip_id: str) -> dict:
    t = await driver_trips.find_one({"_id": await _oid(trip_id), "driver_id": ctx["user_id"]})
    if not t:
        raise HTTPException(404, "Trip not found")
    return t


@router.get("/home")
async def home(ctx: dict = Depends(driver_only)):
    uid = ctx["user_id"]
    trips = await driver_trips.find({"driver_id": uid}).sort("updated_at", -1).to_list(200)
    active = next((t for t in trips if t.get("status") not in ("DELIVERED", "DECLINED", "CANCELLED")), None)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    done_today = [t for t in trips if t.get("status") == "DELIVERED" and t.get("updated_at") and t["updated_at"].replace(tzinfo=timezone.utc) >= today]
    att = await attendance.find_one({"driver_id": uid, "date": today.strftime("%Y-%m-%d")})
    return {
        "name": ctx["user"].get("name"),
        "vehicle": active.get("tm_number") if active else None,
        "active_trip": _serialize_trip(active) if active else None,
        "completed_today": len(done_today),
        "checked_in": bool(att and att.get("check_in") and not att.get("check_out")),
    }


@router.get("/trips")
async def trips(ctx: dict = Depends(driver_only)):
    docs = await driver_trips.find({"driver_id": ctx["user_id"]}).sort("updated_at", -1).to_list(500)
    return {"trips": [_serialize_trip(t) for t in docs]}


@router.get("/trips/{trip_id}")
async def trip_detail(trip_id: str, ctx: dict = Depends(driver_only)):
    t = await _my_trip(ctx, trip_id)
    pod = await proof_of_delivery.find_one({"trip_id": trip_id})
    return {
        "trip": _serialize_trip(t),
        "site_address": t.get("site_address"),
        "pod": {"receiver_name": pod.get("receiver_name"), "delivered_quantity": pod.get("delivered_quantity")} if pod else None,
    }


async def _advance(ctx: dict, trip_id: str, step: str):
    t = await _my_trip(ctx, trip_id)
    allowed, order_target, trip_target = STEP_MAP[step]
    if t.get("status") not in allowed:
        raise HTTPException(409, f"Cannot {step} a trip that is {t.get('status')}")
    now = datetime.now(timezone.utc)
    changed = await driver_trips.update_one(
        {"_id": t["_id"], "driver_id": ctx["user_id"], "status": {"$in": allowed}},
        {"$set": {"status": trip_target, "updated_at": now}},
    )
    if changed.modified_count != 1:
        raise HTTPException(409, "Trip status changed concurrently; refresh and retry")
    order = await orders.find_one({"_id": await _oid(t["order_id"])})
    notify = [order["customer_id"]] if order else []
    try:
        await transition_order(t["order_id"], order_target, ctx["user_id"], note=f"Driver: {trip_target.replace('_',' ').title()}", notify_user_ids=notify, event=f"trip_{trip_target.lower()}")
    except Exception:
        # Standalone Mongo deployments may not support transactions. Roll back
        # only if nobody has advanced this trip since our compare-and-set.
        await driver_trips.update_one(
            {"_id": t["_id"], "status": trip_target},
            {"$set": {"status": t.get("status"), "updated_at": now, "sync_error": True}},
        )
        raise
    await trip_status_history.insert_one({"trip_id": trip_id, "from_status": t.get("status"), "to_status": trip_target, "actor_id": ctx["user_id"], "created_at": now})
    return {"status": trip_target}


@router.post("/trips/{trip_id}/start")
async def start(trip_id: str, ctx: dict = Depends(driver_only)):
    return await _advance(ctx, trip_id, "start")


@router.post("/trips/{trip_id}/arrive")
async def arrive(trip_id: str, ctx: dict = Depends(driver_only)):
    return await _advance(ctx, trip_id, "arrive")


@router.post("/trips/{trip_id}/unload")
async def unload(trip_id: str, ctx: dict = Depends(driver_only)):
    return await _advance(ctx, trip_id, "unload")


@router.post("/trips/{trip_id}/pod")
async def submit_pod(trip_id: str, body: PodBody, ctx: dict = Depends(driver_only)):
    t = await _my_trip(ctx, trip_id)
    existing = await proof_of_delivery.find_one({"trip_id": trip_id})
    if t.get("status") == DELIVERED and existing:
        if (existing.get("receiver_name") == body.receiver_name and
                existing.get("delivered_quantity") == body.delivered_quantity):
            return {"status": DELIVERED, "idempotent": True}
        raise HTTPException(409, "Proof of delivery is already finalized")
    if t.get("status") not in ("UNLOADING", "ARRIVED", "POD_PENDING"):
        raise HTTPException(409, "Start unloading before submitting proof of delivery")
    now = datetime.now(timezone.utc)
    order = await orders.find_one({"_id": await _oid(t["order_id"])})
    if not order or str(order.get("_id")) != t.get("order_id"):
        raise HTTPException(409, "Trip order is unavailable")
    ordered_quantity = float(order.get("quantity") or 0)
    if body.delivered_quantity > ordered_quantity * 1.10:
        raise HTTPException(422, "Delivered quantity exceeds allowed order tolerance")
    claimed = await driver_trips.update_one(
        {"_id": t["_id"], "driver_id": ctx["user_id"], "order_id": t["order_id"],
         "status": {"$in": ["UNLOADING", "ARRIVED", "POD_PENDING"]}},
        {"$set": {"status": "POD_FINALIZING", "updated_at": now}},
    )
    if claimed.modified_count != 1:
        raise HTTPException(409, "Delivery is already being finalized")
    pod_doc = {
        "trip_id": trip_id,
        "order_id": t["order_id"],
        "driver_id": ctx["user_id"],
        "receiver_name": body.receiver_name,
        "delivered_quantity": body.delivered_quantity,
        "remarks": body.remarks,
        "photo_path": body.photo_path,
        "signature": body.signature,
        "lat": body.lat,
        "lng": body.lng,
        "created_at": now,
    }
    try:
        await proof_of_delivery.insert_one(pod_doc)
    except DuplicateKeyError:
        await driver_trips.update_one({"_id": t["_id"], "status": "POD_FINALIZING"}, {"$set": {"status": t.get("status")}})
        raise HTTPException(409, "Proof of delivery is already finalized")

    notify = [order["customer_id"]] if order else []
    # UNLOADING -> POD_PENDING -> DELIVERED (order), trip -> DELIVERED
    try:
        if order.get("status") == UNLOADING:
            await transition_order(t["order_id"], POD_PENDING, ctx["user_id"], note="POD submitted")
        await transition_order(t["order_id"], DELIVERED, ctx["user_id"], note=f"Delivered — received by {body.receiver_name}", notify_user_ids=notify, event="delivered")
    except Exception:
        await proof_of_delivery.delete_one({"trip_id": trip_id, "created_at": now})
        await driver_trips.update_one({"_id": t["_id"], "status": "POD_FINALIZING"}, {"$set": {"status": t.get("status"), "sync_error": True}})
        raise
    await orders.update_one({"_id": await _oid(t["order_id"])}, {"$set": {"delivered_quantity": body.delivered_quantity}})
    await driver_trips.update_one({"_id": t["_id"]}, {"$set": {"status": DELIVERED, "updated_at": now}})
    if t.get("vehicle_id"):
        await vehicles.update_one({"_id": await _oid(t["vehicle_id"])}, {"$set": {"status": "available", "current_order_id": None}})
    await write_audit(ctx["user_id"], "pod.submit", "order", t["order_id"])
    return {"status": DELIVERED}


# ---------------- Attendance ----------------

@router.get("/attendance")
async def get_attendance(ctx: dict = Depends(driver_only)):
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    a = await attendance.find_one({"driver_id": ctx["user_id"], "date": date})
    if not a:
        return {"date": date, "check_in": None, "check_out": None}
    return {
        "date": date,
        "check_in": a.get("check_in").isoformat() if a.get("check_in") else None,
        "check_out": a.get("check_out").isoformat() if a.get("check_out") else None,
    }


@router.post("/attendance/checkin")
async def checkin(body: GeoBody, ctx: dict = Depends(driver_only)):
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing = await attendance.find_one({"driver_id": ctx["user_id"], "date": date})
    if existing and existing.get("check_in"):
        raise HTTPException(409, "Already checked in today")
    now = datetime.now(timezone.utc)
    await attendance.update_one(
        {"driver_id": ctx["user_id"], "date": date},
        {"$set": {"check_in": now, "in_lat": body.lat, "in_lng": body.lng}},
        upsert=True,
    )
    return {"check_in": now.isoformat()}


@router.post("/attendance/checkout")
async def checkout(body: GeoBody, ctx: dict = Depends(driver_only)):
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing = await attendance.find_one({"driver_id": ctx["user_id"], "date": date})
    if not existing or not existing.get("check_in"):
        raise HTTPException(409, "Check in first")
    now = datetime.now(timezone.utc)
    await attendance.update_one({"_id": existing["_id"]}, {"$set": {"check_out": now}})
    return {"check_out": now.isoformat()}


# ---------------- SOS / Incidents ----------------

@router.post("/sos")
async def raise_sos(body: SosBody, ctx: dict = Depends(driver_only)):
    uid = ctx["user_id"]
    active = await driver_trips.find_one(
        {"driver_id": uid, "status": {"$nin": ["DELIVERED", "DECLINED", "CANCELLED"]}}
    )
    plant_id = ctx["user"].get("plant_id") or (active.get("plant_id") if active else None)
    now = datetime.now(timezone.utc)
    doc = {
        "driver_id": uid,
        "driver_name": ctx["user"].get("name"),
        "plant_id": plant_id,
        "trip_id": str(active["_id"]) if active else None,
        "order_number": active.get("order_number") if active else None,
        "vehicle": active.get("tm_number") if active else None,
        "type": body.type,
        "remark": body.remark,
        "lat": body.lat,
        "lng": body.lng,
        "status": "OPEN",
        "created_at": now,
    }
    res = await driver_incidents.insert_one(doc)
    await write_audit(uid, "driver.sos", "incident", str(res.inserted_id), {"type": body.type})

    # Notify the plant owner (durable in-app record — not a fake claim).
    notified = False
    if plant_id:
        plant = await plants.find_one({"_id": await _oid(plant_id)})
        if plant and plant.get("owner_id"):
            await record_notification(
                plant["owner_id"], "sos",
                f"SOS: {body.type} — {ctx['user'].get('name')}",
                body.remark or f"{ctx['user'].get('name')} raised a {body.type} alert.",
            )
            notified = True
    return {"id": str(res.inserted_id), "status": "OPEN", "supervisor_notified": notified}


@router.get("/sos")
async def my_sos(ctx: dict = Depends(driver_only)):
    docs = await driver_incidents.find({"driver_id": ctx["user_id"]}).sort("created_at", -1).to_list(100)
    return {"incidents": [
        {"id": str(d["_id"]), "type": d.get("type"), "status": d.get("status"),
         "remark": d.get("remark"), "order_number": d.get("order_number"),
         "created_at": d.get("created_at").isoformat() if d.get("created_at") else None}
        for d in docs
    ]}


# ---------------- Live location ----------------

@router.post("/trips/{trip_id}/location")
async def post_location(trip_id: str, body: LocationBody, ctx: dict = Depends(driver_only)):
    t = await _my_trip(ctx, trip_id)
    if t.get("status") in ("DELIVERED", "DECLINED", "CANCELLED"):
        raise HTTPException(409, "Trip is not active")
    now = datetime.now(timezone.utc)
    doc = {"trip_id": trip_id, "order_id": t.get("order_id"), "driver_id": ctx["user_id"],
           "vehicle_id": t.get("vehicle_id"), "lat": body.lat, "lng": body.lng,
           "accuracy": body.accuracy, "created_at": now}
    await vehicle_locations.insert_one(doc)
    await driver_trips.update_one({"_id": t["_id"]}, {"$set": {"last_lat": body.lat, "last_lng": body.lng, "last_location_at": now}})
    return {"ok": True}
