"""Order load planning and gate-pass records.

RMC orders may require several transit-mixer loads. This module gives each load
its own durable identity, quantity and assignment so the order is not forced
into a one-order/one-mixer data model.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from business_access import oid, require_business_role, require_visible_plant
from business_models import GatePassBody, OrderLoadBody
from database import gate_passes, next_sequence, order_loads, orders, users, vehicles
from roles import Role
from security import current_user

router = APIRouter(prefix="/api/loads", tags=["order-loads"])

MANAGE_ROLES = (
    Role.PLANT_OWNER.value,
    Role.ADMIN.value,
    Role.DISPATCHER.value,
    Role.CENTRAL_ADMIN.value,
)


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


@router.get("/orders/{order_id}")
async def list_order_loads(order_id: str, ctx: dict = Depends(current_user)):
    require_business_role(ctx, *MANAGE_ROLES, Role.OPERATOR.value, Role.SUPERVISOR.value)
    order = await _order_for_ctx(order_id, ctx)
    docs = await order_loads.find({"order_id": order_id}).sort("load_number", 1).to_list(500)
    planned = round(sum(float(d.get("quantity_m3") or 0) for d in docs if d.get("status") != "CANCELLED"), 3)
    return {
        "order_id": order_id,
        "ordered_quantity_m3": order.get("quantity"),
        "planned_quantity_m3": planned,
        "remaining_quantity_m3": round(max(0, float(order.get("quantity") or 0) - planned), 3),
        "loads": [_serialize(d) for d in docs],
    }


@router.post("/orders/{order_id}")
async def create_order_load(
    order_id: str,
    body: OrderLoadBody,
    ctx: dict = Depends(current_user),
):
    require_business_role(ctx, *MANAGE_ROLES)
    order = await _order_for_ctx(order_id, ctx)
    if order.get("status") in ("REJECTED", "CANCELLED", "DELIVERED"):
        raise HTTPException(409, f"Cannot add a load to an order that is {order.get('status')}")

    existing = await order_loads.find({"order_id": order_id, "status": {"$ne": "CANCELLED"}}).to_list(500)
    planned = sum(float(d.get("quantity_m3") or 0) for d in existing)
    ordered = float(order.get("quantity") or 0)
    if planned + body.quantity_m3 > ordered + 0.001:
        raise HTTPException(422, "Planned load quantity exceeds the order quantity")

    vehicle = None
    driver = None
    if body.vehicle_id:
        vehicle = await vehicles.find_one({"_id": oid(body.vehicle_id), "plant_id": order["plant_id"]})
        if not vehicle:
            raise HTTPException(422, "Transit mixer not found for this plant")
        if body.quantity_m3 > float(vehicle.get("capacity_m3") or 0) + 0.001:
            raise HTTPException(422, "Load quantity exceeds transit mixer capacity")
    if body.driver_id:
        driver = await users.find_one(
            {"_id": oid(body.driver_id), "plant_id": order["plant_id"], "primary_role": Role.DRIVER.value, "status": "active"}
        )
        if not driver:
            raise HTTPException(422, "Driver not found for this plant")

    load_number = await next_sequence(f"order_load:{order_id}")
    now = datetime.now(timezone.utc)
    status = "ASSIGNED" if vehicle and driver else "PLANNED"
    doc = {
        "order_id": order_id,
        "order_number": order.get("order_number"),
        "plant_id": order["plant_id"],
        "customer_id": order.get("customer_id"),
        "load_number": load_number,
        "load_code": f"{order.get('order_number')}-L{load_number:02d}",
        "quantity_m3": body.quantity_m3,
        "vehicle_id": body.vehicle_id,
        "tm_number": vehicle.get("tm_number") if vehicle else None,
        "driver_id": body.driver_id,
        "driver_name": driver.get("name") if driver else None,
        "scheduled_at": body.scheduled_at,
        "notes": body.notes,
        "status": status,
        "created_at": now,
        "updated_at": now,
        "created_by": ctx["user_id"],
    }
    result = await order_loads.insert_one(doc)
    doc["_id"] = result.inserted_id
    return {"load": _serialize(doc)}


@router.post("/{load_id}/cancel")
async def cancel_load(load_id: str, ctx: dict = Depends(current_user)):
    require_business_role(ctx, *MANAGE_ROLES)
    load = await order_loads.find_one({"_id": oid(load_id)})
    if not load:
        raise HTTPException(404, "Load not found")
    await require_visible_plant(ctx, load["plant_id"])
    if load.get("status") not in ("PLANNED", "ASSIGNED"):
        raise HTTPException(409, "This load can no longer be cancelled")
    now = datetime.now(timezone.utc)
    await order_loads.update_one(
        {"_id": load["_id"], "status": {"$in": ["PLANNED", "ASSIGNED"]}},
        {"$set": {"status": "CANCELLED", "cancelled_at": now, "updated_at": now, "cancelled_by": ctx["user_id"]}},
    )
    return {"status": "CANCELLED"}


@router.post("/gate-pass")
async def create_gate_pass(body: GatePassBody, ctx: dict = Depends(current_user)):
    require_business_role(ctx, *MANAGE_ROLES, Role.SUPERVISOR.value)
    load = await order_loads.find_one({"_id": oid(body.load_id)})
    if not load:
        raise HTTPException(404, "Load not found")
    await require_visible_plant(ctx, load["plant_id"])
    if not load.get("vehicle_id") or not load.get("driver_id"):
        raise HTTPException(409, "Assign a transit mixer and driver before issuing a gate pass")
    if load.get("status") == "CANCELLED":
        raise HTTPException(409, "Cannot issue a gate pass for a cancelled load")
    existing = await gate_passes.find_one({"load_id": body.load_id})
    if existing:
        return {"gate_pass": _serialize(existing), "idempotent": True}

    seq = await next_sequence(f"gate_pass:{load['plant_id']}")
    now = datetime.now(timezone.utc)
    doc = {
        "gate_pass_number": f"GP-{seq:06d}",
        "load_id": body.load_id,
        "load_code": load.get("load_code"),
        "order_id": load.get("order_id"),
        "order_number": load.get("order_number"),
        "plant_id": load.get("plant_id"),
        "quantity_m3": load.get("quantity_m3"),
        "tm_number": load.get("tm_number"),
        "driver_id": load.get("driver_id"),
        "driver_name": load.get("driver_name"),
        "security_name": body.security_name,
        "remarks": body.remarks,
        "created_at": now,
        "created_by": ctx["user_id"],
    }
    result = await gate_passes.insert_one(doc)
    doc["_id"] = result.inserted_id
    await order_loads.update_one(
        {"_id": load["_id"]},
        {"$set": {"gate_pass_id": str(result.inserted_id), "gate_pass_number": doc["gate_pass_number"], "updated_at": now}},
    )
    return {"gate_pass": _serialize(doc)}
