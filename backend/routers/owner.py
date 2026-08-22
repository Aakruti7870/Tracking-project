"""Plant Owner endpoints — scoped to the plants the owner owns."""
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from database import order_status_history, orders, plants
from models import RejectOrderBody
from order_service import (
    ACCEPTED,
    PENDING,
    REJECTED,
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
