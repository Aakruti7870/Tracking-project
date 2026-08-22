"""Authoritative order state machine.

The backend is the single source of truth for order status. Every transition
verifies the allowed edges, records history (actor + timestamp), writes an audit
entry, and emits notifications. The frontend can never set status arbitrarily.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import os

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument

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
    """Perform a validated, compare-and-set status transition.

    The status field is included in the update predicate so two concurrent
    transitions cannot both succeed against the same previous state.
    """
    order = await orders.find_one({"_id": await _oid(order_id)})
    if not order:
        raise HTTPException(404, "Order not found")

    current = order.get("status")
    if current == target:
        # Replaying a milestone transition is harmless and gives a previously
        # failed provider delivery one safe chance to retry.
        if target in (DISPATCHED, DELIVERED):
            await _customer_sms_once(order, target)
        return order
    if not can_transition(current, target):
        raise HTTPException(409, f"Cannot move order from {current} to {target}")

    now = datetime.now(timezone.utc)
    updated = await orders.find_one_and_update(
        {"_id": order["_id"], "status": current},
        {"$set": {"status": target, "updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        # Another request changed the order between read and write. Treat a
        # same-target winner as idempotent; otherwise reject the stale request.
        latest = await orders.find_one({"_id": order["_id"]})
        if latest and latest.get("status") == target:
            if target in (DISPATCHED, DELIVERED):
                await _customer_sms_once(latest, target)
            return latest
        latest_status = latest.get("status") if latest else "UNKNOWN"
        raise HTTPException(
            409,
            f"Order status changed concurrently from {current} to {latest_status}; retry from latest state",
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
    await write_audit(
        actor_id,
        f"order.{target.lower()}",
        "order",
        str(order["_id"]),
        {"from": current, "to": target},
    )

    for uid in notify_user_ids or []:
        await record_notification(
            uid,
            event or f"order_{target.lower()}",
            f"Order {updated.get('order_number')} {target.replace('_', ' ').title()}",
            note or f"Your order is now {target.replace('_', ' ').title()}.",
        )

    # Customer SMS on milestone events. A failed provider attempt is marked
    # failed and can be retried by an idempotent replay without duplicating a
    # successfully recorded send.
    if target in (DISPATCHED, DELIVERED):
        await _customer_sms_once(updated, target)

    return updated


async def _customer_sms_once(order: dict, event: str) -> None:
    """Send at most one concurrently active SMS per (order,event).

    Successful sends are durable (`status=sent`). Failed attempts are durable
    (`status=failed`) and may be retried. A stale `sending` claim can be taken
    over after two minutes to recover from a worker crash.
    """
    if not delivery.sms_configured or not order.get("customer_id"):
        return

    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(minutes=2)
    flag = f"sms_flags.{event}"
    claimed = await orders.find_one_and_update(
        {
            "_id": order["_id"],
            flag: {"$ne": True},  # backwards-compatible with legacy boolean flag
            "$or": [
                {f"{flag}.status": {"$exists": False}},
                {f"{flag}.status": "failed"},
                {f"{flag}.status": "sending", f"{flag}.claimed_at": {"$lt": stale_before}},
            ],
        },
        {"$set": {f"{flag}.status": "sending", f"{flag}.claimed_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if not claimed:
        return

    try:
        cust = await users.find_one({"_id": ObjectId(order["customer_id"])})
        phone = cust.get("phone") if cust else None
        if not phone:
            await orders.update_one(
                {"_id": order["_id"]},
                {"$set": {f"{flag}.status": "failed", f"{flag}.failed_at": now,
                           f"{flag}.reason": "missing_customer_phone"}},
            )
            return

        num = order.get("order_number")
        if event == DISPATCHED:
            base = os.environ.get("APP_PUBLIC_URL", "").rstrip("/")
            link = f"{base}/track/{order['_id']}" if base else ""
            tm = order.get("tm_number")
            msg = f"TrackMyRMC: Order {num} DISPATCHED"
            if tm:
                msg += f" (Mixer {tm})"
            msg += (
                f". {order.get('quantity')} m3 {order.get('grade')} en route to "
                f"{order.get('site_name') or 'your site'}."
            )
            if link:
                msg += f" Track live: {link}"
        else:  # DELIVERED
            qty = order.get("delivered_quantity") or order.get("quantity")
            base = os.environ.get("APP_PUBLIC_URL", "").rstrip("/")
            link = f"{base}/order/{order['_id']}" if base else ""
            msg = (
                f"TrackMyRMC: Order {num} DELIVERED. {qty} m3 {order.get('grade')} "
                "delivered successfully."
            )
            if link:
                msg += f" View delivery proof: {link}"
            else:
                msg += " Thank you!"

        sent = await delivery.send("sms", phone, msg)
        if sent:
            await orders.update_one(
                {"_id": order["_id"]},
                {
                    "$set": {f"{flag}.status": "sent", f"{flag}.sent_at": datetime.now(timezone.utc)},
                    "$unset": {f"{flag}.reason": "", f"{flag}.failed_at": ""},
                },
            )
        else:
            await orders.update_one(
                {"_id": order["_id"]},
                {"$set": {f"{flag}.status": "failed", f"{flag}.failed_at": datetime.now(timezone.utc),
                           f"{flag}.reason": "provider_delivery_failed"}},
            )
    except Exception:  # noqa: BLE001 — never block an order transition on SMS
        await orders.update_one(
            {"_id": order["_id"]},
            {"$set": {f"{flag}.status": "failed", f"{flag}.failed_at": datetime.now(timezone.utc),
                       f"{flag}.reason": "unexpected_delivery_error"}},
        )


async def owner_plant_ids(user_id: str) -> list[str]:
    docs = await plants.find({"owner_id": user_id}).to_list(100)
    return [str(d["_id"]) for d in docs]
