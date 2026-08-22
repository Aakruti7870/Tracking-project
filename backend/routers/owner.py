"""Plant Owner endpoints — scoped to the plants the owner owns."""
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from database import next_sequence, order_status_history, orders, plants, users, vehicles, driver_trips, challans
from models import AssignDriverBody, AssignTmBody, ChallanBody, RejectOrderBody
from notifications import record_notification
from order_service import (
    ACCEPTED,
    DISPATCHED,
    DRIVER_ASSIGNED,
    PENDING,
    READY_TO_DISPATCH,
    REJECTED,
    TM_ASSIGNED,
    owner_plant_ids,
    transition_order,
)
from roles import Role
from security import current_user, require_role

router = APIRouter(prefix="/api/owner", tags=["owner"])

owner_only = require_role(Role.PLANT_OWNER.value)


async def _oid(value: str):
    try:
        return ObjectId(value)
    except Exception:
        return value


def _serialize_order(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "order_number": doc.get("order_number"),
        "customer_name": doc.get("customer_name"),
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
        "tm_number": doc.get("tm_number"),
        "driver_name": doc.get("driver_name"),
        "driver_mobile": doc.get("driver_mobile"),
        "challan_number": doc.get("challan_number"),
    }


async def _scoped_plant_ids(ctx: dict) -> list[str]:
    ids = await owner_plant_ids(ctx["user_id"])
    if not ids:
        raise HTTPException(403, "No plants linked to this account")
    return ids


@router.get("/home")
async def owner_home(ctx: dict = Depends(owner_only)):
    plant_ids = await _scoped_plant_ids(ctx)
    base = {"plant_id": {"$in": plant_ids}}
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    all_orders = await orders.find(base).to_list(1000)
    pending = [o for o in all_orders if o.get("status") == PENDING]
    dispatched = [o for o in all_orders if o.get("status") in
                  ("DISPATCHED", "EN_ROUTE", "AT_SITE", "UNLOADING", "POD_PENDING")]
    delivered = [o for o in all_orders if o.get("status") == "DELIVERED"]
    todays = [o for o in all_orders if o.get("created_at") and
              o["created_at"].replace(tzinfo=timezone.utc) >= today]

    ordered_qty = sum(o.get("quantity", 0) for o in all_orders)
    dispatched_qty = sum(o.get("quantity", 0) for o in dispatched)
    delivered_qty = sum(o.get("quantity", 0) for o in delivered)

    my_plants = await plants.find({"_id": {"$in": [await _oid(i) for i in plant_ids]}}).to_list(100)

    recent_pending = sorted(pending, key=lambda o: o.get("created_at", today), reverse=True)[:5]

    return {
        "plant_count": len(plant_ids),
        "plants": [{"id": str(p["_id"]), "name": p.get("name")} for p in my_plants],
        "cards": {
            "todays_orders": len(todays),
            "pending_approvals": len(pending),
            "ordered_qty": ordered_qty,
            "dispatched_qty": dispatched_qty,
            "delivered_qty": delivered_qty,
            "active_mixers": 0,
            "available_mixers": 0,
            "todays_revenue": 0,
            "receivables": 0,
        },
        "pending_orders": [_serialize_order(o) for o in recent_pending],
    }


@router.get("/orders")
async def owner_orders(
    status: str | None = Query(default=None),
    ctx: dict = Depends(owner_only),
):
    plant_ids = await _scoped_plant_ids(ctx)
    query: dict = {"plant_id": {"$in": plant_ids}}
    if status and status != "all":
        query["status"] = status
    docs = await orders.find(query).sort("created_at", -1).to_list(500)
    return {"orders": [_serialize_order(o) for o in docs]}


@router.get("/orders/{order_id}")
async def owner_order_detail(order_id: str, ctx: dict = Depends(owner_only)):
    plant_ids = await _scoped_plant_ids(ctx)
    order = await orders.find_one({"_id": await _oid(order_id), "plant_id": {"$in": plant_ids}})
    if not order:
        raise HTTPException(404, "Order not found")
    history = await order_status_history.find({"order_id": order_id}).sort("created_at", 1).to_list(100)
    return {
        "order": _serialize_order(order),
        "contact_person": order.get("contact_person"),
        "contact_mobile": order.get("contact_mobile"),
        "notes": order.get("notes"),
        "customer_id": order.get("customer_id"),
        "history": [
            {
                "from": h.get("from_status"),
                "to": h.get("to_status"),
                "note": h.get("note"),
                "at": h.get("created_at").isoformat() if h.get("created_at") else None,
            }
            for h in history
        ],
    }


async def _guard_owns(ctx: dict, order_id: str) -> dict:
    plant_ids = await _scoped_plant_ids(ctx)
    order = await orders.find_one({"_id": await _oid(order_id), "plant_id": {"$in": plant_ids}})
    if not order:
        raise HTTPException(404, "Order not found")
    return order


