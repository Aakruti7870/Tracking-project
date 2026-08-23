"""Order load planning, assignment, challan, gate-pass and dispatch APIs.

One commercial RMC order may be fulfilled by multiple transit-mixer loads. Each
load therefore has its own driver trip, challan, gate pass and delivery state.
"""
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from business_access import oid, require_business_role, require_visible_plant
from business_models import GatePassBody, OrderLoadBody
from database import (
    challans,
    driver_trips,
    gate_passes,
    next_sequence,
    order_loads,
    orders,
    plant_business_profiles,
    production_batches,
    users,
    vehicles,
)
from notifications import record_notification
from order_service import (
    DISPATCHED,
    DRIVER_ASSIGNED,
    PRODUCTION_COMPLETE,
    READY_TO_DISPATCH,
    TM_ASSIGNED,
    transition_order,
)
from roles import Role
from security import current_user

router = APIRouter(prefix="/api/loads", tags=["order-loads"])

MANAGE_ROLES = (
    Role.PLANT_OWNER.value,
    Role.ADMIN.value,
    Role.DISPATCHER.value,
    Role.CENTRAL_ADMIN.value,
)
TERMINAL_LOADS = {"DELIVERED", "CANCELLED", "DECLINED"}
ACTIVE_TRIP_STATUSES = {
    "ASSIGNED", "ACCEPTED", "LOADING", "DISPATCHED", "EN_ROUTE",
    "ARRIVED", "UNLOADING", "POD_PENDING", "POD_FINALIZING",
}


class LoadAssignmentBody(BaseModel):
    vehicle_id: str = Field(min_length=1, max_length=128)
    driver_id: str = Field(min_length=1, max_length=128)


class LoadPrepareBody(BaseModel):
    batcher: Optional[str] = Field(default=None, max_length=160)
    supervisor: Optional[str] = Field(default=None, max_length=160)
    quality_engineer: Optional[str] = Field(default=None, max_length=160)
    remarks: Optional[str] = Field(default=None, max_length=2000)


def _serialize(doc: dict) -> dict:
    out = {**doc, "id": str(doc["_id"])}
    out.pop("_id", None)
    for key, value in list(out.items()):
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
    return out


async def _order_for_ctx(order_id: str, ctx: dict) -> dict:
    order = await orders.find_one({"_id": oid(order_id)})
    if not order:
        raise HTTPException(404, "Order not found")
    await require_visible_plant(ctx, order["plant_id"])
    return order


async def _load_for_ctx(load_id: str, ctx: dict) -> dict:
    load = await order_loads.find_one({"_id": oid(load_id)})
    if not load:
        raise HTTPException(404, "Load not found")
    await require_visible_plant(ctx, load["plant_id"])
    return load


async def _validate_assignment(order: dict, load: dict, vehicle_id: str, driver_id: str):
    vehicle = await vehicles.find_one({"_id": oid(vehicle_id), "plant_id": order["plant_id"]})
    if not vehicle:
        raise HTTPException(422, "Transit mixer not found for this plant")
    if float(load.get("quantity_m3") or 0) > float(vehicle.get("capacity_m3") or 0) + 0.001:
        raise HTTPException(422, "Load quantity exceeds transit mixer capacity")
    conflicting_load = await order_loads.find_one(
        {
            "_id": {"$ne": load["_id"]},
            "vehicle_id": vehicle_id,
            "status": {"$nin": list(TERMINAL_LOADS)},
        }
    )
    if conflicting_load:
        raise HTTPException(409, "Transit mixer is already assigned to another active load")

    driver = await users.find_one(
        {
            "_id": oid(driver_id),
            "plant_id": order["plant_id"],
            "primary_role": Role.DRIVER.value,
            "status": "active",
        }
    )
    if not driver:
        raise HTTPException(422, "Driver not found for this plant")
    active_trip = await driver_trips.find_one(
        {"driver_id": driver_id, "status": {"$in": list(ACTIVE_TRIP_STATUSES)}, "load_id": {"$ne": str(load["_id"])}}
    )
    if active_trip:
        raise HTTPException(409, "Driver already has another active trip")
    return vehicle, driver


