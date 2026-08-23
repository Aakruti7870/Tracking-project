"""Invoice creation from persisted plant rate cards and business profile."""
from datetime import date, datetime, timezone

from fastapi import HTTPException

from database import invoices, next_sequence, plant_business_profiles, rate_cards


async def create_invoice_for_order(order: dict) -> dict:
    order_id = str(order["_id"])
    existing = await invoices.find_one({"order_id": order_id})
    if existing:
        return existing

    today = date.today().isoformat()
    card = await rate_cards.find_one(
        {
            "plant_id": order["plant_id"],
            "grade": order.get("grade"),
            "active": True,
            "effective_from": {"$lte": today},
            "$or": [
                {"effective_to": None},
                {"effective_to": {"$exists": False}},
                {"effective_to": {"$gte": today}},
            ],
        },
        sort=[("effective_from", -1)],
    )
    if not card:
        raise HTTPException(409, f"No active rate card configured for {order.get('grade')}")

    qty = float(order.get("delivered_quantity") or order.get("quantity") or 0)
    if qty <= 0:
        raise HTTPException(409, "Delivered quantity is missing; invoice cannot be calculated")

    rate = float(card["rate_per_m3"])
    gst_rate = float(card.get("gst_rate") or 0)
    concrete_amount = qty * rate
    transport_amount = float(order.get("transport_amount") or 0)
    pumping_amount = float(order.get("pumping_amount") or 0)
    subtotal = round(concrete_amount + transport_amount + pumping_amount, 2)
    gst = round(subtotal * gst_rate / 100.0, 2)
    total = round(subtotal + gst, 2)

    profile = await plant_business_profiles.find_one({"plant_id": order["plant_id"]})
    prefix = (profile or {}).get("invoice_prefix") or "INV"
    seq = await next_sequence(f"invoice:{order['plant_id']}")
    invoice_number = f"{prefix}-{seq:06d}"
    now = datetime.now(timezone.utc)

    doc = {
        "invoice_number": invoice_number,
        "order_id": order_id,
        "order_number": order.get("order_number"),
        "plant_id": order["plant_id"],
        "customer_id": order.get("customer_id"),
        "customer_name": order.get("customer_name"),
        "grade": order.get("grade"),
        "quantity": qty,
        "rate": rate,
        "rate_card_id": str(card["_id"]),
        "gst_rate": gst_rate,
        "concrete_amount": round(concrete_amount, 2),
        "transport_amount": round(transport_amount, 2),
        "pumping_amount": round(pumping_amount, 2),
        "subtotal": subtotal,
        "gst": gst,
        "total": total,
        "paid": 0,
        "status": "UNPAID",
        "created_at": now,
    }
    result = await invoices.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc
