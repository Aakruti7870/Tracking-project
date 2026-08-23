"""Plant Owner endpoints — scoped to the plants the owner owns."""
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from audit import write_audit
from billing_service import create_invoice_for_order
from database import driver_incidents, invoices, next_sequence, order_status_history, orders, payments, plants, production_batches, users, vehicles, driver_trips, challans
from models import AssignDriverBody, AssignTmBody, ChallanBody, PaymentBody, ProductionBatchBody, RejectOrderBody
from notifications import record_notification
from order_service import (
    ACCEPTED,
    DISPATCHED,
    DRIVER_ASSIGNED,
    IN_PRODUCTION,
    PENDING,
    PRODUCTION_COMPLETE,
    READY_TO_DISPATCH,
    REJECTED,
    TM_ASSIGNED,
    owner_plant_ids,
    transition_order,
)
from production_service import record_production_batch
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
        "delivery_mode": doc.get("delivery_mode", "DELIVERY"),
        "status": doc.get("status"),
        "payment_status": doc.get("payment_status"),
        "tm_number": doc.get("tm_number"),
        "driver_name": doc.get("driver_name"),
        "driver_mobile": doc.get("driver_mobile"),
        "challan_number": doc.get("challan_number"),
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
    delivered_qty = sum(o.get("delivered_quantity") or o.get("quantity", 0) for o in delivered)

    my_plants = await plants.find({"_id": {"$in": [await _oid(i) for i in plant_ids]}}).to_list(100)
    fleet_docs = await vehicles.find(base).to_list(1000)
    active_mixers = len([v for v in fleet_docs if v.get("status") in ("loading", "dispatched")])
    available_mixers = len([v for v in fleet_docs if v.get("status") == "available"])
    invoice_docs = await invoices.find(base).to_list(2000)
    todays_revenue = sum(
        float(i.get("total") or 0)
        for i in invoice_docs
        if i.get("created_at") and i["created_at"].replace(tzinfo=timezone.utc) >= today
    )
    receivables = sum(float(i.get("total") or 0) - float(i.get("paid") or 0) for i in invoice_docs)

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
            "active_mixers": active_mixers,
            "available_mixers": available_mixers,
            "todays_revenue": round(todays_revenue, 2),
            "receivables": round(receivables, 2),
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


# ---------------- Fleet & drivers ----------------

@router.get("/fleet")
async def fleet(ctx: dict = Depends(owner_only)):
    plant_ids = await _scoped_plant_ids(ctx)
    docs = await vehicles.find({"plant_id": {"$in": plant_ids}}).to_list(200)
    return {
        "vehicles": [
            {
                "id": str(v["_id"]),
                "tm_number": v.get("tm_number"),
                "capacity_m3": v.get("capacity_m3"),
                "status": v.get("status"),
                "current_order_id": v.get("current_order_id"),
            }
            for v in docs
        ]
    }


@router.get("/drivers")
async def drivers(ctx: dict = Depends(owner_only)):
    plant_ids = await _scoped_plant_ids(ctx)
    docs = await users.find({"primary_role": "driver", "plant_id": {"$in": plant_ids}}).to_list(200)
    return {
        "drivers": [
            {"id": str(d["_id"]), "name": d.get("name"), "phone": d.get("phone")}
            for d in docs
        ]
    }


# ---------------- Dispatch workflow ----------------

@router.post("/orders/{order_id}/assign-tm")
async def assign_tm(order_id: str, body: AssignTmBody, ctx: dict = Depends(owner_only)):
    order = await _guard_owns(ctx, order_id)
    if order.get("status") not in (ACCEPTED, "SCHEDULED", "PRODUCTION_COMPLETE", TM_ASSIGNED):
        raise HTTPException(409, "Order is not ready for transit mixer assignment")
    v = await vehicles.find_one({"_id": await _oid(body.vehicle_id), "plant_id": order["plant_id"]})
    if not v:
        raise HTTPException(404, "Vehicle not found for this plant")
    if v.get("status") not in ("available",) and v.get("current_order_id") != order_id:
        raise HTTPException(409, f"Vehicle is {v.get('status')} and cannot be assigned")

    await orders.update_one(
        {"_id": order["_id"]},
        {"$set": {"tm_id": str(v["_id"]), "tm_number": v.get("tm_number")}},
    )
    await vehicles.update_one(
        {"_id": v["_id"]}, {"$set": {"status": "loading", "current_order_id": order_id}}
    )
    if order.get("status") != TM_ASSIGNED:
        await transition_order(order_id, TM_ASSIGNED, ctx["user_id"],
                               note=f"TM {v.get('tm_number')} assigned")
    return {"status": TM_ASSIGNED, "tm_number": v.get("tm_number")}


