"""Payroll period closure, immutable payslip snapshots and exports.

PR37 sits on top of the existing concurrency-safe payroll lifecycle. Payroll
amounts are still prepared by Accountant, approved by Plant Owner and posted to
finance only through the existing payment workflow. This module adds a final
monthly close step and versioned payslip snapshots; it never recalculates or
mutates paid payroll amounts.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from business_access import oid, visible_plant_ids
from database import db, payroll_records, plants, users
from notifications import record_notification
from roles import Role
from security import require_role
from routers.hr_master import _current_salary, employee_profiles, salary_totals
from routers.payroll_concurrency_hotfix import (
    mark_payroll_paid_safe,
    owner_payroll_decision_safe,
    prepare_payroll_draft_safe,
)
from routers.workforce import EMPLOYEE_ROLES
from routers.workforce_reports import (
    PayrollDraftBody,
    PayrollOwnerDecisionBody,
    PayrollPaidBody,
    _require_accountant_plant,
    _require_owner_plant,
    _serialize,
    month_bounds,
)

router = APIRouter(prefix="/api/payroll-periods", tags=["payroll-periods"])
mutation_guard_router = APIRouter(prefix="/api/workforce-reports", tags=["workforce-reports"])

payroll_periods = db.payroll_periods
payslip_snapshots = db.payroll_payslips

report_access = require_role(Role.PLANT_OWNER.value, Role.ACCOUNTANT.value)
owner_only = require_role(Role.PLANT_OWNER.value)
accountant_only = require_role(Role.ACCOUNTANT.value)
employee_only = require_role(*EMPLOYEE_ROLES)


class ReopenPayrollPeriodBody(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


class ClosePayrollPeriodBody(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _doc_id(value: object) -> str:
    return str(value or "")


def closure_readiness(staff: list[dict], payrolls: list[dict]) -> dict:
    """Pure readiness check used by the close endpoint and unit tests."""
    by_user = {str(row.get("user_id")): row for row in payrolls}
    missing: list[str] = []
    unpaid: list[dict] = []
    locked: list[str] = []
    paid = 0
    for employee in staff:
        uid = str(employee.get("_id") or employee.get("user_id") or "")
        row = by_user.get(uid)
        if not row:
            missing.append(uid)
            continue
        if row.get("payment_lock"):
            locked.append(uid)
        if row.get("status") != "PAID":
            unpaid.append({"user_id": uid, "status": row.get("status") or "MISSING"})
        else:
            paid += 1
    return {
        "ready": not missing and not unpaid and not locked,
        "employee_count": len(staff),
        "paid_count": paid,
        "missing_user_ids": missing,
        "unpaid": unpaid,
        "payment_locked_user_ids": locked,
    }


def payslip_number(month: str, plant_id: str, user_id: str, employee_code: str | None = None) -> str:
    employee_key = (employee_code or user_id[-8:] or "EMP").upper().replace(" ", "-")
    plant_key = (plant_id[-6:] or "PLANT").upper()
    return f"PS-{month.replace('-', '')}-{plant_key}-{employee_key}"


def payslips_to_csv(rows: list[dict]) -> str:
    buffer = io.StringIO()
    fields = [
        "payslip_number", "month", "employee_code", "employee_name", "role",
        "basic_amount", "allowances", "overtime_amount", "deductions", "paid_days",
        "net_amount", "payment_method", "payment_reference", "paid_on", "closure_version",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        payroll = row.get("payroll_snapshot") or {}
        writer.writerow({
            "payslip_number": row.get("payslip_number"),
            "month": row.get("month"),
            "employee_code": row.get("employee_code"),
            "employee_name": row.get("employee_name"),
            "role": row.get("role"),
            "basic_amount": payroll.get("basic_amount", 0),
            "allowances": payroll.get("allowances", 0),
            "overtime_amount": payroll.get("overtime_amount", 0),
            "deductions": payroll.get("deductions", 0),
            "paid_days": payroll.get("paid_days", 0),
            "net_amount": payroll.get("net_amount", 0),
            "payment_method": payroll.get("payment_method"),
            "payment_reference": payroll.get("payment_reference"),
            "paid_on": payroll.get("paid_on"),
            "closure_version": row.get("closure_version"),
        })
    return buffer.getvalue()


async def ensure_indexes() -> None:
    await payroll_periods.create_index([("plant_id", 1), ("month", 1)], unique=True)
    await payslip_snapshots.create_index(
        [("plant_id", 1), ("month", 1), ("user_id", 1), ("closure_version", 1)],
        unique=True,
    )
    await payslip_snapshots.create_index([("user_id", 1), ("month", -1), ("closure_version", -1)])


async def _report_plant_ids(ctx: dict) -> list[str]:
    if ctx.get("role") == Role.PLANT_OWNER.value:
        return await visible_plant_ids(ctx)
    plant_id = ctx.get("plant_id") or ctx.get("user", {}).get("plant_id")
    if not plant_id:
        raise HTTPException(403, "Plant assignment required")
    return [str(plant_id)]


async def _staff(plant_id: str) -> list[dict]:
    return await users.find({
        "plant_id": plant_id,
        "primary_role": {"$in": list(EMPLOYEE_ROLES)},
        "status": {"$nin": ["suspended", "disabled", "deleted"]},
    }).sort("name", 1).to_list(2000)


async def _readiness(plant_id: str, month: str) -> tuple[dict, list[dict], list[dict]]:
    staff = await _staff(plant_id)
    payrolls = await payroll_records.find({"plant_id": plant_id, "month": month}).to_list(5000)
    return closure_readiness(staff, payrolls), staff, payrolls


async def _ensure_period_mutable(plant_id: str, month: str) -> None:
    period = await payroll_periods.find_one({"plant_id": plant_id, "month": month})
    if period and period.get("status") in ("CLOSED", "CLOSING"):
        raise HTTPException(409, "Payroll month is closed. Plant Owner must reopen the period before any payroll mutation.")


async def _build_payslip(
    plant_id: str,
    month: str,
    employee: dict,
    payroll: dict,
    version: int,
    issued_by: str,
    issued_at: datetime,
) -> dict:
    uid = str(employee["_id"])
    month_start, _ = month_bounds(month)
    profile = await employee_profiles.find_one({"plant_id": plant_id, "user_id": uid})
    salary = await _current_salary(plant_id, uid, month_start)
    salary_summary = salary_totals(salary or {})
    employee_code = str((profile or {}).get("employee_code") or "") or None
    return {
        "plant_id": plant_id,
        "month": month,
        "user_id": uid,
        "employee_name": employee.get("name") or payroll.get("user_name") or "Staff",
        "role": employee.get("primary_role") or payroll.get("role") or "staff",
        "employee_code": employee_code,
        "designation": (profile or {}).get("designation"),
        "department": (profile or {}).get("department"),
        "payslip_number": payslip_number(month, plant_id, uid, employee_code),
        "closure_version": version,
        "employment_snapshot": {
            "employee_code": employee_code,
            "designation": (profile or {}).get("designation"),
            "department": (profile or {}).get("department"),
            "employment_type": (profile or {}).get("employment_type"),
            "join_date": str((profile or {}).get("join_date") or "") or None,
        },
        "salary_structure_snapshot": {
            "effective_from": (salary or {}).get("effective_from"),
            "pay_basis": (salary or {}).get("pay_basis"),
            "basic_amount": float((salary or {}).get("basic_amount") or 0),
            "hra_amount": float((salary or {}).get("hra_amount") or 0),
            "other_allowances": float((salary or {}).get("other_allowances") or 0),
            "overtime_rate_per_hour": float((salary or {}).get("overtime_rate_per_hour") or 0),
            "gross_amount": salary_summary["gross"],
            "fixed_deductions_total": salary_summary["deductions"],
            "net_before_overtime": salary_summary["net_before_overtime"],
        } if salary else None,
        "payroll_snapshot": {
            "payroll_record_id": _doc_id(payroll.get("_id")),
            "status": payroll.get("status"),
            "basic_amount": float(payroll.get("basic_amount") or 0),
            "allowances": float(payroll.get("allowances") or 0),
            "overtime_amount": float(payroll.get("overtime_amount") or 0),
            "deductions": float(payroll.get("deductions") or 0),
            "paid_days": float(payroll.get("paid_days") or 0),
            "net_amount": float(payroll.get("net_amount") or 0),
            "attendance_evidence": payroll.get("attendance_evidence") or {},
            "payment_method": payroll.get("payment_method"),
            "payment_reference": payroll.get("payment_reference"),
            "paid_on": payroll.get("paid_on"),
            "paid_at": payroll.get("paid_at"),
            "finance_expense_id": payroll.get("finance_expense_id"),
        },
        "issued_by": issued_by,
        "issued_at": issued_at,
        "created_at": issued_at,
        "notice": "Historical payslip snapshot. Payroll values come from the Owner-approved and finance-posted payroll record for this month.",
    }


@mutation_guard_router.put("/plants/{plant_id}/payroll/{month}/{user_id}/draft")
async def guarded_prepare_payroll_draft(
    plant_id: str,
    month: str,
    user_id: str,
    body: PayrollDraftBody,
    ctx: dict = Depends(accountant_only),
):
    await _ensure_period_mutable(plant_id, month)
    return await prepare_payroll_draft_safe(plant_id, month, user_id, body, ctx)


@mutation_guard_router.post("/plants/{plant_id}/payroll/{month}/{user_id}/owner-decision")
async def guarded_owner_payroll_decision(
    plant_id: str,
    month: str,
    user_id: str,
    body: PayrollOwnerDecisionBody,
    ctx: dict = Depends(owner_only),
):
    await _ensure_period_mutable(plant_id, month)
    return await owner_payroll_decision_safe(plant_id, month, user_id, body, ctx)


@mutation_guard_router.post("/plants/{plant_id}/payroll/{month}/{user_id}/mark-paid")
async def guarded_mark_payroll_paid(
    plant_id: str,
    month: str,
    user_id: str,
    body: PayrollPaidBody,
    ctx: dict = Depends(accountant_only),
):
    await _ensure_period_mutable(plant_id, month)
    return await mark_payroll_paid_safe(plant_id, month, user_id, body, ctx)


@router.get("/{month}")
async def payroll_period_status(month: str, ctx: dict = Depends(report_access)):
    month_bounds(month)
    output = []
    for plant_id in await _report_plant_ids(ctx):
        plant = await plants.find_one({"_id": oid(plant_id)})
        readiness, _, _ = await _readiness(plant_id, month)
        period = await payroll_periods.find_one({"plant_id": plant_id, "month": month})
        latest_version = int((period or {}).get("version") or 0)
        slip_count = await payslip_snapshots.count_documents({
            "plant_id": plant_id, "month": month, "closure_version": latest_version,
        }) if latest_version else 0
        output.append({
            "plant_id": plant_id,
            "plant_name": (plant or {}).get("name") or (plant or {}).get("trade_name") or "RMC Plant",
            "month": month,
            "status": (period or {}).get("status") or "OPEN",
            "version": latest_version,
            "closed_at": (period or {}).get("closed_at"),
            "closed_by": (period or {}).get("closed_by"),
            "reopened_at": (period or {}).get("reopened_at"),
            "reopen_reason": (period or {}).get("reopen_reason"),
            "payslip_count": slip_count,
            "readiness": readiness,
        })
    return {"month": month, "periods": [_serialize(row) if "_id" in row else row for row in output]}


@router.post("/plants/{plant_id}/{month}/close")
async def close_payroll_period(
    plant_id: str,
    month: str,
    body: ClosePayrollPeriodBody,
    ctx: dict = Depends(owner_only),
):
    await _require_owner_plant(ctx, plant_id)
    month_bounds(month)
    readiness, staff, payrolls = await _readiness(plant_id, month)
    if not readiness["ready"]:
        raise HTTPException(409, {"message": "Every active employee payroll must be PAID before closing the month", "readiness": readiness})

    current = await payroll_periods.find_one({"plant_id": plant_id, "month": month})
    if current and current.get("status") == "CLOSED":
        return {"period": _serialize(current), "idempotent": True}
    if current and current.get("status") == "CLOSING":
        raise HTTPException(409, "Payroll month is already being closed")

    now = _utcnow()
    lock_id = uuid4().hex
    previous_version = int((current or {}).get("version") or 0)
    version = previous_version + 1
    if current:
        reserved = await payroll_periods.find_one_and_update(
            {"_id": current["_id"], "status": {"$in": ["OPEN", "REOPENED"]}, "version": previous_version},
            {"$set": {"status": "CLOSING", "close_lock": lock_id, "close_started_at": now, "updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if not reserved:
            raise HTTPException(409, "Payroll period changed concurrently; refresh and retry")
    else:
        try:
            result = await payroll_periods.insert_one({
                "plant_id": plant_id,
                "month": month,
                "status": "CLOSING",
                "version": 0,
                "close_lock": lock_id,
                "close_started_at": now,
                "created_at": now,
                "updated_at": now,
            })
            reserved = await payroll_periods.find_one({"_id": result.inserted_id})
        except DuplicateKeyError as exc:
            raise HTTPException(409, "Payroll period was changed concurrently; refresh and retry") from exc

    try:
        latest_readiness, latest_staff, latest_payrolls = await _readiness(plant_id, month)
        if not latest_readiness["ready"] or len(latest_staff) != len(staff):
            raise HTTPException(409, "Payroll readiness changed while closing; period remains open")
        payroll_by_user = {str(row.get("user_id")): row for row in latest_payrolls}
        total_net = 0.0
        created_slips = []
        issued_at = _utcnow()
        for employee in latest_staff:
            uid = str(employee["_id"])
            payroll = payroll_by_user[uid]
            snapshot = await _build_payslip(plant_id, month, employee, payroll, version, ctx["user_id"], issued_at)
            total_net += float((snapshot.get("payroll_snapshot") or {}).get("net_amount") or 0)
            try:
                await payslip_snapshots.insert_one(snapshot)
            except DuplicateKeyError:
                existing = await payslip_snapshots.find_one({
                    "plant_id": plant_id, "month": month, "user_id": uid, "closure_version": version,
                })
                if not existing:
                    raise
            created_slips.append(uid)

        finalized = await payroll_periods.find_one_and_update(
            {"_id": reserved["_id"], "status": "CLOSING", "close_lock": lock_id},
            {
                "$set": {
                    "status": "CLOSED",
                    "version": version,
                    "closed_by": ctx["user_id"],
                    "closed_at": issued_at,
                    "close_note": (body.note or "").strip() or None,
                    "employee_count": len(latest_staff),
                    "payslip_count": len(created_slips),
                    "payroll_total": round(total_net, 2),
                    "updated_at": issued_at,
                },
                "$unset": {"close_lock": "", "close_started_at": ""},
            },
            return_document=ReturnDocument.AFTER,
        )
        if not finalized:
            raise HTTPException(409, "Payslips were snapshotted but period finalization needs reconciliation")
    except Exception:
        await payroll_periods.update_one(
            {"_id": reserved["_id"], "close_lock": lock_id},
            {"$set": {"status": "OPEN", "updated_at": _utcnow()}, "$unset": {"close_lock": "", "close_started_at": ""}},
        )
        raise

    await write_audit(
        ctx["user_id"], "payroll.period.close", "payroll_period", str(finalized["_id"]),
        {"plant_id": plant_id, "month": month, "version": version, "payroll_total": round(total_net, 2)},
    )
    for employee in latest_staff:
        await record_notification(
            str(employee["_id"]),
            "payroll_payslip_issued",
            "Payslip available",
            f"Your payslip for {month} is now available in TrackMyRMC.",
        )
    return {"period": _serialize(finalized), "payslips_created": len(created_slips)}


@router.post("/plants/{plant_id}/{month}/reopen")
async def reopen_payroll_period(
    plant_id: str,
    month: str,
    body: ReopenPayrollPeriodBody,
    ctx: dict = Depends(owner_only),
):
    await _require_owner_plant(ctx, plant_id)
    month_bounds(month)
    now = _utcnow()
    updated = await payroll_periods.find_one_and_update(
        {"plant_id": plant_id, "month": month, "status": "CLOSED"},
        {"$set": {
            "status": "REOPENED",
            "reopened_by": ctx["user_id"],
            "reopened_at": now,
            "reopen_reason": body.reason.strip(),
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        current = await payroll_periods.find_one({"plant_id": plant_id, "month": month})
        if current and current.get("status") == "REOPENED":
            return {"period": _serialize(current), "idempotent": True}
        raise HTTPException(409, "Only a CLOSED payroll period can be reopened")
    await write_audit(
        ctx["user_id"], "payroll.period.reopen", "payroll_period", str(updated["_id"]),
        {"plant_id": plant_id, "month": month, "reason": body.reason.strip(), "version": updated.get("version")},
    )
    return {
        "period": _serialize(updated),
        "note": "Historical payslip snapshots remain immutable. Closing again creates a new payslip version.",
    }


@router.get("/plants/{plant_id}/{month}/payslips")
async def list_period_payslips(plant_id: str, month: str, ctx: dict = Depends(report_access)):
    month_bounds(month)
    if plant_id not in await _report_plant_ids(ctx):
        raise HTTPException(403, "Plant access denied")
    period = await payroll_periods.find_one({"plant_id": plant_id, "month": month})
    version = int((period or {}).get("version") or 0)
    if not version:
        return {"month": month, "plant_id": plant_id, "status": (period or {}).get("status") or "OPEN", "payslips": []}
    rows = await payslip_snapshots.find({
        "plant_id": plant_id, "month": month, "closure_version": version,
    }).sort("employee_name", 1).to_list(5000)
    return {
        "month": month,
        "plant_id": plant_id,
        "status": (period or {}).get("status") or "OPEN",
        "closure_version": version,
        "historical": (period or {}).get("status") != "CLOSED",
        "payslips": [_serialize(row) for row in rows],
    }


@router.get("/plants/{plant_id}/{month}/export")
async def export_period_payroll(plant_id: str, month: str, ctx: dict = Depends(report_access)):
    response = await list_period_payslips(plant_id, month, ctx)
    rows = response["payslips"]
    if not rows:
        raise HTTPException(404, "No closed-period payslips are available to export")
    return {
        "filename": f"payroll-{plant_id}-{month}-v{response.get('closure_version', 0)}.csv",
        "content_type": "text/csv",
        "csv": payslips_to_csv(rows),
        "row_count": len(rows),
        "closure_version": response.get("closure_version"),
    }


@router.get("/me/{month}")
async def my_payslip(month: str, ctx: dict = Depends(employee_only)):
    month_bounds(month)
    plant_id = ctx.get("plant_id") or ctx.get("user", {}).get("plant_id")
    if not plant_id:
        raise HTTPException(403, "Plant assignment required")
    row = await payslip_snapshots.find_one(
        {"plant_id": str(plant_id), "month": month, "user_id": ctx["user_id"]},
        sort=[("closure_version", -1)],
    )
    if not row:
        raise HTTPException(404, "Payslip is not available for this month yet")
    period = await payroll_periods.find_one({"plant_id": str(plant_id), "month": month})
    return {
        "payslip": _serialize(row),
        "period_status": (period or {}).get("status") or "OPEN",
        "historical": int(row.get("closure_version") or 0) != int((period or {}).get("version") or 0) or (period or {}).get("status") != "CLOSED",
    }