@router.get("/orders/{order_id}")
async def list_order_loads(order_id: str, ctx: dict = Depends(current_user)):
    require_business_role(ctx, *MANAGE_ROLES, Role.OPERATOR.value, Role.SUPERVISOR.value)
    order = await _order_for_ctx(order_id, ctx)
    docs = await order_loads.find({"order_id": order_id}).sort("load_number", 1).to_list(500)
    planned = round(sum(float(d.get("quantity_m3") or 0) for d in docs if d.get("status") != "CANCELLED"), 3)
    delivered = round(sum(float(d.get("delivered_quantity") or 0) for d in docs if d.get("status") == "DELIVERED"), 3)
    return {
        "order_id": order_id,
        "ordered_quantity_m3": order.get("quantity"),
        "planned_quantity_m3": planned,
        "delivered_quantity_m3": delivered,
        "remaining_quantity_m3": round(max(0, float(order.get("quantity") or 0) - planned), 3),
        "loads": [_serialize(d) for d in docs],
    }


@router.post("/orders/{order_id}")
async def create_order_load(order_id: str, body: OrderLoadBody, ctx: dict = Depends(current_user)):
    require_business_role(ctx, *MANAGE_ROLES)
    order = await _order_for_ctx(order_id, ctx)
    if order.get("status") in ("REJECTED", "CANCELLED", "DELIVERED"):
        raise HTTPException(409, f"Cannot add a load to an order that is {order.get('status')}")
    if bool(body.vehicle_id) != bool(body.driver_id):
        raise HTTPException(422, "Assign both a transit mixer and driver together")

    existing = await order_loads.find({"order_id": order_id, "status": {"$ne": "CANCELLED"}}).to_list(500)
    planned = sum(float(d.get("quantity_m3") or 0) for d in existing)
    ordered = float(order.get("quantity") or 0)
    if planned + body.quantity_m3 > ordered + 0.001:
        raise HTTPException(422, "Planned load quantity exceeds the order quantity")

    load_number = await next_sequence(f"order_load:{order_id}")
    now = datetime.now(timezone.utc)
    doc = {
        "_id": ObjectId(),
        "order_id": order_id,
        "order_number": order.get("order_number"),
        "plant_id": order["plant_id"],
        "customer_id": order.get("customer_id"),
        "load_number": load_number,
        "load_code": f"{order.get('order_number')}-L{load_number:02d}",
        "quantity_m3": body.quantity_m3,
        "vehicle_id": None,
        "tm_number": None,
        "driver_id": None,
        "driver_name": None,
        "driver_mobile": None,
        "scheduled_at": body.scheduled_at,
        "notes": body.notes,
        "status": "PLANNED",
        "created_at": now,
        "updated_at": now,
        "created_by": ctx["user_id"],
    }

    if body.vehicle_id and body.driver_id:
        vehicle, driver = await _validate_assignment(order, doc, body.vehicle_id, body.driver_id)
        doc.update(
            {
                "vehicle_id": body.vehicle_id,
                "tm_number": vehicle.get("tm_number"),
                "driver_id": body.driver_id,
                "driver_name": driver.get("name"),
                "driver_mobile": driver.get("phone"),
                "status": "ASSIGNED",
            }
        )

    await order_loads.insert_one(doc)

    rows = await order_loads.aggregate(
        [
            {"$match": {"order_id": order_id, "status": {"$ne": "CANCELLED"}}},
            {"$group": {"_id": None, "total": {"$sum": "$quantity_m3"}}},
        ]
    ).to_list(1)
    committed_total = float(rows[0]["total"] if rows else 0)
    if committed_total > ordered + 0.001:
        await order_loads.delete_one({"_id": doc["_id"]})
        raise HTTPException(409, "Order loads changed concurrently; reload and plan the remaining quantity")

    return {"load": _serialize(doc)}


@router.put("/{load_id}/assignment")
async def assign_load(load_id: str, body: LoadAssignmentBody, ctx: dict = Depends(current_user)):
    require_business_role(ctx, *MANAGE_ROLES)
    load = await _load_for_ctx(load_id, ctx)
    if load.get("status") not in ("PLANNED", "ASSIGNED"):
        raise HTTPException(409, "Load assignment can no longer be changed")
    order = await _order_for_ctx(load["order_id"], ctx)
    vehicle, driver = await _validate_assignment(order, load, body.vehicle_id, body.driver_id)
    now = datetime.now(timezone.utc)
    result = await order_loads.update_one(
        {"_id": load["_id"], "status": {"$in": ["PLANNED", "ASSIGNED"]}},
        {"$set": {
            "vehicle_id": body.vehicle_id,
            "tm_number": vehicle.get("tm_number"),
            "driver_id": body.driver_id,
            "driver_name": driver.get("name"),
            "driver_mobile": driver.get("phone"),
            "status": "ASSIGNED",
            "updated_at": now,
            "assigned_by": ctx["user_id"],
        }},
    )
    if result.matched_count != 1:
        raise HTTPException(409, "Load assignment changed concurrently; reload the load")
    updated = await order_loads.find_one({"_id": load["_id"]})
    return {"load": _serialize(updated)}