@router.post("/orders/{order_id}/assign-driver")
async def assign_driver(order_id: str, body: AssignDriverBody, ctx: dict = Depends(owner_only)):
    order = await _guard_owns(ctx, order_id)
    if order.get("status") not in (TM_ASSIGNED, DRIVER_ASSIGNED):
        raise HTTPException(409, "Assign a transit mixer before a driver")
    d = await users.find_one({"_id": await _oid(body.driver_id), "primary_role": "driver",
                              "plant_id": order["plant_id"]})
    if not d:
        raise HTTPException(404, "Driver not found for this plant")

    await orders.update_one(
        {"_id": order["_id"]},
        {"$set": {"driver_id": str(d["_id"]), "driver_name": d.get("name"),
                  "driver_mobile": d.get("phone")}},
    )
    existing_trip = await driver_trips.find_one({"order_id": order_id})
    trip_doc = {
        "order_id": order_id,
        "order_number": order.get("order_number"),
        "plant_id": order["plant_id"],
        "customer_id": order.get("customer_id"),
        "driver_id": str(d["_id"]),
        "vehicle_id": order.get("tm_id"),
        "tm_number": order.get("tm_number"),
        "grade": order.get("grade"),
        "quantity": order.get("quantity"),
        "site_name": order.get("site_name"),
        "site_address": order.get("site_address"),
        "status": "ASSIGNED",
        "updated_at": datetime.now(timezone.utc),
    }
    if existing_trip:
        await driver_trips.update_one({"_id": existing_trip["_id"]}, {"$set": trip_doc})
    else:
        trip_doc["created_at"] = datetime.now(timezone.utc)
        await driver_trips.insert_one(trip_doc)

    await record_notification(str(d["_id"]), "trip_assigned",
                              f"New trip {order.get('order_number')}",
                              f"{order.get('quantity')} m³ of {order.get('grade')} to {order.get('site_name')}.")

    if order.get("status") != DRIVER_ASSIGNED:
        await transition_order(order_id, DRIVER_ASSIGNED, ctx["user_id"],
                               note=f"Driver {d.get('name')} assigned")
    return {"status": DRIVER_ASSIGNED, "driver_name": d.get("name")}


@router.post("/orders/{order_id}/challan")
async def generate_challan(order_id: str, body: ChallanBody, ctx: dict = Depends(owner_only)):
    order = await _guard_owns(ctx, order_id)
    if order.get("status") not in (DRIVER_ASSIGNED, READY_TO_DISPATCH):
        raise HTTPException(409, "Assign transit mixer & driver before generating challan")

    existing = await challans.find_one({"order_id": order_id})
    if existing:
        return {"challan": _serialize_challan(existing)}

    seq = await next_sequence("challan_number")
    challan_number = f"CH-{2000 + seq}"
    now = datetime.now(timezone.utc)
    doc = {
        "challan_number": challan_number,
        "order_id": order_id,
        "order_number": order.get("order_number"),
        "plant_id": order["plant_id"],
        "plant_name": order.get("plant_name"),
        "customer_name": order.get("customer_name"),
        "site_name": order.get("site_name"),
        "site_address": order.get("site_address"),
        "grade": order.get("grade"),
        "quantity": order.get("quantity"),
        "tm_number": order.get("tm_number"),
        "driver_name": order.get("driver_name"),
        "driver_mobile": order.get("driver_mobile"),
        "batcher": body.batcher,
        "supervisor": body.supervisor,
        "quality_engineer": body.quality_engineer,
        "remarks": body.remarks,
        "created_at": now,
    }
    res = await challans.insert_one(doc)
    doc["_id"] = res.inserted_id
    await orders.update_one(
        {"_id": order["_id"]},
        {"$set": {"challan_id": str(res.inserted_id), "challan_number": challan_number}},
    )
    if order.get("status") != READY_TO_DISPATCH:
        await transition_order(order_id, READY_TO_DISPATCH, ctx["user_id"],
                               note=f"Challan {challan_number} generated")
    return {"challan": _serialize_challan(doc)}


