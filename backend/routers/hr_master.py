"""Plant-scoped employee master and versioned salary structures.

Employee identity always comes from the existing users collection. This module
stores HR/employment metadata and salary reference data only. Salary structures
may prefill payroll preparation, but never infer paid days, approve payroll, or
post salary payments automatically.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from validation import StrictModel
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from business_access import oid, visible_plant_ids
from database import db, users
from roles import Role
from security import require_role
from routers.workforce import EMPLOYEE_ROLES

router = APIRouter(prefix="/api/hr", tags=["hr-master"])

employee_profiles = db.hr_employee_profiles
salary_structures = db.hr_salary_structures

hr_read = require_role(Role.PLANT_OWNER.value, Role.ACCOUNTANT.value)
owner_only = require_role(Role.PLANT_OWNER.value)


class EmployeeProfileBody(StrictModel):
    employee_code: str = Field(min_length=2, max_length=40)
    designation: str = Field(min_length=2, max_length=120)
    department: str = Field(min_length=2, max_length=120)
    join_date: date
    employment_type: Literal["PERMANENT", "CONTRACT", "TEMPORARY", "TRAINEE"] = "PERMANENT"
    weekly_off_day: Literal["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"] = "SUNDAY"
    work_location: str | None = Field(default=None, max_length=240)
    emergency_contact_name: str | None = Field(default=None, max_length=120)
    emergency_contact_phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=1000)
    pan_masked: str | None = Field(default=None, max_length=32)
    uan_masked: str | None = Field(default=None, max_length=32)
    bank_account_masked: str | None = Field(default=None, max_length=64)
    bank_name: str | None = Field(default=None, max_length=160)
    ifsc: str | None = Field(default=None, max_length=20)
    document_references: list[str] = Field(default_factory=list, max_length=20)
    notes: str | None = Field(default=None, max_length=3000)


class SalaryStructureBody(StrictModel):
    effective_from: date
    pay_basis: Literal["MONTHLY", "DAILY"] = "MONTHLY"
    basic_amount: float = Field(ge=0, le=100_000_000)
    hra_amount: float = Field(default=0, ge=0, le=100_000_000)
    other_allowances: float = Field(default=0, ge=0, le=100_000_000)
    overtime_rate_per_hour: float = Field(default=0, ge=0, le=1_000_000)
    fixed_deductions: float = Field(default=0, ge=0, le=100_000_000)
    employee_pf: float = Field(default=0, ge=0, le=100_000_000)
    employee_esi: float = Field(default=0, ge=0, le=100_000_000)
    professional_tax: float = Field(default=0, ge=0, le=100_000_000)
    tds: float = Field(default=0, ge=0, le=100_000_000)
    notes: str | None = Field(default=None, max_length=3000)


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


def salary_totals(body: SalaryStructureBody | dict) -> dict:
    data = body.model_dump() if hasattr(body, "model_dump") else body
    allowances = round(float(data.get("hra_amount") or 0) + float(data.get("other_allowances") or 0), 2)
    deductions = round(
        float(data.get("fixed_deductions") or 0)
        + float(data.get("employee_pf") or 0)
        + float(data.get("employee_esi") or 0)
        + float(data.get("professional_tax") or 0)
        + float(data.get("tds") or 0),
        2,
    )
    gross = round(float(data.get("basic_amount") or 0) + allowances, 2)
    net_before_overtime = round(gross - deductions, 2)
    return {"allowances": allowances, "deductions": deductions, "gross": gross, "net_before_overtime": net_before_overtime}


async def ensure_indexes() -> None:
    await employee_profiles.create_index([("plant_id", 1), ("user_id", 1)], unique=True)
    await employee_profiles.create_index([("plant_id", 1), ("employee_code", 1)], unique=True)
    await salary_structures.create_index([("plant_id", 1), ("user_id", 1), ("effective_from", -1)], unique=True)


async def _visible_plants(ctx: dict) -> list[str]:
    if ctx.get("role") == Role.PLANT_OWNER.value:
        return await visible_plant_ids(ctx)
    plant_id = ctx.get("plant_id") or ctx.get("user", {}).get("plant_id")
    if not plant_id:
        raise HTTPException(403, "Plant assignment required")
    return [str(plant_id)]


async def _owner_can_access(ctx: dict, plant_id: str) -> None:
    if plant_id not in await visible_plant_ids(ctx):
        raise HTTPException(403, "Plant access denied")


async def _employee(plant_id: str, user_id: str) -> dict:
    employee = await users.find_one({"_id": oid(user_id), "plant_id": plant_id, "primary_role": {"$in": list(EMPLOYEE_ROLES)}})
    if not employee:
        raise HTTPException(404, "Staff member not found for this plant")
    return employee


async def _current_salary(plant_id: str, user_id: str, as_of: date | None = None) -> dict | None:
    cutoff = (as_of or _utcnow().date()).isoformat()
    return await salary_structures.find_one(
        {"plant_id": plant_id, "user_id": user_id, "effective_from": {"$lte": cutoff}},
        sort=[("effective_from", -1)],
    )


@router.get("/employees")
async def list_employees(ctx: dict = Depends(hr_read)):
    plant_ids = await _visible_plants(ctx)
    output = []
    for plant_id in plant_ids:
        staff = await users.find({
            "plant_id": plant_id,
            "primary_role": {"$in": list(EMPLOYEE_ROLES)},
            "status": {"$nin": ["suspended", "disabled", "deleted"]},
        }).sort("name", 1).to_list(2000)
        profiles = await employee_profiles.find({"plant_id": plant_id}).to_list(2000)
        profile_map = {str(row.get("user_id")): row for row in profiles}
        employees = []
        for user in staff:
            uid = str(user["_id"])
            salary = await _current_salary(plant_id, uid)
            employees.append({
                "user_id": uid,
                "name": user.get("name") or "Staff",
                "role": user.get("primary_role"),
                "email": user.get("email"),
                "phone": user.get("phone"),
                "profile": _serialize(profile_map.get(uid)),
                "current_salary": _serialize(salary),
                "salary_totals": salary_totals(salary or {}),
            })
        output.append({"plant_id": plant_id, "employees": employees})
    return {"plants": output, "can_edit": ctx.get("role") == Role.PLANT_OWNER.value}


@router.get("/plants/{plant_id}/employees/{user_id}")
async def employee_detail(plant_id: str, user_id: str, ctx: dict = Depends(hr_read)):
    if plant_id not in await _visible_plants(ctx):
        raise HTTPException(403, "Plant access denied")
    user = await _employee(plant_id, user_id)
    profile = await employee_profiles.find_one({"plant_id": plant_id, "user_id": user_id})
    salaries = await salary_structures.find({"plant_id": plant_id, "user_id": user_id}).sort("effective_from", -1).to_list(100)
    current = await _current_salary(plant_id, user_id)
    return {
        "employee": {"user_id": user_id, "name": user.get("name") or "Staff", "role": user.get("primary_role"), "email": user.get("email"), "phone": user.get("phone")},
        "profile": _serialize(profile),
        "salary_history": [_serialize(row) for row in salaries],
        "current_salary": _serialize(current),
        "salary_totals": salary_totals(current or {}),
        "advisory": "Salary structure is a payroll preparation reference only; attendance and payroll approval remain separate workflows.",
    }


@router.put("/plants/{plant_id}/employees/{user_id}/profile")
async def save_employee_profile(plant_id: str, user_id: str, body: EmployeeProfileBody, ctx: dict = Depends(owner_only)):
    await _owner_can_access(ctx, plant_id)
    user = await _employee(plant_id, user_id)
    if body.join_date > _utcnow().date() + timedelta(days=365):
        raise HTTPException(422, "Join date is unreasonably far in the future")
    now = _utcnow()
    payload = {
        **body.model_dump(),
        "plant_id": plant_id,
        "user_id": user_id,
        "user_name": user.get("name") or "Staff",
        "role": user.get("primary_role"),
        "updated_by": ctx["user_id"],
        "updated_at": now,
    }
    try:
        await employee_profiles.update_one(
            {"plant_id": plant_id, "user_id": user_id},
            {"$set": payload, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    except DuplicateKeyError as exc:
        raise HTTPException(409, "Employee code is already used in this plant") from exc
    profile = await employee_profiles.find_one({"plant_id": plant_id, "user_id": user_id})
    await write_audit(ctx["user_id"], "hr.employee.profile.update", "hr_employee_profile", str((profile or {}).get("_id")), {"plant_id": plant_id, "user_id": user_id, "employee_code": body.employee_code})
    return {"profile": _serialize(profile)}


@router.put("/plants/{plant_id}/employees/{user_id}/salary")
async def save_salary_structure(plant_id: str, user_id: str, body: SalaryStructureBody, ctx: dict = Depends(owner_only)):
    await _owner_can_access(ctx, plant_id)
    await _employee(plant_id, user_id)
    totals = salary_totals(body)
    if totals["net_before_overtime"] < 0:
        raise HTTPException(422, "Fixed deductions cannot exceed gross salary")
    now = _utcnow()
    effective = body.effective_from.isoformat()
    payload = {
        **body.model_dump(),
        "effective_from": effective,
        "plant_id": plant_id,
        "user_id": user_id,
        "gross_amount": totals["gross"],
        "fixed_allowances": totals["allowances"],
        "fixed_deductions_total": totals["deductions"],
        "net_before_overtime": totals["net_before_overtime"],
        "updated_by": ctx["user_id"],
        "updated_at": now,
    }
    await salary_structures.update_one(
        {"plant_id": plant_id, "user_id": user_id, "effective_from": effective},
        {"$set": payload, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    salary = await salary_structures.find_one({"plant_id": plant_id, "user_id": user_id, "effective_from": effective})
    await write_audit(ctx["user_id"], "hr.employee.salary.update", "hr_salary_structure", str((salary or {}).get("_id")), {"plant_id": plant_id, "user_id": user_id, "effective_from": effective, "gross": totals["gross"]})
    return {"salary": _serialize(salary), "totals": totals}


@router.get("/plants/{plant_id}/employees/{user_id}/salary-suggestion/{month}")
async def salary_suggestion(plant_id: str, user_id: str, month: str, ctx: dict = Depends(hr_read)):
    if plant_id not in await _visible_plants(ctx):
        raise HTTPException(403, "Plant access denied")
    try:
        month_start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise HTTPException(422, "Month must use YYYY-MM format") from exc
    await _employee(plant_id, user_id)
    salary = await _current_salary(plant_id, user_id, month_start)
    if not salary:
        raise HTTPException(404, "No salary structure is effective for this month")
    totals = salary_totals(salary)
    return {
        "month": month,
        "salary_structure": _serialize(salary),
        "payroll_prefill": {
            "basic_amount": float(salary.get("basic_amount") or 0),
            "allowances": totals["allowances"],
            "overtime_amount": 0,
            "deductions": totals["deductions"],
        },
        "requires_review": True,
        "note": "This is an advisory prefill. Accountant must review paid days/overtime; Plant Owner approval is still required before payment.",
    }