@router.post("/{load_id}/prepare")
async def prepare_load(load_id: str, body: LoadPrepareBody, ctx: dict = Depends(current_user)):
    require_business_role(ctx, *MANAGE_ROLES)
    load = await _load_for_ctx(load_id, ctx)
    order = await _order_for_ctx(load["order_id"], ctx)
    if load.get("status") == "READY_TO_DISPATCH":
        trip = await driver_trips.find_one({"load_id": load_id})
        challan = await challans.find_one({"load_id": load_id})
        return {"load": _serialize(load), "trip_id": str(trip["_id"]) if trip else None,
                "challan": _serialize(challan) if challan else None, "idempotent": True}
    if load.get("status") != "ASSIGNED":
        raise HTTPException(409, "Assign a transit mixer and driver before preparing the load")
    if order.get("status") not in (
        PRODUCTION_COMPLETE, TM_ASSIGNED, DRIVER_ASSIGNED, READY_TO_DISPATCH, DISPATCHED
    ):
        raise HTTPException(409, "Complete production before preparing delivery loads")

    produced_rows = await production_batches.aggregate([
        {"$match": {"order_id": load["order_id"]}},
        {"$group": {"_id": None, "total": {"$sum": "$quantity"}}},
    ]).to_list(1)
    produced = float(produced_rows[0]["total"] if produced_rows else 0)
    committed_loads = await order_loads.find(
        {"order_id": load["order_id"], "_id": {"$ne": load["_id"]},
         "status": {"$nin": ["PLANNED", "ASSIGNED", "CANCELLED"]}}
    ).to_list(500)
    committed = sum(float(x.get("quantity_m3") or 0) for x in committed_loads)
    if committed + float(load.get("quantity_m3") or 0) > produced * 1.02 + 0.001:
        raise HTTPException(409, "Produced quantity is not sufficient for this load")

    vehicle = await vehicles.find_one({"_id": oid(load["vehicle_id"]), "plant_id": load["plant_id"]})
    if not vehicle or (vehicle.get("status") not in ("available", "loading") and vehicle.get("current_load_id") != load_id):
        raise HTTPException(409, "Transit mixer is not available")
    active_trip = await driver_trips.find_one(
        {"driver_id": load["driver_id"], "status": {"$in": list(ACTIVE_TRIP_STATUSES)}, "load_id": {"$ne": load_id}}
    )
    if active_trip:
        raise HTTPException(409, "Driver already has another active trip")

    now = datetime.now(timezone.utc)
    trip = await driver_trips.find_one({"load_id": load_id})
    if not trip:
        trip_doc = {
            "load_id": load_id,
            "load_code": load.get("load_code"),
            "order_id": load["order_id"],
            "order_number": order.get("order_number"),
            "plant_id": load["plant_id"],
            "customer_id": order.get("customer_id"),
            "driver_id": load["driver_id"],
            "driver_mobile": load.get("driver_mobile"),
            "vehicle_id": load["vehicle_id"],
            "tm_number": load.get("tm_number"),
            "grade": order.get("grade"),
            "quantity": load.get("quantity_m3"),
            "site_name": order.get("site_name"),
            "site_address": order.get("site_address"),
            "status": "ASSIGNED",
            "created_at": now,
            "updated_at": now,
        }
        result = await driver_trips.insert_one(trip_doc)
        trip_doc["_id"] = result.inserted_id
        trip = trip_doc

    challan = await challans.find_one({"load_id": load_id})
    if not challan:
        profile = await plant_business_profiles.find_one({"plant_id": load["plant_id"]})
        prefix = (profile or {}).get("challan_prefix") or "CH"
        seq = await next_sequence(f"challan:{load['plant_id']}")
        challan_doc = {
            "challan_number": f"{prefix}-{seq:06d}",
            "load_id": load_id,
            "load_code": load.get("load_code"),
            "order_id": load["order_id"],
            "order_number": order.get("order_number"),
            "plant_id": load["plant_id"],
            "plant_name": order.get("plant_name"),
            "customer_name": order.get("customer_name"),
            "site_name": order.get("site_name"),
            "site_address": order.get("site_address"),
            "grade": order.get("grade"),
            "quantity": load.get("quantity_m3"),
            "tm_number": load.get("tm_number"),
            "driver_name": load.get("driver_name"),
            "driver_mobile": load.get("driver_mobile"),
            "batcher": body.batcher,
            "supervisor": body.supervisor,
            "quality_engineer": body.quality_engineer,
            "remarks": body.remarks,
            "created_at": now,
        }
        result = await challans.insert_one(challan_doc)
        challan_doc["_id"] = result.inserted_id
        challan = challan_doc

    await vehicles.update_one(
        {"_id": vehicle["_id"]},
        {"$set": {"status": "loading", "current_order_id": load["order_id"], "current_load_id": load_id}},
    )
    claimed = await order_loads.update_one(
        {"_id": load["_id"], "status": "ASSIGNED"},
        {"$set": {"status": "READY_TO_DISPATCH", "trip_id": str(trip["_id"]),
                   "challan_id": str(challan["_id"]), "challan_number": challan["challan_number"],
                   "updated_at": now}},
    )
    if claimed.modified_count != 1:
        raise HTTPException(409, "Load preparation changed concurrently; reload the load")

    current = order.get("status")
    await orders.update_one(
        {"_id": order["_id"]},
        {"$set": {"tm_id": load["vehicle_id"], "tm_number": load.get("tm_number"),
                   "driver_id": load["driver_id"], "driver_name": load.get("driver_name"),
                   "driver_mobile": load.get("driver_mobile"),
                   "active_load_id": load_id, "challan_number": challan["challan_number"]}},
    )
    if current == PRODUCTION_COMPLETE:
        await transition_order(load["order_id"], TM_ASSIGNED, ctx["user_id"], note=f"Load {load.get('load_code')} mixer assigned")
        current = TM_ASSIGNED
    if current == TM_ASSIGNED:
        await transition_order(load["order_id"], DRIVER_ASSIGNED, ctx["user_id"], note=f"Load {load.get('load_code')} driver assigned")
        current = DRIVER_ASSIGNED
    if current == DRIVER_ASSIGNED:
        await transition_order(load["order_id"], READY_TO_DISPATCH, ctx["user_id"], note=f"Load {load.get('load_code')} challan ready")

    await record_notification(
        load["driver_id"], "trip_assigned", f"New load {load.get('load_code')}",
        f"{load.get('quantity_m3')} m³ of {order.get('grade')} to {order.get('site_name')}.",
    )
    updated = await order_loads.find_one({"_id": load["_id"]})
    return {"load": _serialize(updated), "trip_id": str(trip["_id"]), "challan": _serialize(challan)}


