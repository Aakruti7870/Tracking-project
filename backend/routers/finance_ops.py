"""Commercial, finance, workforce and procurement APIs."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo import ReturnDocument, UpdateOne
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from business_access import oid, require_business_role, require_visible_plant
from business_models import (
    AttendanceActionBody,
    CustomerQuotationDecisionBody,
    DieselTransactionBody,
    ExpenseBody,
    PayrollRecordBody,
    PurchaseReceiptBody,
    QuotationBody,
    QuotationRequestResponseBody,
)
from database import (
    diesel_transactions,
    expenses,
    materials,
    next_sequence,
    payroll_records,
    purchase_receipts,
    plants,
    quotations,
    quotation_requests,
    staff_attendance,
    stock_movements,
    suppliers,
    users,
    vehicles,
)
from notifications import record_notification
from roles import Role
from security import current_user

router = APIRouter(prefix="/api/ops", tags=["business-operations"])


def _serialize(doc: dict) -> dict:
    out = {**doc, "id": str(doc["_id"])}
    out.pop("_id", None)
    for key, value in list(out.items()):
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
    return out


@router.get("/plants/{plant_id}/quotations")
async def list_quotations(plant_id: str, ctx: dict = Depends(current_user)):
    require_business_role(
        ctx,
        Role.PLANT_OWNER.value,
        Role.ADMIN.value,
        Role.ACCOUNTANT.value,
        Role.CENTRAL_ADMIN.value,
    )
    await require_visible_plant(ctx, plant_id)
    today = datetime.now(timezone.utc).date().isoformat()
    await quotations.update_many(
        {"plant_id": plant_id, "status": "OPEN", "valid_until": {"$lt": today}},
        {"$set": {"status": "EXPIRED", "expired_at": datetime.now(timezone.utc)}},
    )
    docs = await quotations.find({"plant_id": plant_id}).sort("created_at", -1).to_list(1000)
    return {"quotations": [_serialize(d) for d in docs]}


@router.get("/customer/quotations")
async def customer_quotations(ctx: dict = Depends(current_user)):
    require_business_role(ctx, Role.CUSTOMER.value)
    today = datetime.now(timezone.utc).date().isoformat()
    await quotations.update_many(
        {"customer_id": ctx["user_id"], "status": "OPEN", "valid_until": {"$lt": today}},
        {"$set": {"status": "EXPIRED", "expired_at": datetime.now(timezone.utc)}},
    )
    docs = await quotations.find({"customer_id": ctx["user_id"]}).sort("created_at", -1).to_list(500)
    return {"quotations": [_serialize(d) for d in docs]}


@router.post("/customer/quotations/{quotation_id}/decision")
async def customer_quotation_decision(
    quotation_id: str,
    body: CustomerQuotationDecisionBody,
    ctx: dict = Depends(current_user),
):
    require_business_role(ctx, Role.CUSTOMER.value)
    quote = await quotations.find_one({"_id": oid(quotation_id), "customer_id": ctx["user_id"]})
    if not quote:
        raise HTTPException(404, "Quotation not found")
    if quote.get("status") != "OPEN":
        raise HTTPException(409, "Quotation is no longer open")
    today = datetime.now(timezone.utc).date().isoformat()
    if str(quote.get("valid_until") or "") < today:
        await quotations.update_one(
            {"_id": quote["_id"], "status": "OPEN"},
            {"$set": {"status": "EXPIRED", "expired_at": datetime.now(timezone.utc)}},
        )
        raise HTTPException(409, "Quotation has expired")

    now = datetime.now(timezone.utc)
    target = "ACCEPTED" if body.action == "ACCEPT" else "DECLINED"
    updated = await quotations.find_one_and_update(
        {"_id": quote["_id"], "customer_id": ctx["user_id"], "status": "OPEN"},
        {"$set": {
            "status": target,
            "customer_response_reason": (body.reason or "").strip() or None,
            "customer_responded_at": now,
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "Quotation was already handled")
    await write_audit(
        ctx["user_id"], f"quotation.{target.lower()}", "quotation", quotation_id,
        {"plant_id": quote["plant_id"], "quotation_number": quote["quotation_number"]},
    )
    plant = await plants.find_one({"_id": oid(quote["plant_id"])})
    recipients = {quote.get("created_by"), (plant or {}).get("owner_id")}
    for recipient in recipients:
        if recipient:
            await record_notification(
                recipient, f"quotation_{target.lower()}", f"Quotation {target.lower()}",
                f"{quote.get('customer_name') or 'Customer'} {target.lower()} {quote['quotation_number']}.",
            )
    return {"quotation": _serialize(updated)}


@router.post("/plants/{plant_id}/quotations")
async def create_quotation(
    plant_id: str,
    body: QuotationBody,
    ctx: dict = Depends(current_user),
):
    require_business_role(
        ctx,
        Role.PLANT_OWNER.value,
        Role.ADMIN.value,
        Role.ACCOUNTANT.value,
        Role.CENTRAL_ADMIN.value,
    )
    await require_visible_plant(ctx, plant_id)
    if body.customer_id:
        customer = await users.find_one({"_id": oid(body.customer_id), "primary_role": Role.CUSTOMER.value})
        if not customer:
            raise HTTPException(422, "Customer not found")
    seq = await next_sequence(f"quotation:{plant_id}")
    subtotal = body.quantity_m3 * body.rate_per_m3 + body.transport_amount + body.pumping_amount
    gst_amount = round(subtotal * body.gst_rate / 100, 2)
    now = datetime.now(timezone.utc)
    doc = body.model_dump(mode="json")
    doc.update(
        {
            "quotation_number": f"QT-{seq:06d}",
            "plant_id": plant_id,
            "subtotal": round(subtotal, 2),
            "gst_amount": gst_amount,
            "total": round(subtotal + gst_amount, 2),
            "status": "OPEN",
            "created_at": now,
            "created_by": ctx["user_id"],
        }
    )
    result = await quotations.insert_one(doc)
    doc["_id"] = result.inserted_id
    return {"quotation": _serialize(doc)}


@router.get("/plants/{plant_id}/quotation-requests")
async def list_quotation_requests(
    plant_id: str,
    status: str | None = Query(default=None, pattern=r"^(REQUESTED|QUOTED|DECLINED)$"),
    ctx: dict = Depends(current_user),
):
    require_business_role(
        ctx,
        Role.PLANT_OWNER.value,
        Role.ADMIN.value,
        Role.ACCOUNTANT.value,
        Role.CENTRAL_ADMIN.value,
    )
    await require_visible_plant(ctx, plant_id)
    query: dict = {"plant_id": plant_id}
    if status:
        query["status"] = status
    docs = await quotation_requests.find(query).sort("created_at", -1).to_list(1000)
    return {"requests": [_serialize(d) for d in docs]}


@router.post("/plants/{plant_id}/quotation-requests/{request_id}/respond")
async def respond_to_quotation_request(
    plant_id: str,
    request_id: str,
    body: QuotationRequestResponseBody,
    ctx: dict = Depends(current_user),
):
    require_business_role(
        ctx,
        Role.PLANT_OWNER.value,
        Role.ADMIN.value,
        Role.ACCOUNTANT.value,
        Role.CENTRAL_ADMIN.value,
    )
    await require_visible_plant(ctx, plant_id)
    request = await quotation_requests.find_one(
        {"_id": oid(request_id), "plant_id": plant_id, "status": "REQUESTED"}
    )
    if not request:
        raise HTTPException(409, "Quotation request is no longer pending")

    now = datetime.now(timezone.utc)
    if body.action == "DECLINE":
        reason = (body.decline_reason or "").strip()
        if not reason:
            raise HTTPException(422, "Decline reason is required")
        updated = await quotation_requests.find_one_and_update(
            {"_id": request["_id"], "plant_id": plant_id, "status": "REQUESTED"},
            {"$set": {
                "status": "DECLINED",
                "decline_reason": reason,
                "responded_at": now,
                "responded_by": ctx["user_id"],
                "updated_at": now,
            }},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            raise HTTPException(409, "Quotation request was already handled")
        await write_audit(ctx["user_id"], "quotation_request.decline", "quotation_request", request_id, {"plant_id": plant_id})
        await record_notification(
            request["customer_id"], "quotation_declined", "Quotation request update",
            f"{request.get('plant_name') or 'The plant'} could not quote this request. Reason: {reason}",
        )
        return {"request": _serialize(updated)}

    if body.rate_per_m3 is None or body.valid_until is None:
        raise HTTPException(422, "Rate and validity date are required")
    if body.valid_until < now.date():
        raise HTTPException(422, "Validity date cannot be in the past")

    claimed = await quotation_requests.find_one_and_update(
        {"_id": request["_id"], "plant_id": plant_id, "status": "REQUESTED"},
        {"$set": {"status": "PROCESSING", "updated_at": now, "responded_by": ctx["user_id"]}},
        return_document=ReturnDocument.AFTER,
    )
    if not claimed:
        raise HTTPException(409, "Quotation request was already handled")

    seq = await next_sequence(f"quotation:{plant_id}")
    subtotal = (
        float(request["quantity"]) * body.rate_per_m3
        + body.transport_amount
        + body.pumping_amount
    )
    gst_amount = round(subtotal * body.gst_rate / 100, 2)
    quote = {
        "quotation_number": f"QT-{seq:06d}",
        "request_id": request_id,
        "plant_id": plant_id,
        "customer_id": request["customer_id"],
        "customer_name": request.get("customer_name") or "Customer",
        "customer_mobile": request.get("customer_mobile"),
        "site_id": request.get("site_id"),
        "site_name": request["site_name"],
        "site_address": request["site_address"],
        "grade": request["grade"],
        "quantity_m3": request["quantity"],
        "rate_per_m3": body.rate_per_m3,
        "gst_rate": body.gst_rate,
        "transport_amount": body.transport_amount,
        "pumping_amount": body.pumping_amount,
        "subtotal": round(subtotal, 2),
        "gst_amount": gst_amount,
        "total": round(subtotal + gst_amount, 2),
        "valid_until": body.valid_until.isoformat(),
        "notes": body.notes,
        "status": "OPEN",
        "created_at": now,
        "created_by": ctx["user_id"],
    }
    result = await quotations.insert_one(quote)
    quote["_id"] = result.inserted_id
    await quotation_requests.update_one(
        {"_id": request["_id"], "status": "PROCESSING"},
        {"$set": {
            "status": "QUOTED",
            "quotation_id": str(result.inserted_id),
            "quotation_number": quote["quotation_number"],
            "quoted_total": quote["total"],
            "responded_at": now,
            "updated_at": now,
        }},
    )
    await write_audit(
        ctx["user_id"], "quotation_request.quote", "quotation_request", request_id,
        {"plant_id": plant_id, "quotation_id": str(result.inserted_id), "total": quote["total"]},
    )
    await record_notification(
        request["customer_id"], "quotation_received", "Official quotation received",
        f"{request.get('plant_name') or 'The plant'} sent {quote['quotation_number']} for ₹{quote['total']:,.2f}.",
    )
    return {"quotation": _serialize(quote), "request_status": "QUOTED"}


@router.get("/plants/{plant_id}/expenses")
async def list_expenses(plant_id: str, ctx: dict = Depends(current_user)):
    require_business_role(
        ctx, Role.PLANT_OWNER.value, Role.ADMIN.value, Role.ACCOUNTANT.value, Role.CENTRAL_ADMIN.value
    )
    await require_visible_plant(ctx, plant_id)
    docs = await expenses.find({"plant_id": plant_id}).sort("expense_date", -1).to_list(2000)
    total = round(sum(float(d.get("amount") or 0) for d in docs), 2)
    return {"total": total, "expenses": [_serialize(d) for d in docs]}


@router.post("/plants/{plant_id}/expenses")
async def create_expense(plant_id: str, body: ExpenseBody, ctx: dict = Depends(current_user)):
    require_business_role(
        ctx, Role.PLANT_OWNER.value, Role.ADMIN.value, Role.ACCOUNTANT.value, Role.CENTRAL_ADMIN.value
    )
    await require_visible_plant(ctx, plant_id)
    now = datetime.now(timezone.utc)
    doc = body.model_dump(mode="json")
    doc.update({"plant_id": plant_id, "created_at": now, "created_by": ctx["user_id"]})
    result = await expenses.insert_one(doc)
    doc["_id"] = result.inserted_id
    return {"expense": _serialize(doc)}


async def _diesel_balance(plant_id: str) -> float:
    pipeline = [
        {"$match": {"plant_id": plant_id}},
        {"$group": {"_id": None, "balance": {"$sum": "$signed_litres"}}},
    ]
    rows = await diesel_transactions.aggregate(pipeline).to_list(1)
    return round(float(rows[0]["balance"] if rows else 0), 3)


@router.get("/plants/{plant_id}/diesel")
async def list_diesel(plant_id: str, ctx: dict = Depends(current_user)):
    require_business_role(
        ctx,
        Role.PLANT_OWNER.value,
        Role.ADMIN.value,
        Role.ACCOUNTANT.value,
        Role.FLEET_MANAGER.value,
        Role.STORE_MANAGER.value,
        Role.CENTRAL_ADMIN.value,
    )
    await require_visible_plant(ctx, plant_id)
    docs = await diesel_transactions.find({"plant_id": plant_id}).sort("created_at", -1).to_list(2000)
    return {"balance_litres": await _diesel_balance(plant_id), "transactions": [_serialize(d) for d in docs]}


@router.post("/plants/{plant_id}/diesel")
async def create_diesel_transaction(
    plant_id: str,
    body: DieselTransactionBody,
    ctx: dict = Depends(current_user),
):
    require_business_role(
        ctx,
        Role.PLANT_OWNER.value,
        Role.ADMIN.value,
        Role.FLEET_MANAGER.value,
        Role.STORE_MANAGER.value,
        Role.CENTRAL_ADMIN.value,
    )
    await require_visible_plant(ctx, plant_id)
    if body.vehicle_id:
        vehicle = await vehicles.find_one({"_id": oid(body.vehicle_id), "plant_id": plant_id})
        if not vehicle:
            raise HTTPException(422, "Vehicle not found for this plant")
    if body.supplier_id:
        supplier = await suppliers.find_one({"_id": oid(body.supplier_id), "plant_id": plant_id})
        if not supplier:
            raise HTTPException(422, "Supplier not found for this plant")
    signed = body.litres if body.transaction_type in ("IN", "ADJUSTMENT") else -body.litres
    current = await _diesel_balance(plant_id)
    if current + signed < -0.001:
        raise HTTPException(409, "Diesel stock cannot become negative")
    now = datetime.now(timezone.utc)
    doc = body.model_dump()
    doc.update(
        {
            "plant_id": plant_id,
            "signed_litres": signed,
            "created_at": now,
            "created_by": ctx["user_id"],
        }
    )
    result = await diesel_transactions.insert_one(doc)
    doc["_id"] = result.inserted_id
    return {"balance_litres": await _diesel_balance(plant_id), "transaction": _serialize(doc)}


@router.get("/plants/{plant_id}/payroll/{month}")
async def list_payroll(plant_id: str, month: str, ctx: dict = Depends(current_user)):
    require_business_role(
        ctx, Role.PLANT_OWNER.value, Role.ADMIN.value, Role.ACCOUNTANT.value, Role.CENTRAL_ADMIN.value
    )
    await require_visible_plant(ctx, plant_id)
    docs = await payroll_records.find({"plant_id": plant_id, "month": month}).sort("user_name", 1).to_list(1000)
    return {"payroll": [_serialize(d) for d in docs]}


@router.put("/plants/{plant_id}/payroll")
async def upsert_payroll(
    plant_id: str,
    body: PayrollRecordBody,
    ctx: dict = Depends(current_user),
):
    require_business_role(
        ctx, Role.PLANT_OWNER.value, Role.ADMIN.value, Role.ACCOUNTANT.value, Role.CENTRAL_ADMIN.value
    )
    await require_visible_plant(ctx, plant_id)
    user = await users.find_one({"_id": oid(body.user_id), "plant_id": plant_id})
    if not user:
        raise HTTPException(422, "Staff member not found for this plant")
    net = body.basic_amount + body.allowances + body.overtime_amount - body.deductions
    if net < 0:
        raise HTTPException(422, "Payroll net amount cannot be negative")
    now = datetime.now(timezone.utc)
    payload = body.model_dump()
    payload.update(
        {
            "plant_id": plant_id,
            "user_name": user.get("name"),
            "net_amount": round(net, 2),
            "updated_at": now,
            "updated_by": ctx["user_id"],
        }
    )
    await payroll_records.update_one(
        {"plant_id": plant_id, "user_id": body.user_id, "month": body.month},
        {"$set": payload, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    doc = await payroll_records.find_one(
        {"plant_id": plant_id, "user_id": body.user_id, "month": body.month}
    )
    return {"payroll": _serialize(doc)}


@router.post("/plants/{plant_id}/attendance/checkin")
async def staff_checkin(
    plant_id: str,
    body: AttendanceActionBody,
    ctx: dict = Depends(current_user),
):
    require_business_role(
        ctx,
        Role.PLANT_OWNER.value,
        Role.ADMIN.value,
        Role.DISPATCHER.value,
        Role.OPERATOR.value,
        Role.SUPERVISOR.value,
        Role.ACCOUNTANT.value,
        Role.QUALITY_ENGINEER.value,
        Role.FLEET_MANAGER.value,
        Role.STORE_MANAGER.value,
    )
    await require_visible_plant(ctx, plant_id)
    date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc)
    existing = await staff_attendance.find_one({"user_id": ctx["user_id"], "date": date_key})
    if existing and existing.get("check_in"):
        raise HTTPException(409, "Already checked in today")
    await staff_attendance.update_one(
        {"user_id": ctx["user_id"], "date": date_key},
        {
            "$set": {
                "plant_id": plant_id,
                "user_name": ctx["user"].get("name"),
                "check_in": now,
                "check_in_lat": body.lat,
                "check_in_lng": body.lng,
                "check_in_note": body.note,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return {"status": "checked_in", "at": now.isoformat()}


@router.post("/plants/{plant_id}/attendance/checkout")
async def staff_checkout(
    plant_id: str,
    body: AttendanceActionBody,
    ctx: dict = Depends(current_user),
):
    await require_visible_plant(ctx, plant_id)
    date_key = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now = datetime.now(timezone.utc)
    doc = await staff_attendance.find_one({"user_id": ctx["user_id"], "date": date_key, "plant_id": plant_id})
    if not doc or not doc.get("check_in"):
        raise HTTPException(409, "Check in before checking out")
    if doc.get("check_out"):
        raise HTTPException(409, "Already checked out today")
    await staff_attendance.update_one(
        {"_id": doc["_id"]},
        {"$set": {"check_out": now, "check_out_lat": body.lat, "check_out_lng": body.lng, "check_out_note": body.note}},
    )
    return {"status": "checked_out", "at": now.isoformat()}


@router.get("/plants/{plant_id}/attendance/{date_key}")
async def attendance_register(plant_id: str, date_key: str, ctx: dict = Depends(current_user)):
    require_business_role(
        ctx, Role.PLANT_OWNER.value, Role.ADMIN.value, Role.ACCOUNTANT.value, Role.CENTRAL_ADMIN.value
    )
    await require_visible_plant(ctx, plant_id)
    docs = await staff_attendance.find({"plant_id": plant_id, "date": date_key}).sort("user_name", 1).to_list(1000)
    return {"attendance": [_serialize(d) for d in docs]}


@router.get("/plants/{plant_id}/purchases")
async def list_purchases(plant_id: str, ctx: dict = Depends(current_user)):
    require_business_role(
        ctx,
        Role.PLANT_OWNER.value,
        Role.ADMIN.value,
        Role.ACCOUNTANT.value,
        Role.STORE_MANAGER.value,
        Role.CENTRAL_ADMIN.value,
    )
    await require_visible_plant(ctx, plant_id)
    docs = await purchase_receipts.find({"plant_id": plant_id}).sort("receipt_date", -1).to_list(2000)
    return {"purchases": [_serialize(d) for d in docs]}


@router.post("/plants/{plant_id}/purchases")
async def create_purchase(
    plant_id: str,
    body: PurchaseReceiptBody,
    ctx: dict = Depends(current_user),
):
    require_business_role(
        ctx,
        Role.PLANT_OWNER.value,
        Role.ADMIN.value,
        Role.STORE_MANAGER.value,
        Role.CENTRAL_ADMIN.value,
    )
    await require_visible_plant(ctx, plant_id)
    supplier = await suppliers.find_one({"_id": oid(body.supplier_id), "plant_id": plant_id, "active": True})
    if not supplier:
        raise HTTPException(422, "Supplier not found for this plant")

    material_docs = {}
    for line in body.lines:
        material = await materials.find_one({"_id": oid(line.material_id), "plant_id": plant_id})
        if not material:
            raise HTTPException(422, f"Material {line.material_id} not found for this plant")
        material_docs[line.material_id] = material

    now = datetime.now(timezone.utc)
    base_total = sum(line.quantity * line.rate for line in body.lines)
    total = round(base_total + body.gst_amount + body.freight_amount, 2)
    receipt = body.model_dump(mode="json")
    receipt.update(
        {
            "plant_id": plant_id,
            "supplier_name": supplier.get("name"),
            "base_total": round(base_total, 2),
            "total": total,
            "status": "POSTING",
            "created_at": now,
            "created_by": ctx["user_id"],
        }
    )
    try:
        inserted = await purchase_receipts.insert_one(receipt)
    except DuplicateKeyError:
        raise HTTPException(409, "Purchase receipt number already exists for this plant")

    operations = [
        UpdateOne({"_id": material_docs[line.material_id]["_id"]}, {"$inc": {"stock": line.quantity}})
        for line in body.lines
    ]
    try:
        await materials.bulk_write(operations, ordered=True)
        movements = [
            {
                "plant_id": plant_id,
                "material_id": line.material_id,
                "material_name": material_docs[line.material_id].get("name"),
                "delta": line.quantity,
                "reason": "PURCHASE",
                "reference_id": str(inserted.inserted_id),
                "receipt_number": body.receipt_number,
                "created_at": now,
                "actor_id": ctx["user_id"],
            }
            for line in body.lines
        ]
        await stock_movements.insert_many(movements)
        await purchase_receipts.update_one({"_id": inserted.inserted_id}, {"$set": {"status": "POSTED"}})
    except Exception:
        rollback = [
            UpdateOne({"_id": material_docs[line.material_id]["_id"]}, {"$inc": {"stock": -line.quantity}})
            for line in body.lines
        ]
        await materials.bulk_write(rollback, ordered=False)
        await purchase_receipts.delete_one({"_id": inserted.inserted_id})
        raise HTTPException(500, "Purchase posting failed and was rolled back")

    doc = await purchase_receipts.find_one({"_id": inserted.inserted_id})
    return {"purchase": _serialize(doc)}