@router.post("/orders/{order_id}/approve")
async def approve_order(order_id: str, ctx: dict = Depends(owner_only)):
    order = await _guard_owns(ctx, order_id)
    await transition_order(
        order_id, ACCEPTED, ctx["user_id"],
        note="Approved by plant", notify_user_ids=[order["customer_id"]],
        event="order_approved",
    )
    return {"status": ACCEPTED}


@router.post("/orders/{order_id}/reject")
async def reject_order(order_id: str, body: RejectOrderBody, ctx: dict = Depends(owner_only)):
    order = await _guard_owns(ctx, order_id)
    await transition_order(
        order_id, REJECTED, ctx["user_id"],
        note=f"Rejected: {body.reason}", notify_user_ids=[order["customer_id"]],
        event="order_rejected",
    )
    return {"status": REJECTED}


# ---------------- Fleet & drivers ----------------

@router.get("/fleet")
async def fleet(ctx: dict = Depends(owner_only)):
    plant_ids = await _scoped_plant_ids(ctx)
    docs = await vehicles.find({"plant_id": {"$in": plant_ids}}).to_list(200)
    return {
        "vehicles": [
            {
                "id": str(v["_id"]),
                "tm_number": v.get("tm_number"),
                "capacity_m3": v.get("capacity_m3"),
                "status": v.get("status"),
                "current_order_id": v.get("current_order_id"),
            }
            for v in docs
        ]
    }


@router.get("/drivers")
async def drivers(ctx: dict = Depends(owner_only)):
    plant_ids = await _scoped_plant_ids(ctx)
    docs = await users.find({"primary_role": "driver", "plant_id": {"$in": plant_ids}}).to_list(200)
    return {
        "drivers": [
            {"id": str(d["_id"]), "name": d.get("name"), "phone": d.get("phone")}
            for d in docs
        ]
    }


# ---------------- Dispatch workflow ----------------

@router.post("/orders/{order_id}/assign-tm")
async def assign_tm(order_id: str, body: AssignTmBody, ctx: dict = Depends(owner_only)):
    order = await _guard_owns(ctx, order_id)
    if order.get("status") not in (ACCEPTED, "SCHEDULED", "PRODUCTION_COMPLETE", TM_ASSIGNED):
        raise HTTPException(409, "Order is not ready for transit mixer assignment")
    v = await vehicles.find_one({"_id": await _oid(body.vehicle_id), "plant_id": order["plant_id"]})
    if not v:
        raise HTTPException(404, "Vehicle not found for this plant")
    if v.get("status") not in ("available",) and v.get("current_order_id") != order_id:
        raise HTTPException(409, f"Vehicle is {v.get('status')} and cannot be assigned")

    await orders.update_one(
        {"_id": order["_id"]},
        {"$set": {"tm_id": str(v["_id"]), "tm_number": v.get("tm_number")}},
    )
    await vehicles.update_one(
        {"_id": v["_id"]}, {"$set": {"status": "loading", "current_order_id": order_id}}
    )
    if order.get("status") != TM_ASSIGNED:
        await transition_order(order_id, TM_ASSIGNED, ctx["user_id"],
                               note=f"TM {v.get('tm_number')} assigned")
    return {"status": TM_ASSIGNED, "tm_number": v.get("tm_number")}


@router.post("/orders/{order_id}/assign-driver")
async def assign_driver(order_id: str, body: AssignDriverBody, ctx: dict = Depends(owner_only)):
    order = await _guard_owns(ctx, order_id)
    if order.get("status") not in (TM_ASSIGNED, DRIVER_ASSIGNED):
        raise HTTPException(409, "Assign a transit mixer before a driver")
    d = await users.find_one({"_id": await _oid(body.driver_id), "primary_role": "driver",
                              "plant_id": order["plant_id"]})
    if not d:
        raise HTTPException(404, "Driver not found for this plant")

    await orders.update_one(
        {"_id": order["_id"]},
        {"$set": {"driver_id": str(d["_id"]), "driver_name": d.get("name"),
                  "driver_mobile": d.get("phone")}},
    )
    # Create/refresh the driver trip in ASSIGNED state.
    existing_trip = await driver_trips.find_one({"order_id": order_id})
    trip_doc = {
        "order_id": order_id,
        "order_number": order.get("order_number"),
        "plant_id": order["plant_id"],
        "customer_id": order.get("customer_id"),
        "driver_id": str(d["_id"]),
        "vehicle_id": order.get("tm_id"),
        "tm_number": order.get("tm_number"),
        "grade": order.get("grade"),
        "quantity": order.get("quantity"),
        "site_name": order.get("site_name"),
        "site_address": order.get("site_address"),
        "status": "ASSIGNED",
        "updated_at": datetime.now(timezone.utc),
    }
    if existing_trip:
        await driver_trips.update_one({"_id": existing_trip["_id"]}, {"$set": trip_doc})
    else:
        trip_doc["created_at"] = datetime.now(timezone.utc)
        await driver_trips.insert_one(trip_doc)

    await record_notification(str(d["_id"]), "trip_assigned",
                              f"New trip {order.get('order_number')}",
                              f"{order.get('quantity')} m³ of {order.get('grade')} to {order.get('site_name')}.")

    if order.get("status") != DRIVER_ASSIGNED:
        await transition_order(order_id, DRIVER_ASSIGNED, ctx["user_id"],
                               note=f"Driver {d.get('name')} assigned")
    return {"status": DRIVER_ASSIGNED, "driver_name": d.get("name")}


