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
from typing import Any, Optional

from bson import ObjectId
from pymongo import ReturnDocument

from database import db, order_status_history, orders

ORDER_STATUS_CHANGED = "ORDER_STATUS_CHANGED"
SCHEMA_VERSION = 1

STATE_PENDING = "PENDING"
STATE_PROCESSING = "PROCESSING"
STATE_RETRY = "RETRY"
STATE_COMPLETED = "COMPLETED"

order_automation_events = db.order_automation_events

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
        "routing_key": f"order.status.{target.lower()}",
        "aggregate_type": "order",
        "aggregate_id": order_id,
        "source_history_id": str(history_id),
        "from_status": history.get("from_status"),
        "to_status": target,
        "actor_id": _as_external(history.get("actor_id")),
        "note": history.get("note"),
        "occurred_at": occurred_at,
        "payload": _order_payload(order),
        "state": STATE_PENDING,
        "attempts": 0,
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
                    "updated_at": now,
                },
                "$inc": {"attempts": 1},
            },
            sort=[("created_at", 1), ("_id", 1)],
            return_document=ReturnDocument.AFTER,
        )
        if not event:
            break
        claimed.append(event)

    return claimed


async def complete_order_status_event(
    event_id: Any,
    worker_id: str,
    result: Optional[dict] = None,
) -> bool:
    """Acknowledge a claimed event. Wrong/stale workers cannot acknowledge it."""
    now = _utcnow()
    update = {
        "$set": {
            "state": STATE_COMPLETED,
            "completed_at": now,
            "updated_at": now,
            "result": result or {},
        },
        "$unset": {
            "lease_expires_at": "",
            "last_error": "",
        },
    }
    res = await order_automation_events.update_one(
        {"_id": event_id, "state": STATE_PROCESSING, "worker_id": worker_id},
        update,
    )
    return res.modified_count == 1


async def fail_order_status_event(
    event_id: Any,
    worker_id: str,
    error: str,
    retry_after_seconds: int = 60,
) -> bool:
    """Release a failed event back to the queue with bounded retry delay."""
    now = _utcnow()
    retry_after_seconds = max(15, min(int(retry_after_seconds), 3600))
    res = await order_automation_events.update_one(
        {"_id": event_id, "state": STATE_PROCESSING, "worker_id": worker_id},
        {
            "$set": {
                "state": STATE_RETRY,
                "last_error": str(error)[:1000],
                "next_attempt_at": now + timedelta(seconds=retry_after_seconds),
                "updated_at": now,
            },
            "$unset": {"lease_expires_at": ""},
        },
    )
    return res.modified_count == 1
