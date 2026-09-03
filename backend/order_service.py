"""Authoritative order state machine.

The backend is the single source of truth for order status. Every transition
verifies the allowed edges, records history (actor + timestamp), writes an audit
entry, and emits notifications. The frontend can never set status arbitrarily.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import logging

import os

from bson import ObjectId
from fastapi import HTTPException
from pymongo import ReturnDocument

from audit import write_audit
from database import order_status_history, orders, plants, production_batches, users
from notifications import delivery, record_notification

logger = logging.getLogger(__name__)

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

TERMINAL = {DELIVERED, REJECTED, CANCELLED}


def can_transition(current: str, target: str) -> bool:
    return target in TRANSITIONS.get(current, set())


async def _oid(value: str):
    try:
        return ObjectId(value)
    except Exception:
        return value


async def _guard_transition_invariants(order: dict, target: str) -> None:
    """Enforce domain invariants shared by every role and endpoint."""
    if target != PRODUCTION_COMPLETE:
        return

    order_id = str(order["_id"])
    rows = await production_batches.aggregate(
        [
            {"$match": {"order_id": order_id}},
            {"$group": {"_id": None, "total": {"$sum": "$quantity"}}},
        ]
    ).to_list(1)
    produced = float(rows[0]["total"] if rows else 0)
    required = float(order.get("quantity") or 0)
    if required <= 0:
        raise HTTPException(409, "Order quantity is invalid; production cannot be completed")
    # Small batching/tolerance difference is allowed, but materially incomplete
    # production must never be marked complete by any role-specific endpoint.
    if produced + 0.001 < required * 0.98:
        raise HTTPException(409, f"Production is incomplete ({produced:g} / {required:g} m³)")


async def transition_order(
    order_id: str,
    target: str,
    actor_id: str,
    note: Optional[str] = None,
    notify_user_ids: Optional[list[str]] = None,
    event: Optional[str] = None,
) -> dict:
    """Perform a validated, compare-and-set status transition."""
    order = await orders.find_one({"_id": await _oid(order_id)})
    if not order:
        raise HTTPException(404, "Order not found")

    current = order.get("status")
    if current == target:
        if target in (DISPATCHED, DELIVERED):
            await _customer_sms_once(order, target)
        return order
    if not can_transition(current, target):
        raise HTTPException(409, f"Cannot move order from {current} to {target}")

    await _guard_transition_invariants(order, target)

    now = datetime.now(timezone.utc)
    updated = await orders.find_one_and_update(
        {"_id": order["_id"], "status": current},
        {"$set": {"status": target, "updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
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

    history = {
            "order_id": str(order["_id"]),
            "from_status": current,
            "to_status": target,
            "actor_id": actor_id,
            "note": note,
            "created_at": now,
        }
    history_result = await order_status_history.insert_one(history)
    history["_id"] = history_result.inserted_id
    # Materialization is deliberately after the authoritative transition. A
    # transient queue failure can be recovered by startup backfill.
    from order_automation import automation_service
    try:
        await automation_service.status_changed(history)
    except Exception as exc:  # recovered by idempotent startup backfill
        logger.warning("Order automation materialization deferred (%s)", type(exc).__name__)
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

    if target in (DISPATCHED, DELIVERED):
        await _customer_sms_once(updated, target)

    return updated


async def _customer_sms_once(order: dict, event: str) -> None:
    """Send at most one concurrently active SMS per (order,event)."""
    if not delivery.sms_configured or not order.get("customer_id"):
        return

    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(minutes=2)
    flag = f"sms_flags.{event}"
    claimed = await orders.find_one_and_update(
        {
            "_id": order["_id"],
            flag: {"$ne": True},
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
        else:
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
    except Exception:
        await orders.update_one(
            {"_id": order["_id"]},
            {"$set": {f"{flag}.status": "failed", f"{flag}.failed_at": datetime.now(timezone.utc),
                       f"{flag}.reason": "unexpected_delivery_error"}},
        )


async def owner_plant_ids(user_id: str) -> list[str]:
    docs = await plants.find({"owner_id": user_id}).to_list(100)
    return [str(d["_id"]) for d in docs]