@router.post("/{load_id}/dispatch")
async def dispatch_load(load_id: str, ctx: dict = Depends(current_user)):
    require_business_role(ctx, *MANAGE_ROLES)
    load = await _load_for_ctx(load_id, ctx)
    order = await _order_for_ctx(load["order_id"], ctx)
    if load.get("status") == "DISPATCHED":
        return {"status": "DISPATCHED", "idempotent": True}
    if load.get("status") != "READY_TO_DISPATCH":
        raise HTTPException(409, "Prepare the load and challan before dispatching")
    if order.get("status") not in (READY_TO_DISPATCH, DISPATCHED):
        raise HTTPException(409, f"Parent order is not dispatchable ({order.get('status')})")
    trip = await driver_trips.find_one({"load_id": load_id, "driver_id": load.get("driver_id")})
    challan = await challans.find_one({"load_id": load_id})
    gate_pass = await gate_passes.find_one({"load_id": load_id})
    if not trip or not challan:
        raise HTTPException(409, "Load trip/challan is incomplete")
    if not gate_pass:
        raise HTTPException(409, "Issue a gate pass before dispatching the load")

    now = datetime.now(timezone.utc)
    claimed = await order_loads.update_one(
        {"_id": load["_id"], "status": "READY_TO_DISPATCH"},
        {"$set": {"status": "DISPATCHED", "dispatched_at": now, "updated_at": now, "dispatched_by": ctx["user_id"]}},
    )
    if claimed.modified_count != 1:
        latest = await order_loads.find_one({"_id": load["_id"]})
        if latest and latest.get("status") == "DISPATCHED":
            return {"status": "DISPATCHED", "idempotent": True}
        raise HTTPException(409, "Load dispatch changed concurrently; reload the load")

    await driver_trips.update_one(
        {"_id": trip["_id"]}, {"$set": {"status": "DISPATCHED", "updated_at": now}}
    )
    await vehicles.update_one(
        {"_id": oid(load["vehicle_id"]), "current_load_id": load_id},
        {"$set": {"status": "dispatched"}},
    )
    await orders.update_one(
        {"_id": order["_id"]},
        {"$set": {"tm_id": load["vehicle_id"], "tm_number": load.get("tm_number"),
                   "driver_id": load["driver_id"], "driver_name": load.get("driver_name"),
                   "driver_mobile": load.get("driver_mobile"),
                   "active_load_id": load_id, "dispatched_at": now}},
    )
    if order.get("status") == READY_TO_DISPATCH:
        await transition_order(
            load["order_id"], DISPATCHED, ctx["user_id"],
            note=f"Load {load.get('load_code')} dispatched",
            notify_user_ids=[order["customer_id"]] if order.get("customer_id") else [],
            event="dispatched",
        )
    elif order.get("customer_id"):
        await record_notification(
            order["customer_id"], "load_dispatched", f"Load {load.get('load_code')} dispatched",
            f"Mixer {load.get('tm_number')} is carrying {load.get('quantity_m3')} m³ of {order.get('grade')}.",
        )
    return {"status": "DISPATCHED", "load_id": load_id, "trip_id": str(trip["_id"])}