@router.post("/orders/{order_id}/challan")
async def generate_challan(order_id: str, body: ChallanBody, ctx: dict = Depends(owner_only)):
    order = await _guard_owns(ctx, order_id)
    if order.get("status") not in (DRIVER_ASSIGNED, READY_TO_DISPATCH):
        raise HTTPException(409, "Assign transit mixer & driver before generating challan")

    existing = await challans.find_one({"order_id": order_id})
    if existing:
        return {"challan": _serialize_challan(existing)}

    plant = await plants.find_one({"_id": await _oid(order["plant_id"])})
    seq = await next_sequence("challan_number")
    challan_number = f"CH-{2000 + seq}"
    now = datetime.now(timezone.utc)
    doc = {
        "challan_number": challan_number,
        "order_id": order_id,
        "order_number": order.get("order_number"),
        "plant_id": order["plant_id"],
        "plant_name": order.get("plant_name"),
        "customer_name": order.get("customer_name"),
        "site_name": order.get("site_name"),
        "site_address": order.get("site_address"),
        "grade": order.get("grade"),
        "quantity": order.get("quantity"),
        "tm_number": order.get("tm_number"),
        "driver_name": order.get("driver_name"),
        "driver_mobile": order.get("driver_mobile"),
        "batcher": body.batcher,
        "supervisor": body.supervisor,
        "quality_engineer": body.quality_engineer,
        "remarks": body.remarks,
        "created_at": now,
    }
    res = await challans.insert_one(doc)
    doc["_id"] = res.inserted_id
    await orders.update_one(
        {"_id": order["_id"]},
        {"$set": {"challan_id": str(res.inserted_id), "challan_number": challan_number}},
    )
    if order.get("status") != READY_TO_DISPATCH:
        await transition_order(order_id, READY_TO_DISPATCH, ctx["user_id"],
                               note=f"Challan {challan_number} generated")
    return {"challan": _serialize_challan(doc)}


@router.get("/orders/{order_id}/challan")
async def get_challan(order_id: str, ctx: dict = Depends(owner_only)):
    await _guard_owns(ctx, order_id)
    doc = await challans.find_one({"order_id": order_id})
    if not doc:
        raise HTTPException(404, "Challan not generated yet")
    return {"challan": _serialize_challan(doc)}


@router.post("/orders/{order_id}/dispatch")
async def dispatch_order(order_id: str, ctx: dict = Depends(owner_only)):
    order = await _guard_owns(ctx, order_id)
    if order.get("status") != READY_TO_DISPATCH:
        raise HTTPException(409, "Generate a challan before dispatching")

    now = datetime.now(timezone.utc)
    await orders.update_one({"_id": order["_id"]}, {"$set": {"dispatched_at": now}})
    if order.get("tm_id"):
        await vehicles.update_one({"_id": await _oid(order["tm_id"])}, {"$set": {"status": "dispatched"}})
    await driver_trips.update_one(
        {"order_id": order_id},
        {"$set": {"status": "DISPATCHED", "updated_at": now}},
    )
    await transition_order(
        order_id, DISPATCHED, ctx["user_id"],
        note="Dispatched — live tracking available",
        notify_user_ids=[order["customer_id"]], event="dispatched",
    )
    return {"status": DISPATCHED}


def _serialize_challan(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "challan_number": doc.get("challan_number"),
        "order_number": doc.get("order_number"),
        "plant_name": doc.get("plant_name"),
        "customer_name": doc.get("customer_name"),
        "site_name": doc.get("site_name"),
        "site_address": doc.get("site_address"),
        "grade": doc.get("grade"),
        "quantity": doc.get("quantity"),
        "tm_number": doc.get("tm_number"),
        "driver_name": doc.get("driver_name"),
        "driver_mobile": doc.get("driver_mobile"),
        "batcher": doc.get("batcher"),
        "supervisor": doc.get("supervisor"),
        "quality_engineer": doc.get("quality_engineer"),
        "remarks": doc.get("remarks"),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
    }
