"""Authoritative order state machine.

The backend is the single source of truth for order status. Every transition
verifies the allowed edges, records history (actor + timestamp), writes an audit
entry, and emits notifications. The frontend can never set status arbitrarily.
"""
from datetime import datetime, timezone
from typing import Optional

import os

from bson import ObjectId
from fastapi import HTTPException

from audit import write_audit
from database import order_status_history, orders, plants, users
from notifications import delivery, record_notification

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

    # Idempotent customer SMS on the two milestone events (best-effort, non-blocking).
    if target in (DISPATCHED, DELIVERED):
        await _customer_sms_once(order, target)

    order["status"] = target
    return order


async def _customer_sms_once(order: dict, event: str) -> None:
    """Send exactly one SMS per (order, event). Claims the flag atomically so
    retries never duplicate; delivery failure never blocks the status update."""
    if not delivery.sms_configured or not order.get("customer_id"):
        return
    claimed = await orders.find_one_and_update(
        {"_id": order["_id"], f"sms_flags.{event}": {"$ne": True}},
        {"$set": {f"sms_flags.{event}": True}},
    )
    if not claimed:
        return  # already sent for this event
    try:
        cust = await users.find_one({"_id": ObjectId(order["customer_id"])})
        phone = cust.get("phone") if cust else None
        if not phone:
            return
        num = order.get("order_number")
        if event == DISPATCHED:
            base = os.environ.get("APP_PUBLIC_URL", "").rstrip("/")
            link = f"{base}/track/{order['_id']}" if base else ""
            tm = order.get("tm_number")
            msg = f"TrackMyRMC: Order {num} DISPATCHED"
            if tm:
                msg += f" (Mixer {tm})"
            msg += f". {order.get('quantity')} m3 {order.get('grade')} en route to {order.get('site_name') or 'your site'}."
            if link:
                msg += f" Track live: {link}"
        else:  # DELIVERED
            qty = order.get("delivered_quantity") or order.get("quantity")
            base = os.environ.get("APP_PUBLIC_URL", "").rstrip("/")
            link = f"{base}/order/{order['_id']}" if base else ""
            msg = f"TrackMyRMC: Order {num} DELIVERED. {qty} m3 {order.get('grade')} delivered successfully."
            if link:
                msg += f" View delivery proof: {link}"
            else:
                msg += " Thank you!"
        await delivery.send("sms", phone, msg)
    except Exception:  # noqa: BLE001 — never block a status update on SMS
        pass


async def owner_plant_ids(user_id: str) -> list[str]:
    docs = await plants.find({"owner_id": user_id}).to_list(100)
    return [str(d["_id"]) for d in docs]
