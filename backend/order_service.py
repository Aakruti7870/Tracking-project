"""Authoritative order state machine.

The backend is the single source of truth for order status. Every transition
verifies the allowed edges, records history (actor + timestamp), writes an audit
entry, and emits notifications. The frontend can never set status arbitrarily.
"""
from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException

from audit import write_audit
from database import order_status_history, orders, plants
from notifications import record_notification

# --- States ---
DRAFT = "DRAFT"
PENDING = "PENDING"
ACCEPTED = "ACCEPTED"
REJECTED = "REJECTED"
SCHEDULED = "SCHEDULED"
IN_PRODUCTION = "IN_PRODUCTION"
PRODUCTION_COMPLETE = "PRODUCTION_COMPLETE"
TM_ASSIGNED = "TM_ASSIGNED"
DRIVER_ASSIGNED = "DRIVER_ASSIGNED"
READY_TO_DISPATCH = "READY_TO_DISPATCH"
DISPATCHED = "DISPATCHED"
EN_ROUTE = "EN_ROUTE"
AT_SITE = "AT_SITE"
UNLOADING = "UNLOADING"
POD_PENDING = "POD_PENDING"
DELIVERED = "DELIVERED"
CANCELLED = "CANCELLED"

# Allowed transitions (edges implemented so far + placeholders for later phases).
TRANSITIONS: dict[str, set[str]] = {
    DRAFT: {PENDING, CANCELLED},
    PENDING: {ACCEPTED, REJECTED, CANCELLED},
    ACCEPTED: {SCHEDULED, IN_PRODUCTION, TM_ASSIGNED, CANCELLED},
    SCHEDULED: {IN_PRODUCTION, TM_ASSIGNED, CANCELLED},
    IN_PRODUCTION: {PRODUCTION_COMPLETE, CANCELLED},
    PRODUCTION_COMPLETE: {TM_ASSIGNED, CANCELLED},
    TM_ASSIGNED: {DRIVER_ASSIGNED, CANCELLED},
    DRIVER_ASSIGNED: {READY_TO_DISPATCH, CANCELLED},
    READY_TO_DISPATCH: {DISPATCHED, CANCELLED},
    DISPATCHED: {EN_ROUTE},
    EN_ROUTE: {AT_SITE},
    AT_SITE: {UNLOADING},
    UNLOADING: {POD_PENDING},
    POD_PENDING: {DELIVERED},
    DELIVERED: set(),
    REJECTED: set(),
    CANCELLED: set(),
}

# Customer-facing status label helper reused by clients if needed.
TERMINAL = {DELIVERED, REJECTED, CANCELLED}


def can_transition(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, set())


async def _oid(value: str):
    try:
        return ObjectId(value)
    except Exception:
        return value


async def transition_order(
    order_id: str,
    target: str,
    actor_id: str,
    note: Optional[str] = None,
    notify_user_ids: Optional[list[str]] = None,
    event: Optional[str] = None,
) -> dict:
    """Perform a validated status transition. Returns the updated order doc."""
    order = await orders.find_one({"_id": await _oid(order_id)})
    if not order:
        raise HTTPException(404, "Order not found")

    current = order.get("status")
    if current == target:
        return order
    if not can_transition(current, target):
        raise HTTPException(409, f"Cannot move order from {current} to {target}")

    now = datetime.now(timezone.utc)
    await orders.update_one(
        {"_id": order["_id"]},
        {"$set": {"status": target, "updated_at": now}},
    )
    await order_status_history.insert_one(
        {
            "order_id": str(order["_id"]),
            "from_status": current,
            "to_status": target,
            "actor_id": actor_id,
            "note": note,
            "created_at": now,
        }
    )
    await write_audit(actor_id, f"order.{target.lower()}", "order", str(order["_id"]),
                      {"from": current, "to": target})

    for uid in notify_user_ids or []:
        await record_notification(
            uid,
            event or f"order_{target.lower()}",
            f"Order {order.get('order_number')} {target.replace('_', ' ').title()}",
            note or f"Your order is now {target.replace('_', ' ').title()}.",
        )

    order["status"] = target
    return order


async def owner_plant_ids(user_id: str) -> list[str]:
    docs = await plants.find({"owner_id": user_id}).to_list(100)
    return [str(d["_id"]) for d in docs]
