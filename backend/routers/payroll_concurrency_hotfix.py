"""Concurrency-safe payroll mutations for the PR32 workforce payroll lifecycle.

These routes intentionally shadow the matching PR32 mutation routes. They add
compare-and-set protection to draft/owner decisions and an explicit POSTING
reservation before finance expense creation so concurrent users cannot lose an
owner decision or leave a salary expense posted for a payroll that was returned.
"""
from fastapi import APIRouter, Depends, HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from business_access import oid
from database import expenses, payroll_records, users
from notifications import record_notification
from roles import Role
from security import require_role
from routers.workforce import EMPLOYEE_ROLES
from routers.workforce_reports import (
    PayrollDraftBody,
    PayrollOwnerDecisionBody,
    PayrollPaidBody,
    _plant_report,
    _require_accountant_plant,
    _require_owner_plant,
    _serialize,
    _utcnow,
    month_bounds,
    payroll_net,
)

router = APIRouter(prefix="/api/workforce-reports", tags=["workforce-reports"])
accountant_only = require_role(Role.ACCOUNTANT.value)
owner_only = require_role(Role.PLANT_OWNER.value)


def _cas_filter(current: dict) -> dict:
    """Match the exact lifecycle version observed by the caller."""
    query = {"_id": current["_id"], "status": current.get("status")}
    if "updated_at" in current:
        query["updated_at"] = current.get("updated_at")
    else:
        query["updated_at"] = {"$exists": False}
    return query


@router.put("/plants/{plant_id}/payroll/{month}/{user_id}/draft")
async def prepare_payroll_draft_safe(
    plant_id: str,
    month: str,
    user_id: str,
    body: PayrollDraftBody,
    ctx: dict = Depends(accountant_only),
):
    await _require_accountant_plant(ctx, plant_id)
    _, last = month_bounds(month)
    if body.paid_days > last.day:
        raise HTTPException(422, f"Paid days cannot exceed {last.day} for {month}")

    user = await users.find_one(
        {"_id": oid(user_id), "plant_id": plant_id, "primary_role": {"$in": list(EMPLOYEE_ROLES)}}
    )
    if not user:
        raise HTTPException(404, "Staff member not found for this plant")

    net = payroll_net(body.basic_amount, body.allowances, body.overtime_amount, body.deductions)
    if net < 0:
        raise HTTPException(422, "Payroll net amount cannot be negative")

    key = {"plant_id": plant_id, "user_id": user_id, "month": month}
    existing = await payroll_records.find_one(key)
    if existing and existing.get("status") not in ("DRAFT", "RETURNED"):
        raise HTTPException(409, f"{existing.get('status') or 'Current'} payroll cannot be edited")

    report = await _plant_report(plant_id, month)
    evidence = next((item for item in report["employees"] if item["user_id"] == user_id), None)
    now = _utcnow()
    payload = body.model_dump()
    payload.update(
        {
            **key,
            "user_name": user.get("name") or "Staff",
            "net_amount": net,
            "status": "DRAFT",
            "prepared_by": ctx["user_id"],
            "prepared_at": now,
            "updated_by": ctx["user_id"],
            "updated_at": now,
            "attendance_evidence": {
                "attendance_days": (evidence or {}).get("attendance_days", 0),
                "completed_shifts": (evidence or {}).get("completed_shifts", 0),
                "attendance_hours": (evidence or {}).get("attendance_hours", 0),
                "approved_leave_days": (evidence or {}).get("approved_leave_days", 0),
                "leave_days_by_type": (evidence or {}).get("leave_days_by_type", {}),
            },
        }
    )

    if existing:
        result = await payroll_records.update_one(_cas_filter(existing), {"$set": payload})
        if result.matched_count != 1:
            raise HTTPException(409, "Payroll changed concurrently; refresh before saving the draft")
    else:
        try:
            await payroll_records.insert_one({**payload, "created_at": now})
        except DuplicateKeyError as exc:
            raise HTTPException(409, "Payroll was created concurrently; refresh before saving") from exc

    doc = await payroll_records.find_one(key)
    await write_audit(
        ctx["user_id"],
        "workforce.payroll.draft",
        "payroll_record",
        str((doc or {}).get("_id") or f"{plant_id}:{user_id}:{month}"),
        {"plant_id": plant_id, "month": month, "net_amount": net},
    )
    return {"payroll": _serialize(doc)}


