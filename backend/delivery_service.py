"""Aggregate multi-load delivery reconciliation.

A single mixer load may be delivered while the commercial order still has
additional loads outstanding. This service updates delivered quantity after each
load and finalizes the parent order exactly once when all non-cancelled loads are
complete and quantity tolerance is satisfied.
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from pymongo import ReturnDocument

from audit import write_audit
from database import order_loads, order_status_history, orders, proof_of_delivery
from notifications import record_notification
from order_service import DELIVERED, DISPATCHED, _customer_sms_once


async def reconcile_parent_delivery(order_id: str, actor_id: str, receiver_name: str) -> dict:
    order = await orders.find_one({"_id": await _oid(order_id)})
    if not order:
        raise HTTPException(409, "Delivery order is missing")

    pods = await proof_of_delivery.find({"order_id": order_id}).to_list(1000)
    delivered_quantity = round(sum(float(p.get("delivered_quantity") or 0) for p in pods), 3)
    await orders.update_one(
        {"_id": order["_id"]},
        {"$set": {"delivered_quantity": delivered_quantity, "pod_submitted_at": datetime.now(timezone.utc)}},
    )

    active_remaining = await order_loads.count_documents(
        {"order_id": order_id, "status": {"$nin": ["DELIVERED", "CANCELLED"]}}
    )
    required = float(order.get("quantity") or 0)
    quantity_complete = required > 0 and delivered_quantity + 0.001 >= required * 0.98
    if active_remaining or not quantity_complete:
        return {
            "order_status": order.get("status"),
            "delivered_quantity": delivered_quantity,
            "required_quantity": required,
            "complete": False,
        }

    latest = await orders.find_one({"_id": order["_id"]})
    if latest and latest.get("status") == DELIVERED:
        return {
            "order_status": DELIVERED,
            "delivered_quantity": delivered_quantity,
            "required_quantity": required,
            "complete": True,
            "idempotent": True,
        }
    if not latest or latest.get("status") != DISPATCHED:
        raise HTTPException(
            409,
            f"All loads are delivered but parent order requires reconciliation from {latest.get('status') if latest else 'UNKNOWN'}",
        )

    now = datetime.now(timezone.utc)
    updated = await orders.find_one_and_update(
        {"_id": latest["_id"], "status": DISPATCHED},
        {"$set": {"status": DELIVERED, "delivered_quantity": delivered_quantity,
                  "delivered_at": now, "updated_at": now}, "$unset": {"active_load_id": ""}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        concurrent = await orders.find_one({"_id": latest["_id"]})
        if concurrent and concurrent.get("status") == DELIVERED:
            return {"order_status": DELIVERED, "delivered_quantity": delivered_quantity,
                    "required_quantity": required, "complete": True, "idempotent": True}
        raise HTTPException(409, "Parent order changed concurrently during final delivery")

    await order_status_history.insert_one(
        {"order_id": order_id, "from_status": DISPATCHED, "to_status": DELIVERED,
         "actor_id": actor_id, "note": "All planned mixer loads delivered",
         "created_at": now}
    )
    await write_audit(
        actor_id, "order.delivered", "order", order_id,
        {"from": DISPATCHED, "to": DELIVERED, "delivered_quantity": delivered_quantity},
    )
    if updated.get("customer_id"):
        await record_notification(
            updated["customer_id"], "delivered",
            f"Order {updated.get('order_number')} Delivered",
            f"All loads delivered — received by {receiver_name}.",
        )
    await _customer_sms_once(updated, DELIVERED)
    return {"order_status": DELIVERED, "delivered_quantity": delivered_quantity,
            "required_quantity": required, "complete": True}


async def _oid(value: str):
    from bson import ObjectId
    try:
        return ObjectId(value)
    except Exception:
        return value
