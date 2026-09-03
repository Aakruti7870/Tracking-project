"""Durable order-status automation queue.

Step 1 of the TrackMyRMC automation system uses the existing
``order_status_history`` collection as the canonical event ledger. Each history
record is materialized exactly once into ``order_automation_events`` and can be
claimed by a future n8n/Vapi/notification worker without granting that worker
permission to mutate order state.

The order state machine remains authoritative; this module only observes status
history and prepares safe automation work items.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe
from typing import Any, Optional

from bson import ObjectId
from pymongo import ReturnDocument

from database import db, order_status_history, orders, users

ORDER_STATUS_CHANGED = "ORDER_STATUS_CHANGED"
SCHEMA_VERSION = 1

STATE_PENDING = "PENDING"
STATE_PROCESSING = "PROCESSING"
STATE_RETRY = "RETRY"
STATE_COMPLETED = "COMPLETED"
STATE_DEAD_LETTER = "DEAD_LETTER"

CANONICAL_STATUSES = (
    "DRAFT", "PENDING", "ACCEPTED", "REJECTED", "SCHEDULED",
    "IN_PRODUCTION", "PRODUCTION_COMPLETE", "TM_ASSIGNED", "DRIVER_ASSIGNED",
    "READY_TO_DISPATCH", "DISPATCHED", "EN_ROUTE", "AT_SITE", "UNLOADING",
    "POD_PENDING", "DELIVERED", "CANCELLED",
)

# Copy and delivery policy live outside the state machine so operators can evolve
# customer communications without granting an integration permission to mutate orders.
_MESSAGES = {
    "DRAFT": "Your order draft is saved.",
    "PENDING": "We received your order and it is awaiting plant review.",
    "ACCEPTED": "Your order has been accepted by the plant.",
    "REJECTED": "The plant could not accept this order. Contact support for help.",
    "SCHEDULED": "Your concrete delivery has been scheduled.",
    "IN_PRODUCTION": "Production has started for your order.",
    "PRODUCTION_COMPLETE": "Production is complete for your order.",
    "TM_ASSIGNED": "A transit mixer has been assigned to your order.",
    "DRIVER_ASSIGNED": "A driver has been assigned to your order.",
    "READY_TO_DISPATCH": "Your order is ready to dispatch.",
    "DISPATCHED": "Your order has left the plant. Tracking and ETA are available in the app.",
    "EN_ROUTE": "Your delivery is en route. View the latest ETA in the app.",
    "AT_SITE": "Your delivery has arrived at the site.",
    "UNLOADING": "Unloading is in progress.",
    "POD_PENDING": "Delivery is complete and proof of delivery is being finalized.",
    "DELIVERED": "Your order was delivered. View the authorized challan and POD in the app.",
    "CANCELLED": "Your order was cancelled. Contact support if you need assistance.",
}

AUTOMATION_POLICIES = {
    status: {
        "routing_key": f"order.status.{status.lower()}",
        "template": {"en": _MESSAGES[status]},
        "channels": (["n8n", "push", "sms", "whatsapp", "vapi"]
                     if status in {"REJECTED", "CANCELLED", "DELIVERED"}
                     else ["n8n", "push", "sms", "whatsapp"]),
        "quiet_hours": status not in {"REJECTED", "CANCELLED"},
        "respect_opt_out": True,
        "max_attempts": 5,
        "escalate": status in {"REJECTED", "CANCELLED"},
    }
    for status in CANONICAL_STATUSES
}

order_automation_events = db.order_automation_events
order_automation_attempts = db.order_automation_attempts

_SAFE_ORDER_FIELDS = (
    "order_number",
    "customer_id",
    "plant_id",
    "site_id",
    "site_name",
    "grade",
    "quantity",
    "delivery_mode",
    "scheduled_at",
    "delivery_date",
    "delivery_time",
    "tm_id",
    "tm_number",
    "driver_id",
    "delivered_quantity",
    "payment_status",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_external(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    return value


def _order_payload(order: Optional[dict]) -> dict:
    """Return an automation-safe order snapshot with no contact/secret fields."""
    if not order:
        return {}
    payload: dict[str, Any] = {}
    for field in _SAFE_ORDER_FIELDS:
        if field in order and order[field] is not None:
            payload[field] = _as_external(order[field])
    return payload


def build_order_status_event(history: dict, order: Optional[dict]) -> dict:
    """Build one deterministic automation event from an order history row."""
    history_id = history.get("_id")
    if history_id is None:
        raise ValueError("Order status history row must have _id")

    order_id = str(history.get("order_id") or (order or {}).get("_id") or "")
    if not order_id:
        raise ValueError("Order status history row must identify an order")

    target = str(history.get("to_status") or "").strip().upper()
    if not target:
        raise ValueError("Order status history row must have to_status")

    now = _utcnow()
    occurred_at = history.get("created_at") or now
    return {
        "_id": history_id,
        "schema_version": SCHEMA_VERSION,
        "event_type": ORDER_STATUS_CHANGED,
        "routing_key": AUTOMATION_POLICIES.get(target, {}).get(
            "routing_key", f"order.status.{target.lower()}"
        ),
        "aggregate_type": "order",
        "aggregate_id": order_id,
        "source_history_id": str(history_id),
        "from_status": history.get("from_status"),
        "to_status": target,
        "occurred_at": occurred_at,
        "payload": _order_payload(order),
        "delivery": AUTOMATION_POLICIES.get(target, {}),
        "state": STATE_PENDING,
        "attempts": 0,
        "max_attempts": AUTOMATION_POLICIES.get(target, {}).get("max_attempts", 5),
        "next_attempt_at": now,
        "created_at": now,
        "updated_at": now,
    }


async def ensure_indexes() -> None:
    """Create queue indexes. ``_id`` is the dedup key for each history event."""
    await order_automation_events.create_index(
        [("state", 1), ("next_attempt_at", 1), ("created_at", 1)],
        name="automation_claim_queue",
    )
    await order_automation_events.create_index(
        [("aggregate_id", 1), ("occurred_at", -1)],
        name="automation_order_timeline",
    )
    await order_automation_events.create_index(
        [("routing_key", 1), ("state", 1)],
        name="automation_route_state",
    )
    await order_automation_attempts.create_index(
        [("event_id", 1), ("created_at", 1)], name="automation_attempt_audit"
    )


async def _order_for_history(history: dict) -> Optional[dict]:
    raw = history.get("order_id")
    if raw is None:
        return None
    candidates: list[Any] = [raw]
    try:
        candidates.insert(0, ObjectId(str(raw)))
    except Exception:
        pass
    return await orders.find_one({"_id": {"$in": candidates}})


async def materialize_history_event(history: dict) -> dict:
    """Idempotently turn one status-history row into one queue event."""
    order = await _order_for_history(history)
    event = build_order_status_event(history, order)
    await order_automation_events.update_one(
        {"_id": event["_id"]},
        {"$setOnInsert": event},
        upsert=True,
    )
    stored = await order_automation_events.find_one({"_id": event["_id"]})
    return stored or event


async def backfill_order_status_events(limit: int = 500) -> int:
    """Materialize history rows not yet present in the automation queue."""
    limit = max(1, min(int(limit), 2000))
    pipeline = [
        {"$sort": {"created_at": 1, "_id": 1}},
        {
            "$lookup": {
                "from": order_automation_events.name,
                "localField": "_id",
                "foreignField": "_id",
                "as": "automation_event",
            }
        },
        {"$match": {"automation_event": {"$eq": []}}},
        {"$limit": limit},
        {"$project": {"automation_event": 0}},
    ]
    rows = await order_status_history.aggregate(pipeline).to_list(limit)
    for history in rows:
        await materialize_history_event(history)
    return len(rows)


async def claim_order_status_events(
    worker_id: str,
    limit: int = 50,
    lease_seconds: int = 120,
) -> list[dict]:
    """Atomically claim pending/retry events for one automation worker."""
    worker_id = str(worker_id).strip()
    if not worker_id:
        raise ValueError("worker_id is required")

    limit = max(1, min(int(limit), 200))
    lease_seconds = max(30, min(int(lease_seconds), 900))
    claimed: list[dict] = []

    for _ in range(limit):
        now = _utcnow()
        lease_expires_at = now + timedelta(seconds=lease_seconds)
        lease_token = token_urlsafe(24)
        event = await order_automation_events.find_one_and_update(
            {
                "$or": [
                    {
                        "state": {"$in": [STATE_PENDING, STATE_RETRY]},
                        "next_attempt_at": {"$lte": now},
                    },
                    {
                        "state": STATE_PROCESSING,
                        "lease_expires_at": {"$lte": now},
                    },
                ]
            },
            {
                "$set": {
                    "state": STATE_PROCESSING,
                    "worker_id": worker_id,
                    "claimed_at": now,
                    "lease_expires_at": lease_expires_at,
                    "lease_token": lease_token,
                    "updated_at": now,
                },
                "$inc": {"attempts": 1},
            },
            sort=[("created_at", 1), ("_id", 1)],
            return_document=ReturnDocument.AFTER,
        )
        if not event:
            break
        await order_automation_attempts.insert_one({
            "event_id": str(event["_id"]), "worker_id": worker_id,
            "attempt": event["attempts"], "action": "CLAIMED", "created_at": now,
        })
        claimed.append(event)

    return claimed


async def complete_order_status_event(
    event_id: Any,
    worker_id: str,
    result: Optional[dict] = None,
    lease_token: Optional[str] = None,
) -> bool:
    """Acknowledge a claimed event. Wrong/stale workers cannot acknowledge it."""
    now = _utcnow()
    update = {
        "$set": {
            "state": STATE_COMPLETED,
            "completed_at": now,
            "updated_at": now,
            "provider_result": _safe_provider_result(result),
        },
        "$unset": {
            "lease_expires_at": "",
            "lease_token": "",
            "last_error": "",
        },
    }
    res = await order_automation_events.update_one(
        {"_id": event_id, "state": STATE_PROCESSING, "worker_id": worker_id,
         "lease_token": lease_token, "lease_expires_at": {"$gt": now}},
        update,
    )
    if res.modified_count == 1:
        await order_automation_attempts.insert_one({
            "event_id": str(event_id), "worker_id": worker_id, "action": "COMPLETED",
            "provider_result": _safe_provider_result(result), "created_at": now,
        })
    return res.modified_count == 1


async def fail_order_status_event(
    event_id: Any,
    worker_id: str,
    error: str,
    retry_after_seconds: int = 60,
    lease_token: Optional[str] = None,
) -> bool:
    """Release a failed event back to the queue with bounded retry delay."""
    now = _utcnow()
    retry_after_seconds = max(15, min(int(retry_after_seconds), 3600))
    event = await order_automation_events.find_one({
        "_id": event_id, "state": STATE_PROCESSING, "worker_id": worker_id,
        "lease_token": lease_token, "lease_expires_at": {"$gt": now},
    })
    if not event:
        return False
    dead = int(event.get("attempts", 0)) >= int(event.get("max_attempts", 5))
    retry_after_seconds = min(3600, retry_after_seconds * (2 ** max(0, int(event.get("attempts", 1)) - 1)))
    res = await order_automation_events.update_one(
        {"_id": event_id, "state": STATE_PROCESSING, "worker_id": worker_id,
         "lease_token": lease_token, "lease_expires_at": {"$gt": now}},
        {
            "$set": {
                "state": STATE_DEAD_LETTER if dead else STATE_RETRY,
                "last_error": str(error)[:1000],
                "next_attempt_at": now + timedelta(seconds=retry_after_seconds),
                "dead_lettered_at": now if dead else None,
                "updated_at": now,
            },
            "$unset": {"lease_expires_at": "", "lease_token": ""},
        },
    )
    if res.modified_count == 1:
        await order_automation_attempts.insert_one({
            "event_id": str(event_id), "worker_id": worker_id,
            "attempt": event.get("attempts"), "action": "DEAD_LETTERED" if dead else "RETRY_SCHEDULED",
            "failure_reason": str(error)[:1000], "retry_after_seconds": retry_after_seconds,
            "created_at": now,
        })
    return res.modified_count == 1


def _safe_provider_result(result: Optional[dict]) -> dict:
    """Persist only non-sensitive delivery metadata returned by a provider."""
    result = result or {}
    allowed = ("provider", "provider_id", "status", "failure_reason", "sent_at", "completed_at")
    safe = {key: _as_external(result[key]) for key in allowed if result.get(key) is not None}
    deliveries = result.get("deliveries")
    if isinstance(deliveries, list):
        safe["deliveries"] = [
            {key: str(row[key])[:500] for key in ("provider", "provider_id", "status") if row.get(key) is not None}
            for row in deliveries[:10] if isinstance(row, dict)
        ]
    return safe


async def deliver_claimed_event(event_id: Any, worker_id: str, lease_token: str,
                                requested_channels: Optional[list[str]] = None) -> dict:
    """Deliver one currently leased event through configured adapter boundaries.

    Contact information is resolved inside the trusted backend and is never returned
    through the worker API or stored in provider results.
    """
    now = _utcnow()
    event = await order_automation_events.find_one({
        "_id": event_id, "state": STATE_PROCESSING, "worker_id": worker_id,
        "lease_token": lease_token, "lease_expires_at": {"$gt": now},
    })
    if not event:
        raise ValueError("Event lease is stale or not owned by this worker")
    allowed = list(event.get("delivery", {}).get("channels", []))
    channels = requested_channels or allowed
    if not channels or any(channel not in allowed for channel in channels):
        raise ValueError("Requested channel is not allowed by event policy")

    order = await _order_for_history({"order_id": event["aggregate_id"]})
    customer = None
    if order and order.get("customer_id"):
        customer_id = order["customer_id"]
        candidates: list[Any] = [customer_id]
        try:
            candidates.insert(0, ObjectId(str(customer_id)))
        except Exception:
            pass
        customer = await users.find_one({"_id": {"$in": candidates}})
    customer = customer or {}
    opted_out = set(customer.get("notification_opt_out_channels") or [])
    if customer.get("automation_opt_out"):
        opted_out.update({"sms", "whatsapp", "vapi"})

    from automation_providers import n8n, twilio_messages, vapi
    from notifications import record_notification
    results: list[dict] = []
    message = event.get("delivery", {}).get("template", {}).get("en", "Order status updated.")
    for channel in channels:
        if channel in opted_out:
            results.append({"provider": channel, "provider_id": "opt-out", "status": "skipped"})
            continue
        if channel == "n8n":
            results.append((await n8n.send(event)).as_dict())
        elif channel == "vapi":
            results.append((await vapi.send(event, str(customer.get("phone") or ""))).as_dict())
        elif channel in {"sms", "whatsapp"}:
            results.append((await twilio_messages.send(channel, str(customer.get("phone") or ""), message)).as_dict())
        elif channel == "push":
            customer_id = str((order or {}).get("customer_id") or "")
            if not customer_id:
                raise RuntimeError("Order customer is unavailable")
            await record_notification(customer_id, event["routing_key"], "Order update", message,
                                      {"order_id": event["aggregate_id"], "status": event["to_status"]})
            results.append({"provider": "firebase_fcm_v1", "provider_id": event["source_history_id"], "status": "sent"})
        else:
            raise ValueError("Unsupported automation channel")
    return {"provider": "multi", "provider_id": event["source_history_id"],
            "status": "completed", "deliveries": results}