@router.get("/orders/{order_id}/challan")
async def get_challan(order_id: str, ctx: dict = Depends(owner_only)):
    await _guard_owns(ctx, order_id)
    doc = await challans.find_one({"order_id": order_id})
    if not doc:
        raise HTTPException(404, "Challan not generated yet")
    return {"challan": _serialize_challan(doc)}


@router.post("/orders/{order_id}/dispatch")
async def dispatch_order(order_id: str, ctx: dict = Depends(owner_only)):
    order = await _guard_owns(ctx, order_id)
    if order.get("status") != READY_TO_DISPATCH:
        raise HTTPException(409, "Generate a challan before dispatching")

    now = datetime.now(timezone.utc)
    await orders.update_one({"_id": order["_id"]}, {"$set": {"dispatched_at": now}})
    if order.get("tm_id"):
        await vehicles.update_one({"_id": await _oid(order["tm_id"])}, {"$set": {"status": "dispatched"}})
    await driver_trips.update_one(
        {"order_id": order_id},
        {"$set": {"status": "DISPATCHED", "updated_at": now}},
    )
    await transition_order(
        order_id, DISPATCHED, ctx["user_id"],
        note="Dispatched — live tracking available",
        notify_user_ids=[order["customer_id"]], event="dispatched",
    )
    return {"status": DISPATCHED}


def _serialize_challan(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "challan_number": doc.get("challan_number"),
        "order_number": doc.get("order_number"),
        "plant_name": doc.get("plant_name"),
        "customer_name": doc.get("customer_name"),
        "site_name": doc.get("site_name"),
        "site_address": doc.get("site_address"),
        "grade": doc.get("grade"),
        "quantity": doc.get("quantity"),
        "tm_number": doc.get("tm_number"),
        "driver_name": doc.get("driver_name"),
        "driver_mobile": doc.get("driver_mobile"),
        "batcher": doc.get("batcher"),
        "supervisor": doc.get("supervisor"),
        "quality_engineer": doc.get("quality_engineer"),
        "remarks": doc.get("remarks"),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
    }


# ---------------- Incidents (Driver SOS) ----------------

@router.get("/incidents")
async def incidents(ctx: dict = Depends(owner_only)):
    plant_ids = await _scoped_plant_ids(ctx)
    docs = await driver_incidents.find({"plant_id": {"$in": plant_ids}}).sort("created_at", -1).to_list(200)
    return {"incidents": [
        {"id": str(d["_id"]), "type": d.get("type"), "status": d.get("status"),
         "driver_name": d.get("driver_name"), "vehicle": d.get("vehicle"),
         "order_number": d.get("order_number"), "remark": d.get("remark"),
         "lat": d.get("lat"), "lng": d.get("lng"),
         "created_at": d.get("created_at").isoformat() if d.get("created_at") else None}
        for d in docs
    ]}


@router.post("/incidents/{incident_id}/resolve")
async def resolve_incident(incident_id: str, ctx: dict = Depends(owner_only)):
    plant_ids = await _scoped_plant_ids(ctx)
    inc = await driver_incidents.find_one({"_id": await _oid(incident_id), "plant_id": {"$in": plant_ids}})
    if not inc:
        raise HTTPException(404, "Incident not found")
    await driver_incidents.update_one({"_id": inc["_id"]}, {"$set": {"status": "RESOLVED"}})
    await record_notification(inc["driver_id"], "sos_resolved", "SOS resolved",
                              f"Your {inc.get('type')} alert has been acknowledged.")
    return {"status": "RESOLVED"}


# ---------------- Production Board ----------------

@router.post("/orders/{order_id}/production/start")
async def start_production(order_id: str, ctx: dict = Depends(owner_only)):
    order = await _guard_owns(ctx, order_id)
    if order.get("status") not in (ACCEPTED, "SCHEDULED"):
        raise HTTPException(409, "Approve the order before starting production")
    await transition_order(order_id, IN_PRODUCTION, ctx["user_id"], note="Production started",
                           notify_user_ids=[order["customer_id"]], event="production_started")
    return {"status": IN_PRODUCTION}