@router.post("/plants/{plant_id}/payroll/{month}/{user_id}/owner-decision")
async def owner_payroll_decision_safe(
    plant_id: str,
    month: str,
    user_id: str,
    body: PayrollOwnerDecisionBody,
    ctx: dict = Depends(owner_only),
):
    await _require_owner_plant(ctx, plant_id)
    month_bounds(month)
    current = await payroll_records.find_one({"plant_id": plant_id, "user_id": user_id, "month": month})
    if not current:
        raise HTTPException(404, "Payroll draft not found")

    if body.action == "APPROVE":
        if current.get("status") == "APPROVED":
            return {"payroll": _serialize(current), "idempotent": True}
        if current.get("status") != "DRAFT":
            raise HTTPException(409, "Only DRAFT payroll can be approved")
        target = "APPROVED"
    else:
        if current.get("status") not in ("DRAFT", "APPROVED"):
            raise HTTPException(409, "Payroll cannot be returned from its current status")
        if not (body.note or "").strip():
            raise HTTPException(422, "Return reason is required")
        target = "RETURNED"

    now = _utcnow()
    updated = await payroll_records.find_one_and_update(
        _cas_filter(current),
        {"$set": {
            "status": target,
            "owner_decision_note": (body.note or "").strip() or None,
            "owner_decided_by": ctx["user_id"],
            "owner_decided_at": now,
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "Payroll changed concurrently; refresh and review the latest amounts")

    await write_audit(
        ctx["user_id"],
        f"workforce.payroll.{target.lower()}",
        "payroll_record",
        str(current["_id"]),
        {"plant_id": plant_id, "month": month},
    )
    await record_notification(
        user_id,
        f"workforce_payroll_{target.lower()}",
        "Payroll approved" if target == "APPROVED" else "Payroll returned for correction",
        f"Your payroll for {month} is {target.lower()}.",
    )
    return {"payroll": _serialize(updated)}


@router.post("/plants/{plant_id}/payroll/{month}/{user_id}/mark-paid")
async def mark_payroll_paid_safe(
    plant_id: str,
    month: str,
    user_id: str,
    body: PayrollPaidBody,
    ctx: dict = Depends(accountant_only),
):
    await _require_accountant_plant(ctx, plant_id)
    month_bounds(month)
    key = {"plant_id": plant_id, "user_id": user_id, "month": month}
    current = await payroll_records.find_one(key)
    if not current:
        raise HTTPException(404, "Payroll record not found")
    if current.get("status") == "PAID":
        return {"payroll": _serialize(current), "idempotent": True}

    # Atomically reserve APPROVED -> POSTING before touching the finance ledger.
    # POSTING blocks the owner-return route and also makes retries recoverable.
    if current.get("status") == "APPROVED":
        now = _utcnow()
        reserved = await payroll_records.find_one_and_update(
            _cas_filter(current),
            {"$set": {
                "status": "POSTING",
                "payment_started_by": ctx["user_id"],
                "payment_started_at": now,
                "updated_at": now,
            }},
            return_document=ReturnDocument.AFTER,
        )
        if reserved:
            current = reserved
        else:
            current = await payroll_records.find_one(key)
            if current and current.get("status") == "PAID":
                return {"payroll": _serialize(current), "idempotent": True}
            if not current or current.get("status") != "POSTING":
                raise HTTPException(409, "Payroll changed concurrently; refresh before recording payment")
    elif current.get("status") != "POSTING":
        raise HTTPException(409, "Plant Owner approval is required before payment")

    amount = round(float(current.get("net_amount") or 0), 2)
    if amount < 0:
        raise HTTPException(409, "Invalid payroll net amount")

    payroll_key = f"{plant_id}:{user_id}:{month}"
    finance_doc = await expenses.find_one({"payroll_key": payroll_key})
    if not finance_doc:
        now = _utcnow()
        requested_paid_on = body.paid_on or now.date()
        candidate = {
            "plant_id": plant_id,
            "category": "salary",
            "amount": amount,
            "expense_date": requested_paid_on.isoformat(),
            "vendor": current.get("user_name"),
            "reference": body.payment_reference.strip(),
            "payment_method": body.payment_method,
            "notes": (body.note or "").strip() or f"Payroll {month}",
            "payroll_key": payroll_key,
            "source": "PAYROLL",
            "created_by": ctx["user_id"],
            "created_at": now,
        }
        try:
            inserted = await expenses.insert_one(candidate)
            candidate["_id"] = inserted.inserted_id
            finance_doc = candidate
        except DuplicateKeyError:
            finance_doc = await expenses.find_one({"payroll_key": payroll_key})
            if not finance_doc:
                raise HTTPException(409, "Payroll finance posting conflict; refresh and retry")

    expense_id = finance_doc["_id"]
    paid_on_value = str(finance_doc.get("expense_date"))
    payment_method = str(finance_doc.get("payment_method") or body.payment_method)
    payment_reference = str(finance_doc.get("reference") or body.payment_reference.strip())
    now = _utcnow()
    updated = await payroll_records.find_one_and_update(
        {"_id": current["_id"], "status": "POSTING"},
        {"$set": {
            "status": "PAID",
            "paid_by": ctx["user_id"],
            "paid_at": now,
            "paid_on": paid_on_value,
            "payment_method": payment_method,
            "payment_reference": payment_reference,
            "finance_expense_id": str(expense_id),
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        latest = await payroll_records.find_one({"_id": current["_id"]})
        if latest and latest.get("status") == "PAID":
            return {"payroll": _serialize(latest), "idempotent": True}
        raise HTTPException(409, "Payroll payment is reserved for reconciliation; retry the payment action")

    await write_audit(
        ctx["user_id"],
        "workforce.payroll.paid",
        "payroll_record",
        str(current["_id"]),
        {"plant_id": plant_id, "month": month, "amount": amount, "finance_expense_id": str(expense_id)},
    )
    await record_notification(
        user_id,
        "workforce_payroll_paid",
        "Payroll marked paid",
        f"Your payroll for {month} was marked paid. Reference: {payment_reference}.",
    )
    return {"payroll": _serialize(updated)}
