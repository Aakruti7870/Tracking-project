"""Monthly workforce reporting and controlled payroll workflow.

PR32 builds on PR31 attendance, leave, client-visit and expense-claim records.
It deliberately does not infer salary from attendance. Attendance and approved
leave are evidence; an accountant prepares payroll, the plant owner approves
it, and an accountant records payment. Paid payroll is posted once to the
existing finance expense ledger.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from validation import StrictModel
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from business_access import oid, visible_plant_ids
from database import expenses, payroll_records, plants, staff_attendance, users
from notifications import record_notification
from roles import Role
from security import current_user, require_role
from routers.workforce import EMPLOYEE_ROLES, client_visits, expense_claims, leave_requests

router = APIRouter(prefix="/api/workforce-reports", tags=["workforce-reports"])

report_access = require_role(Role.PLANT_OWNER.value, Role.ACCOUNTANT.value)
accountant_only = require_role(Role.ACCOUNTANT.value)
owner_only = require_role(Role.PLANT_OWNER.value)


class PayrollDraftBody(StrictModel):
    basic_amount: float = Field(ge=0, le=100_000_000)
    allowances: float = Field(default=0, ge=0, le=100_000_000)
    overtime_amount: float = Field(default=0, ge=0, le=100_000_000)
    deductions: float = Field(default=0, ge=0, le=100_000_000)
    paid_days: float = Field(default=0, ge=0, le=31)
    notes: str | None = Field(default=None, max_length=3000)


class PayrollOwnerDecisionBody(StrictModel):
    action: Literal["APPROVE", "RETURN"]
    note: str | None = Field(default=None, max_length=1000)


class PayrollPaidBody(StrictModel):
    payment_method: Literal["cash", "upi", "bank_transfer", "cheque", "card"]
    payment_reference: str = Field(min_length=2, max_length=160)
    paid_on: date | None = None
    note: str | None = Field(default=None, max_length=1000)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(doc: dict | None) -> dict | None:
    if not doc:
        return None
    out = {**doc, "id": str(doc["_id"])}
    out.pop("_id", None)
    for key, value in list(out.items()):
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
    return out


def month_bounds(month: str) -> tuple[date, date]:
    try:
        first = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise HTTPException(422, "Month must use YYYY-MM format") from exc
    last = first.replace(day=monthrange(first.year, first.month)[1])
    return first, last


def overlap_days(start: str, end: str, first: date, last: date) -> int:
    try:
        leave_start = date.fromisoformat(start)
        leave_end = date.fromisoformat(end)
    except (TypeError, ValueError):
        return 0
    lo = max(leave_start, first)
    hi = min(leave_end, last)
    return max(0, (hi - lo).days + 1)


def payroll_net(basic: float, allowances: float, overtime: float, deductions: float) -> float:
    return round(float(basic) + float(allowances) + float(overtime) - float(deductions), 2)


async def ensure_indexes() -> None:
    # Base payroll uniqueness already exists in database.ensure_indexes. This
    # unique finance key makes salary posting idempotent even after retries.
    await expenses.create_index(
        "payroll_key",
        unique=True,
        partialFilterExpression={"payroll_key": {"$type": "string"}},
        name="unique_finance_expense_per_payroll",
    )
    await payroll_records.create_index([("plant_id", 1), ("month", 1), ("status", 1)])


async def _report_plant_ids(ctx: dict) -> list[str]:
    if ctx.get("role") == Role.PLANT_OWNER.value:
        return await visible_plant_ids(ctx)
    if ctx.get("role") == Role.ACCOUNTANT.value:
        plant_id = ctx.get("plant_id") or ctx.get("user", {}).get("plant_id")
        if not plant_id:
            raise HTTPException(403, "Plant assignment required")
        return [str(plant_id)]
    raise HTTPException(403, "Workforce reporting access denied")


async def _require_owner_plant(ctx: dict, plant_id: str) -> None:
    if ctx.get("role") != Role.PLANT_OWNER.value:
        raise HTTPException(403, "Plant owner access required")
    if plant_id not in await visible_plant_ids(ctx):
        raise HTTPException(403, "Plant access denied")


async def _require_accountant_plant(ctx: dict, plant_id: str) -> None:
    if ctx.get("role") != Role.ACCOUNTANT.value:
        raise HTTPException(403, "Accountant access required")
    assigned = ctx.get("plant_id") or ctx.get("user", {}).get("plant_id")
    if str(assigned or "") != str(plant_id):
        raise HTTPException(403, "Accountant is not assigned to this plant")


async def _staff_for_plant(plant_id: str) -> list[dict]:
    return await users.find(
        {
            "plant_id": plant_id,
            "primary_role": {"$in": list(EMPLOYEE_ROLES)},
            "status": {"$nin": ["suspended", "disabled", "deleted"]},
        }
    ).sort("name", 1).to_list(2000)


def _attendance_hours(rows: list[dict]) -> float:
    total_seconds = 0.0
    for row in rows:
        check_in = row.get("check_in")
        check_out = row.get("check_out")
        if not isinstance(check_in, datetime) or not isinstance(check_out, datetime):
            continue
        seconds = (check_out - check_in).total_seconds()
        if 0 <= seconds <= 24 * 60 * 60:
            total_seconds += seconds
    return round(total_seconds / 3600, 2)


async def _plant_report(plant_id: str, month: str) -> dict:
    first, last = month_bounds(month)
    start_key = first.isoformat()
    end_key = last.isoformat()
    start_dt = datetime(first.year, first.month, first.day, tzinfo=timezone.utc)
    next_month = (last.replace(day=28) + __import__("datetime").timedelta(days=4)).replace(day=1)
    end_dt = datetime(next_month.year, next_month.month, next_month.day, tzinfo=timezone.utc)

    plant = await plants.find_one({"_id": oid(plant_id)})
    staff = await _staff_for_plant(plant_id)
    user_ids = [str(user["_id"]) for user in staff]

    attendance_rows = await staff_attendance.find(
        {"plant_id": plant_id, "date": {"$gte": start_key, "$lte": end_key}}
    ).to_list(10000)
    leave_rows = await leave_requests.find(
        {
            "plant_id": plant_id,
            "status": "APPROVED",
            "start_date": {"$lte": end_key},
            "end_date": {"$gte": start_key},
        }
    ).to_list(5000)
    visit_rows = await client_visits.find(
        {
            "plant_id": plant_id,
            "status": "COMPLETED",
            "scheduled_for": {"$gte": start_dt, "$lt": end_dt},
        }
    ).to_list(5000)
    claim_rows = await expense_claims.find(
        {
            "plant_id": plant_id,
            "status": "APPROVED",
            "expense_date": {"$gte": start_key, "$lte": end_key},
        }
    ).to_list(5000)
    payroll_rows = await payroll_records.find({"plant_id": plant_id, "month": month}).to_list(5000)

    attendance_by_user: dict[str, list[dict]] = {}
    for row in attendance_rows:
        attendance_by_user.setdefault(str(row.get("user_id")), []).append(row)
    leaves_by_user: dict[str, list[dict]] = {}
    for row in leave_rows:
        leaves_by_user.setdefault(str(row.get("user_id")), []).append(row)
    visits_by_user: dict[str, list[dict]] = {}
    for row in visit_rows:
        visits_by_user.setdefault(str(row.get("user_id")), []).append(row)
    claims_by_user: dict[str, list[dict]] = {}
    for row in claim_rows:
        claims_by_user.setdefault(str(row.get("user_id")), []).append(row)
    payroll_by_user = {str(row.get("user_id")): row for row in payroll_rows}

    employees = []
    for user in staff:
        uid = str(user["_id"])
        att = attendance_by_user.get(uid, [])
        approved_leaves = leaves_by_user.get(uid, [])
        leave_by_type: dict[str, int] = {}
        for leave in approved_leaves:
            days = overlap_days(str(leave.get("start_date")), str(leave.get("end_date")), first, last)
            leave_type = str(leave.get("leave_type") or "OTHER")
            leave_by_type[leave_type] = leave_by_type.get(leave_type, 0) + days
        attendance_days = len({str(row.get("date")) for row in att if row.get("check_in")})
        completed_shifts = len([row for row in att if row.get("check_in") and row.get("check_out")])
        open_shifts = len([row for row in att if row.get("check_in") and not row.get("check_out")])
        approved_expenses = round(sum(float(row.get("amount") or 0) for row in claims_by_user.get(uid, [])), 2)
        payroll = payroll_by_user.get(uid)
        employees.append(
            {
                "user_id": uid,
                "user_name": user.get("name") or "Staff",
                "role": user.get("primary_role") or "staff",
                "attendance_days": attendance_days,
                "completed_shifts": completed_shifts,
                "open_shifts": open_shifts,
                "attendance_hours": _attendance_hours(att),
                "approved_leave_days": sum(leave_by_type.values()),
                "leave_days_by_type": leave_by_type,
                "completed_client_visits": len(visits_by_user.get(uid, [])),
                "approved_expenses": approved_expenses,
                "payroll": _serialize(payroll),
            }
        )

    total_payroll = round(sum(float((row.get("net_amount") or 0)) for row in payroll_rows), 2)
    approved_expense_total = round(sum(float(row.get("amount") or 0) for row in claim_rows), 2)
    return {
        "plant_id": plant_id,
        "plant_name": (plant or {}).get("name") or (plant or {}).get("trade_name") or "RMC Plant",
        "month": month,
        "calendar_days": last.day,
        "employee_count": len(user_ids),
        "present_records": sum(e["attendance_days"] for e in employees),
        "completed_shift_records": sum(e["completed_shifts"] for e in employees),
        "open_shift_records": sum(e["open_shifts"] for e in employees),
        "approved_leave_days": sum(e["approved_leave_days"] for e in employees),
        "completed_client_visits": sum(e["completed_client_visits"] for e in employees),
        "approved_expenses": approved_expense_total,
        "payroll_total": total_payroll,
        "payroll_status_counts": {
            status: len([row for row in payroll_rows if row.get("status") == status])
            for status in ("DRAFT", "RETURNED", "APPROVED", "PAID")
        },
        "employees": employees,
        "payroll_note": "Attendance and leave are evidence only. Paid days and salary amounts require explicit payroll preparation and approval.",
    }


@router.get("/monthly/{month}")
async def monthly_workforce_report(month: str, ctx: dict = Depends(report_access)):
    month_bounds(month)
    plant_ids = await _report_plant_ids(ctx)
    reports = [await _plant_report(plant_id, month) for plant_id in plant_ids]
    return {"month": month, "reports": reports}


@router.put("/plants/{plant_id}/payroll/{month}/{user_id}/draft")
async def prepare_payroll_draft(
    plant_id: str,
    month: str,
    user_id: str,
    body: PayrollDraftBody,
    ctx: dict = Depends(accountant_only),
):
    await _require_accountant_plant(ctx, plant_id)
    first, last = month_bounds(month)
    if body.paid_days > last.day:
        raise HTTPException(422, f"Paid days cannot exceed {last.day} for {month}")
    user = await users.find_one({"_id": oid(user_id), "plant_id": plant_id, "primary_role": {"$in": list(EMPLOYEE_ROLES)}})
    if not user:
        raise HTTPException(404, "Staff member not found for this plant")
    net = payroll_net(body.basic_amount, body.allowances, body.overtime_amount, body.deductions)
    if net < 0:
        raise HTTPException(422, "Payroll net amount cannot be negative")
    existing = await payroll_records.find_one({"plant_id": plant_id, "user_id": user_id, "month": month})
    if existing and existing.get("status") in ("APPROVED", "PAID"):
        raise HTTPException(409, f"{existing.get('status')} payroll cannot be edited")

    report = await _plant_report(plant_id, month)
    evidence = next((item for item in report["employees"] if item["user_id"] == user_id), None)
    now = _utcnow()
    payload = body.model_dump()
    payload.update(
        {
            "plant_id": plant_id,
            "user_id": user_id,
            "user_name": user.get("name") or "Staff",
            "month": month,
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
    await payroll_records.update_one(
        {"plant_id": plant_id, "user_id": user_id, "month": month},
        {"$set": payload, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    doc = await payroll_records.find_one({"plant_id": plant_id, "user_id": user_id, "month": month})
    await write_audit(
        ctx["user_id"],
        "workforce.payroll.draft",
        "payroll_record",
        str((doc or {}).get("_id") or f"{plant_id}:{user_id}:{month}"),
        {"plant_id": plant_id, "month": month, "net_amount": net},
    )
    return {"payroll": _serialize(doc)}


@router.post("/plants/{plant_id}/payroll/{month}/{user_id}/owner-decision")
async def owner_payroll_decision(
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
        {"_id": current["_id"], "status": current["status"]},
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
        raise HTTPException(409, "Payroll changed concurrently; refresh and retry")
    await write_audit(
        ctx["user_id"], f"workforce.payroll.{target.lower()}", "payroll_record", str(current["_id"]),
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
async def mark_payroll_paid(
    plant_id: str,
    month: str,
    user_id: str,
    body: PayrollPaidBody,
    ctx: dict = Depends(accountant_only),
):
    await _require_accountant_plant(ctx, plant_id)
    month_bounds(month)
    current = await payroll_records.find_one({"plant_id": plant_id, "user_id": user_id, "month": month})
    if not current:
        raise HTTPException(404, "Payroll record not found")
    if current.get("status") == "PAID":
        return {"payroll": _serialize(current), "idempotent": True}
    if current.get("status") != "APPROVED":
        raise HTTPException(409, "Plant Owner approval is required before payment")
    amount = round(float(current.get("net_amount") or 0), 2)
    if amount < 0:
        raise HTTPException(409, "Invalid payroll net amount")

    paid_on = body.paid_on or _utcnow().date()
    payroll_key = f"{plant_id}:{user_id}:{month}"
    now = _utcnow()
    finance_doc = {
        "plant_id": plant_id,
        "category": "salary",
        "amount": amount,
        "expense_date": paid_on.isoformat(),
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
        inserted = await expenses.insert_one(finance_doc)
        expense_id = inserted.inserted_id
    except DuplicateKeyError:
        existing_expense = await expenses.find_one({"payroll_key": payroll_key})
        if not existing_expense:
            raise HTTPException(409, "Payroll finance posting conflict; refresh and retry")
        expense_id = existing_expense["_id"]

    updated = await payroll_records.find_one_and_update(
        {"_id": current["_id"], "status": "APPROVED"},
        {"$set": {
            "status": "PAID",
            "paid_by": ctx["user_id"],
            "paid_at": now,
            "paid_on": paid_on.isoformat(),
            "payment_method": body.payment_method,
            "payment_reference": body.payment_reference.strip(),
            "finance_expense_id": str(expense_id),
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        latest = await payroll_records.find_one({"_id": current["_id"]})
        if latest and latest.get("status") == "PAID":
            return {"payroll": _serialize(latest), "idempotent": True}
        raise HTTPException(409, "Salary was posted to finance but payroll finalization needs reconciliation")

    await write_audit(
        ctx["user_id"], "workforce.payroll.paid", "payroll_record", str(current["_id"]),
        {"plant_id": plant_id, "month": month, "amount": amount, "finance_expense_id": str(expense_id)},
    )
    await record_notification(
        user_id,
        "workforce_payroll_paid",
        "Payroll marked paid",
        f"Your payroll for {month} was marked paid. Reference: {body.payment_reference.strip()}.",
    )
    return {"payroll": _serialize(updated)}