@router.post("/orders/{order_id}/production/batch")
async def add_batch(order_id: str, body: ProductionBatchBody, ctx: dict = Depends(owner_only)):
    order = await _guard_owns(ctx, order_id)
    if order.get("status") != IN_PRODUCTION:
        raise HTTPException(409, "Start production before adding a batch")
    return await record_production_batch(
        order=order,
        quantity=body.quantity,
        actor_id=ctx["user_id"],
        remarks=body.remarks,
        batch_reference=body.batch_reference,
        consume_materials=body.consume_materials,
    )


@router.post("/orders/{order_id}/production/complete")
async def complete_production(order_id: str, ctx: dict = Depends(owner_only)):
    order = await _guard_owns(ctx, order_id)
    if order.get("status") != IN_PRODUCTION:
        raise HTTPException(409, "Order is not in production")
    rows = await production_batches.aggregate([
        {"$match": {"order_id": order_id}},
        {"$group": {"_id": None, "total": {"$sum": "$quantity"}}},
    ]).to_list(1)
    produced = float(rows[0]["total"] if rows else 0)
    required = float(order.get("quantity") or 0)
    if required <= 0 or produced + 0.001 < required * 0.98:
        raise HTTPException(409, f"Production is incomplete ({produced:g} / {required:g} m³)")
    await transition_order(order_id, PRODUCTION_COMPLETE, ctx["user_id"], note="Production complete",
                           notify_user_ids=[order["customer_id"]], event="production_complete")
    return {"status": PRODUCTION_COMPLETE, "produced": produced, "required": required}


@router.get("/orders/{order_id}/production")
async def production_detail(order_id: str, ctx: dict = Depends(owner_only)):
    order = await _guard_owns(ctx, order_id)
    batches = await production_batches.find({"order_id": order_id}).sort("created_at", 1).to_list(100)
    produced = sum(b.get("quantity", 0) for b in batches)
    return {
        "status": order.get("status"), "required": order.get("quantity"), "produced": produced,
        "batches": [{
            "id": str(b["_id"]),
            "quantity": b.get("quantity"),
            "batch_reference": b.get("batch_reference"),
            "mix_design_version": b.get("mix_design_version"),
            "material_consumption": b.get("material_consumption", []),
            "remarks": b.get("remarks"),
            "at": b.get("created_at").isoformat() if b.get("created_at") else None,
        } for b in batches],
    }


# ---------------- Invoices & Ledger ----------------

def _serialize_invoice(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "invoice_number": doc.get("invoice_number"),
        "order_number": doc.get("order_number"),
        "customer_name": doc.get("customer_name"),
        "grade": doc.get("grade"),
        "quantity": doc.get("quantity"),
        "rate": doc.get("rate"),
        "gst_rate": doc.get("gst_rate"),
        "subtotal": doc.get("subtotal"),
        "gst": doc.get("gst"),
        "total": doc.get("total"),
        "paid": doc.get("paid", 0),
        "balance": round(doc.get("total", 0) - doc.get("paid", 0), 2),
        "status": doc.get("status"),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
    }


@router.post("/orders/{order_id}/invoice")
async def create_invoice(order_id: str, ctx: dict = Depends(owner_only)):
    order = await _guard_owns(ctx, order_id)
    if order.get("status") != "DELIVERED":
        raise HTTPException(409, "Invoice can be raised only after delivery")
    doc = await create_invoice_for_order(order)
    await orders.update_one(
        {"_id": order["_id"]},
        {"$set": {"invoice_number": doc["invoice_number"]}},
    )
    return {"invoice": _serialize_invoice(doc)}


@router.get("/invoices")
async def list_invoices(ctx: dict = Depends(owner_only)):
    plant_ids = await _scoped_plant_ids(ctx)
    docs = await invoices.find({"plant_id": {"$in": plant_ids}}).sort("created_at", -1).to_list(500)
    total = sum(d.get("total", 0) for d in docs)
    paid = sum(d.get("paid", 0) for d in docs)
    return {
        "invoices": [_serialize_invoice(d) for d in docs],
        "summary": {"billed": round(total, 2), "received": round(paid, 2), "outstanding": round(total - paid, 2)},
    }