@router.post("/{load_id}/cancel")
async def cancel_load(load_id: str, ctx: dict = Depends(current_user)):
    require_business_role(ctx, *MANAGE_ROLES)
    load = await _load_for_ctx(load_id, ctx)
    if load.get("status") not in ("PLANNED", "ASSIGNED"):
        raise HTTPException(409, "This load can no longer be cancelled")
    now = datetime.now(timezone.utc)
    result = await order_loads.update_one(
        {"_id": load["_id"], "status": {"$in": ["PLANNED", "ASSIGNED"]}},
        {"$set": {"status": "CANCELLED", "cancelled_at": now, "updated_at": now, "cancelled_by": ctx["user_id"]}},
    )
    if result.modified_count != 1:
        raise HTTPException(409, "Load cancellation changed concurrently; reload the load")
    return {"status": "CANCELLED"}


@router.post("/gate-pass")
async def create_gate_pass(body: GatePassBody, ctx: dict = Depends(current_user)):
    require_business_role(ctx, *MANAGE_ROLES, Role.SUPERVISOR.value)
    load = await _load_for_ctx(body.load_id, ctx)
    if load.get("status") not in ("READY_TO_DISPATCH", "DISPATCHED", "EN_ROUTE", "ARRIVED", "UNLOADING", "DELIVERED"):
        raise HTTPException(409, "Prepare the load before issuing a gate pass")
    existing = await gate_passes.find_one({"load_id": body.load_id})
    if existing:
        return {"gate_pass": _serialize(existing), "idempotent": True}

    seq = await next_sequence(f"gate_pass:{load['plant_id']}")
    now = datetime.now(timezone.utc)
    doc = {
        "gate_pass_number": f"GP-{seq:06d}", "load_id": body.load_id,
        "load_code": load.get("load_code"), "order_id": load.get("order_id"),
        "order_number": load.get("order_number"), "plant_id": load.get("plant_id"),
        "quantity_m3": load.get("quantity_m3"), "tm_number": load.get("tm_number"),
        "driver_id": load.get("driver_id"), "driver_name": load.get("driver_name"),
        "security_name": body.security_name, "remarks": body.remarks,
        "created_at": now, "created_by": ctx["user_id"],
    }
    result = await gate_passes.insert_one(doc)
    doc["_id"] = result.inserted_id
    await order_loads.update_one(
        {"_id": load["_id"]},
        {"$set": {"gate_pass_id": str(result.inserted_id), "gate_pass_number": doc["gate_pass_number"], "updated_at": now}},
    )
    return {"gate_pass": _serialize(doc)}