@router.post("/invoices/{invoice_id}/payment")
async def record_payment(invoice_id: str, body: PaymentBody, ctx: dict = Depends(owner_only)):
    plant_ids = await _scoped_plant_ids(ctx)
    inv = await invoices.find_one({"_id": await _oid(invoice_id), "plant_id": {"$in": plant_ids}})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    balance = round(inv.get("total", 0) - inv.get("paid", 0), 2)
    if body.amount > balance + 0.01:
        raise HTTPException(422, f"Amount exceeds outstanding balance ({balance})")
    now = datetime.now(timezone.utc)
    await payments.insert_one({
        "invoice_id": invoice_id, "order_id": inv.get("order_id"), "plant_id": inv["plant_id"],
        "customer_id": inv.get("customer_id"), "amount": body.amount, "method": body.method,
        "note": body.note, "created_at": now,
    })
    new_paid = round(inv.get("paid", 0) + body.amount, 2)
    status = "PAID" if new_paid >= inv.get("total", 0) - 0.01 else "PARTIAL"
    await invoices.update_one({"_id": inv["_id"]}, {"$set": {"paid": new_paid, "status": status}})
    if inv.get("order_id"):
        await orders.update_one({"_id": await _oid(inv["order_id"])}, {"$set": {"payment_status": status}})
    await write_audit(ctx["user_id"], "payment.record", "invoice", invoice_id, {"amount": body.amount})
    return {"paid": new_paid, "status": status, "balance": round(inv.get("total", 0) - new_paid, 2)}


@router.get("/ledger")
async def ledger(ctx: dict = Depends(owner_only)):
    plant_ids = await _scoped_plant_ids(ctx)
    docs = await invoices.find({"plant_id": {"$in": plant_ids}}).to_list(1000)
    by_customer: dict = {}
    for d in docs:
        k = d.get("customer_name") or "Customer"
        e = by_customer.setdefault(k, {"customer": k, "billed": 0, "paid": 0})
        e["billed"] = round(e["billed"] + d.get("total", 0), 2)
        e["paid"] = round(e["paid"] + d.get("paid", 0), 2)
    rows = [{**e, "balance": round(e["billed"] - e["paid"], 2)} for e in by_customer.values()]
    return {"ledger": rows}


@router.get("/insights")
async def insights(ctx: dict = Depends(owner_only)):
    """Last 7 days: volume ordered vs delivered + payments received per day."""
    plant_ids = await _scoped_plant_ids(ctx)
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    days = [(today - timedelta(days=i)) for i in range(6, -1, -1)]
    labels = [d.strftime("%a") for d in days]
    keys = [d.strftime("%Y-%m-%d") for d in days]

    ordered = {k: 0.0 for k in keys}
    delivered = {k: 0.0 for k in keys}
    paid = {k: 0.0 for k in keys}

    all_orders = await orders.find({"plant_id": {"$in": plant_ids}}).to_list(3000)
    for o in all_orders:
        c = o.get("created_at")
        if c:
            k = c.replace(tzinfo=timezone.utc).strftime("%Y-%m-%d")
            if k in ordered:
                ordered[k] += o.get("quantity", 0)
        if o.get("status") == "DELIVERED":
            dt = o.get("updated_at") or o.get("created_at")
            if dt:
                k = dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%d")
                if k in delivered:
                    delivered[k] += o.get("delivered_quantity") or o.get("quantity", 0)

    pays = await payments.find({"plant_id": {"$in": plant_ids}}).to_list(3000)
    for p in pays:
        c = p.get("created_at")
        if c:
            k = c.replace(tzinfo=timezone.utc).strftime("%Y-%m-%d")
            if k in paid:
                paid[k] += p.get("amount", 0)

    return {
        "labels": labels,
        "ordered": [round(ordered[k], 1) for k in keys],
        "delivered": [round(delivered[k], 1) for k in keys],
        "payments": [round(paid[k], 0) for k in keys],
        "totals": {
            "ordered": round(sum(ordered.values()), 1),
            "delivered": round(sum(delivered.values()), 1),
            "payments": round(sum(paid.values()), 0),
        },
    }
