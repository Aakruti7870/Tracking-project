"""Plant-scoped workforce and field activity workflows.

This module extends the existing staff attendance and finance data model with
leave requests, client visits and two-stage employee expense claims. Employee
workflows are intentionally unavailable to customer, authority, central-admin
and plant-owner accounts. Plant owners receive approval controls only; plant
accountants verify expense claims before owner approval.
"""
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from business_access import oid, visible_plant_ids
from database import db, expenses, plants, staff_attendance, users
from notifications import record_notification
from roles import Role
from security import current_user, require_role

router = APIRouter(prefix="/api/workforce", tags=["workforce"])

leave_requests = db.workforce_leave_requests
client_visits = db.workforce_client_visits
expense_claims = db.workforce_expense_claims

EMPLOYEE_ROLES = (
    Role.DRIVER.value,
    Role.ADMIN.value,
    Role.DISPATCHER.value,
    Role.OPERATOR.value,
    Role.SUPERVISOR.value,
    Role.ACCOUNTANT.value,
    Role.QUALITY_ENGINEER.value,
    Role.FLEET_MANAGER.value,
    Role.STORE_MANAGER.value,
)
employee_only = require_role(*EMPLOYEE_ROLES)
accountant_only = require_role(Role.ACCOUNTANT.value)
owner_only = require_role(Role.PLANT_OWNER.value)

LEAVE_TYPES = ("CASUAL", "SICK", "PAID", "UNPAID", "OTHER")


class LocationEvidence(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy_m: float | None = Field(default=None, ge=0, le=10000)
    note: str | None = Field(default=None, max_length=500)


class LeaveRequestBody(BaseModel):
    leave_type: Literal["CASUAL", "SICK", "PAID", "UNPAID", "OTHER"]
    start_date: date
    end_date: date
    reason: str = Field(min_length=3, max_length=1000)


class VisitRequestBody(BaseModel):
    client_name: str = Field(min_length=2, max_length=160)
    purpose: str = Field(min_length=3, max_length=1000)
    scheduled_for: datetime
    site_address: str = Field(min_length=3, max_length=500)
    contact_name: str | None = Field(default=None, max_length=120)
    contact_phone: str | None = Field(default=None, max_length=30)


class VisitActionBody(LocationEvidence):
    outcome: str | None = Field(default=None, max_length=1000)


class ExpenseClaimBody(BaseModel):
    category: str = Field(min_length=2, max_length=64)
    amount: float = Field(gt=0, le=10_000_000)
    expense_date: date
    description: str = Field(min_length=3, max_length=1000)
    receipt_reference: str | None = Field(default=None, max_length=500)


class DecisionBody(BaseModel):
    action: Literal["APPROVE", "REJECT"]
    note: str | None = Field(default=None, max_length=1000)


class AccountantExpenseDecisionBody(BaseModel):
    action: Literal["VERIFY", "RETURN"]
    note: str | None = Field(default=None, max_length=1000)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _serialize(doc: dict | None) -> dict | None:
    if not doc:
        return None
    out = {**doc, "id": str(doc["_id"])}
    out.pop("_id", None)
    for key, value in list(out.items()):
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
    return out


def _employee_plant(ctx: dict) -> str:
    if ctx.get("role") not in EMPLOYEE_ROLES:
        raise HTTPException(403, "Workforce employee access denied")
    plant_id = ctx.get("plant_id") or ctx.get("user", {}).get("plant_id")
    if not plant_id:
        raise HTTPException(403, "Plant assignment required for workforce access")
    return str(plant_id)


async def _owner_can_access(ctx: dict, plant_id: str) -> None:
    if ctx.get("role") != Role.PLANT_OWNER.value:
        raise HTTPException(403, "Plant owner access required")
    if plant_id not in await visible_plant_ids(ctx):
        raise HTTPException(403, "Plant access denied")


async def _notify_owner(plant_id: str, event: str, title: str, message: str) -> None:
    plant = await plants.find_one({"_id": oid(plant_id)})
    owner_id = (plant or {}).get("owner_id")
    if owner_id:
        await record_notification(str(owner_id), event, title, message)


async def _notify_accountants(plant_id: str, event: str, title: str, message: str) -> None:
    docs = await users.find(
        {
            "plant_id": plant_id,
            "primary_role": Role.ACCOUNTANT.value,
            "status": {"$nin": ["suspended", "disabled", "deleted"]},
        }
    ).to_list(100)
    for user in docs:
        await record_notification(str(user["_id"]), event, title, message)


async def ensure_indexes() -> None:
    """Create indexes for the workforce collections owned by this router."""
    await leave_requests.create_index([("user_id", 1), ("created_at", -1)])
    await leave_requests.create_index([("plant_id", 1), ("status", 1), ("start_date", 1)])
    await client_visits.create_index([("user_id", 1), ("scheduled_for", -1)])
    await client_visits.create_index([("plant_id", 1), ("status", 1), ("scheduled_for", 1)])
    await expense_claims.create_index([("user_id", 1), ("expense_date", -1)])
    await expense_claims.create_index([("plant_id", 1), ("status", 1), ("expense_date", -1)])
    await expenses.create_index(
        "claim_id",
        unique=True,
        partialFilterExpression={"claim_id": {"$type": "string"}},
        name="unique_finance_expense_per_workforce_claim",
    )


@router.get("/me")
async def my_workforce(ctx: dict = Depends(employee_only)):
    plant_id = _employee_plant(ctx)
    uid = ctx["user_id"]
    today = _utcnow().date().isoformat()
    attendance = await staff_attendance.find_one({"user_id": uid, "plant_id": plant_id, "date": today})
    attendance_history = await staff_attendance.find(
        {"user_id": uid, "plant_id": plant_id}
    ).sort("date", -1).to_list(14)
    leaves = await leave_requests.find({"user_id": uid, "plant_id": plant_id}).sort("created_at", -1).to_list(25)
    visits = await client_visits.find({"user_id": uid, "plant_id": plant_id}).sort("scheduled_for", -1).to_list(25)
    claims = await expense_claims.find({"user_id": uid, "plant_id": plant_id}).sort("created_at", -1).to_list(25)
    return {
        "mode": "employee",
        "plant_id": plant_id,
        "role": ctx["role"],
        "attendance": _serialize(attendance),
        "attendance_history": [_serialize(d) for d in attendance_history],
        "leave_requests": [_serialize(d) for d in leaves],
        "client_visits": [_serialize(d) for d in visits],
        "expense_claims": [_serialize(d) for d in claims],
        "can_verify_expenses": ctx["role"] == Role.ACCOUNTANT.value,
    }


@router.post("/attendance/punch-in")
async def punch_in(body: LocationEvidence, ctx: dict = Depends(employee_only)):
    plant_id = _employee_plant(ctx)
    date_key = _utcnow().date().isoformat()
    now = _utcnow()
    existing = await staff_attendance.find_one({"user_id": ctx["user_id"], "date": date_key})
    if existing and existing.get("check_in"):
        if existing.get("plant_id") != plant_id:
            raise HTTPException(409, "Attendance is already recorded against another plant today")
        raise HTTPException(409, "Already punched in today")
    await staff_attendance.update_one(
        {"user_id": ctx["user_id"], "date": date_key},
        {
            "$set": {
                "plant_id": plant_id,
                "user_name": ctx["user"].get("name"),
                "role": ctx["role"],
                "check_in": now,
                "check_in_lat": body.lat,
                "check_in_lng": body.lng,
                "check_in_accuracy_m": body.accuracy_m,
                "check_in_note": body.note,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    await write_audit(
        ctx["user_id"], "workforce.attendance.punch_in", "staff_attendance", date_key,
        {"plant_id": plant_id, "lat": body.lat, "lng": body.lng, "accuracy_m": body.accuracy_m},
    )
    return {"status": "checked_in", "at": now.isoformat()}


@router.post("/attendance/punch-out")
async def punch_out(body: LocationEvidence, ctx: dict = Depends(employee_only)):
    plant_id = _employee_plant(ctx)
    date_key = _utcnow().date().isoformat()
    now = _utcnow()
    doc = await staff_attendance.find_one(
        {"user_id": ctx["user_id"], "plant_id": plant_id, "date": date_key}
    )
    if not doc or not doc.get("check_in"):
        raise HTTPException(409, "Punch in before punching out")
    if doc.get("check_out"):
        raise HTTPException(409, "Already punched out today")
    updated = await staff_attendance.find_one_and_update(
        {"_id": doc["_id"], "check_out": {"$exists": False}},
        {"$set": {
            "check_out": now,
            "check_out_lat": body.lat,
            "check_out_lng": body.lng,
            "check_out_accuracy_m": body.accuracy_m,
            "check_out_note": body.note,
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "Attendance changed concurrently; refresh and retry")
    await write_audit(
        ctx["user_id"], "workforce.attendance.punch_out", "staff_attendance", date_key,
        {"plant_id": plant_id, "lat": body.lat, "lng": body.lng, "accuracy_m": body.accuracy_m},
    )
    return {"status": "checked_out", "at": now.isoformat()}


@router.post("/leave")
async def create_leave(body: LeaveRequestBody, ctx: dict = Depends(employee_only)):
    plant_id = _employee_plant(ctx)
    if body.end_date < body.start_date:
        raise HTTPException(422, "Leave end date cannot be before start date")
    if (body.end_date - body.start_date).days > 90:
        raise HTTPException(422, "A single leave request cannot exceed 90 days")
    if body.start_date < _utcnow().date() - timedelta(days=1):
        raise HTTPException(422, "Leave cannot start in the past")
    start = body.start_date.isoformat()
    end = body.end_date.isoformat()
    overlap = await leave_requests.find_one(
        {
            "user_id": ctx["user_id"],
            "plant_id": plant_id,
            "status": {"$in": ["PENDING", "APPROVED"]},
            "start_date": {"$lte": end},
            "end_date": {"$gte": start},
        }
    )
    if overlap:
        raise HTTPException(409, "An active leave request already overlaps these dates")
    now = _utcnow()
    doc = {
        "user_id": ctx["user_id"],
        "user_name": ctx["user"].get("name"),
        "role": ctx["role"],
        "plant_id": plant_id,
        "leave_type": body.leave_type,
        "start_date": start,
        "end_date": end,
        "reason": body.reason.strip(),
        "status": "PENDING",
        "created_at": now,
        "updated_at": now,
    }
    result = await leave_requests.insert_one(doc)
    request_id = str(result.inserted_id)
    await write_audit(ctx["user_id"], "workforce.leave.submit", "leave_request", request_id, {"plant_id": plant_id})
    await _notify_owner(
        plant_id, "workforce_leave_pending", "Leave approval required",
        f"{doc['user_name'] or 'Staff member'} requested {body.leave_type.lower()} leave from {start} to {end}.",
    )
    doc["_id"] = result.inserted_id
    return {"leave_request": _serialize(doc)}


@router.post("/visits")
async def create_visit(body: VisitRequestBody, ctx: dict = Depends(employee_only)):
    plant_id = _employee_plant(ctx)
    scheduled = _aware(body.scheduled_for)
    if scheduled < _utcnow() - timedelta(minutes=15):
        raise HTTPException(422, "Client visit cannot be scheduled in the past")
    if scheduled > _utcnow() + timedelta(days=180):
        raise HTTPException(422, "Client visit cannot be scheduled more than 180 days ahead")
    now = _utcnow()
    doc = {
        "user_id": ctx["user_id"],
        "user_name": ctx["user"].get("name"),
        "role": ctx["role"],
        "plant_id": plant_id,
        "client_name": body.client_name.strip(),
        "purpose": body.purpose.strip(),
        "scheduled_for": scheduled,
        "site_address": body.site_address.strip(),
        "contact_name": (body.contact_name or "").strip() or None,
        "contact_phone": (body.contact_phone or "").strip() or None,
        "status": "PENDING",
        "created_at": now,
        "updated_at": now,
    }
    result = await client_visits.insert_one(doc)
    visit_id = str(result.inserted_id)
    await write_audit(ctx["user_id"], "workforce.visit.submit", "client_visit", visit_id, {"plant_id": plant_id})
    await _notify_owner(
        plant_id, "workforce_visit_pending", "Client visit approval required",
        f"{doc['user_name'] or 'Staff member'} requested a visit to {doc['client_name']}.",
    )
    doc["_id"] = result.inserted_id
    return {"client_visit": _serialize(doc)}


async def _my_visit(ctx: dict, visit_id: str) -> dict:
    plant_id = _employee_plant(ctx)
    doc = await client_visits.find_one(
        {"_id": oid(visit_id), "user_id": ctx["user_id"], "plant_id": plant_id}
    )
    if not doc:
        raise HTTPException(404, "Client visit not found")
    return doc


@router.post("/visits/{visit_id}/start")
async def start_visit(visit_id: str, body: VisitActionBody, ctx: dict = Depends(employee_only)):
    doc = await _my_visit(ctx, visit_id)
    if doc.get("status") == "IN_PROGRESS":
        return {"client_visit": _serialize(doc), "idempotent": True}
    if doc.get("status") != "APPROVED":
        raise HTTPException(409, "Client visit must be approved before it can start")
    now = _utcnow()
    updated = await client_visits.find_one_and_update(
        {"_id": doc["_id"], "status": "APPROVED"},
        {"$set": {
            "status": "IN_PROGRESS",
            "started_at": now,
            "start_lat": body.lat,
            "start_lng": body.lng,
            "start_accuracy_m": body.accuracy_m,
            "start_note": body.note,
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "Visit status changed concurrently; refresh and retry")
    await write_audit(ctx["user_id"], "workforce.visit.start", "client_visit", visit_id, {"plant_id": doc["plant_id"]})
    return {"client_visit": _serialize(updated)}


@router.post("/visits/{visit_id}/complete")
async def complete_visit(visit_id: str, body: VisitActionBody, ctx: dict = Depends(employee_only)):
    doc = await _my_visit(ctx, visit_id)
    if doc.get("status") == "COMPLETED":
        return {"client_visit": _serialize(doc), "idempotent": True}
    if doc.get("status") != "IN_PROGRESS":
        raise HTTPException(409, "Start the approved client visit before completing it")
    now = _utcnow()
    updated = await client_visits.find_one_and_update(
        {"_id": doc["_id"], "status": "IN_PROGRESS"},
        {"$set": {
            "status": "COMPLETED",
            "completed_at": now,
            "complete_lat": body.lat,
            "complete_lng": body.lng,
            "complete_accuracy_m": body.accuracy_m,
            "outcome": (body.outcome or body.note or "").strip() or None,
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "Visit status changed concurrently; refresh and retry")
    await write_audit(ctx["user_id"], "workforce.visit.complete", "client_visit", visit_id, {"plant_id": doc["plant_id"]})
    return {"client_visit": _serialize(updated)}


@router.post("/expenses")
async def create_expense_claim(body: ExpenseClaimBody, ctx: dict = Depends(employee_only)):
    plant_id = _employee_plant(ctx)
    today = _utcnow().date()
    if body.expense_date > today:
        raise HTTPException(422, "Expense date cannot be in the future")
    if body.expense_date < today - timedelta(days=180):
        raise HTTPException(422, "Expense claims older than 180 days require manual finance handling")
    now = _utcnow()
    doc = {
        "user_id": ctx["user_id"],
        "user_name": ctx["user"].get("name"),
        "role": ctx["role"],
        "plant_id": plant_id,
        "category": body.category.strip().upper(),
        "amount": round(float(body.amount), 2),
        "expense_date": body.expense_date.isoformat(),
        "description": body.description.strip(),
        "receipt_reference": (body.receipt_reference or "").strip() or None,
        "status": "SUBMITTED",
        "created_at": now,
        "updated_at": now,
    }
    result = await expense_claims.insert_one(doc)
    claim_id = str(result.inserted_id)
    await write_audit(ctx["user_id"], "workforce.expense.submit", "expense_claim", claim_id, {"plant_id": plant_id, "amount": doc["amount"]})
    await _notify_accountants(
        plant_id, "workforce_expense_submitted", "Expense claim to verify",
        f"{doc['user_name'] or 'Staff member'} submitted ₹{doc['amount']:,.2f} for {doc['category']}.",
    )
    doc["_id"] = result.inserted_id
    return {"expense_claim": _serialize(doc)}


@router.get("/accountant/expenses")
async def accountant_expenses(ctx: dict = Depends(accountant_only)):
    plant_id = _employee_plant(ctx)
    docs = await expense_claims.find(
        {"plant_id": plant_id, "status": {"$in": ["SUBMITTED", "VERIFIED", "RETURNED"]}}
    ).sort("created_at", -1).to_list(500)
    return {"expense_claims": [_serialize(d) for d in docs]}


@router.post("/accountant/expenses/{claim_id}/decision")
async def accountant_expense_decision(
    claim_id: str,
    body: AccountantExpenseDecisionBody,
    ctx: dict = Depends(accountant_only),
):
    plant_id = _employee_plant(ctx)
    current = await expense_claims.find_one({"_id": oid(claim_id), "plant_id": plant_id})
    if not current:
        raise HTTPException(404, "Expense claim not found")
    target = "VERIFIED" if body.action == "VERIFY" else "RETURNED"
    if current.get("status") == target:
        return {"expense_claim": _serialize(current), "idempotent": True}
    if current.get("status") not in ("SUBMITTED", "RETURNED"):
        raise HTTPException(409, f"Expense claim cannot be reviewed from {current.get('status')}")
    if body.action == "RETURN" and not (body.note or "").strip():
        raise HTTPException(422, "Return reason is required")
    now = _utcnow()
    updated = await expense_claims.find_one_and_update(
        {"_id": current["_id"], "plant_id": plant_id, "status": current["status"]},
        {"$set": {
            "status": target,
            "accountant_id": ctx["user_id"],
            "accountant_name": ctx["user"].get("name"),
            "accountant_note": (body.note or "").strip() or None,
            "accountant_reviewed_at": now,
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "Expense claim changed concurrently; refresh and retry")
    await write_audit(ctx["user_id"], f"workforce.expense.{target.lower()}", "expense_claim", claim_id, {"plant_id": plant_id})
    await record_notification(
        current["user_id"], f"workforce_expense_{target.lower()}",
        "Expense claim verified" if target == "VERIFIED" else "Expense claim returned",
        f"Your ₹{float(current.get('amount') or 0):,.2f} expense claim is {target.lower()}.",
    )
    if target == "VERIFIED":
        await _notify_owner(
            plant_id, "workforce_expense_verified", "Verified expense awaiting approval",
            f"₹{float(current.get('amount') or 0):,.2f} from {current.get('user_name') or 'Staff member'} is ready for final approval.",
        )
    return {"expense_claim": _serialize(updated)}


@router.get("/owner/control")
async def owner_control(ctx: dict = Depends(owner_only)):
    plant_ids = await visible_plant_ids(ctx)
    if not plant_ids:
        return {"plant_ids": [], "attendance": [], "leave_requests": [], "client_visits": [], "expense_claims": []}
    today = _utcnow().date().isoformat()
    attendance = await staff_attendance.find(
        {"plant_id": {"$in": plant_ids}, "date": today}
    ).sort("user_name", 1).to_list(2000)
    leaves = await leave_requests.find(
        {"plant_id": {"$in": plant_ids}, "status": "PENDING"}
    ).sort("created_at", 1).to_list(1000)
    visits = await client_visits.find(
        {"plant_id": {"$in": plant_ids}, "status": "PENDING"}
    ).sort("scheduled_for", 1).to_list(1000)
    claims = await expense_claims.find(
        {"plant_id": {"$in": plant_ids}, "status": {"$in": ["SUBMITTED", "VERIFIED"]}}
    ).sort("created_at", 1).to_list(1000)
    return {
        "mode": "owner_control",
        "plant_ids": plant_ids,
        "attendance": [_serialize(d) for d in attendance],
        "leave_requests": [_serialize(d) for d in leaves],
        "client_visits": [_serialize(d) for d in visits],
        "expense_claims": [_serialize(d) for d in claims],
    }


@router.post("/owner/leave/{request_id}/decision")
async def owner_leave_decision(request_id: str, body: DecisionBody, ctx: dict = Depends(owner_only)):
    current = await leave_requests.find_one({"_id": oid(request_id)})
    if not current:
        raise HTTPException(404, "Leave request not found")
    await _owner_can_access(ctx, current["plant_id"])
    if current.get("status") not in ("PENDING", body.action + "D"):
        raise HTTPException(409, "Leave request has already been handled")
    target = "APPROVED" if body.action == "APPROVE" else "REJECTED"
    if current.get("status") == target:
        return {"leave_request": _serialize(current), "idempotent": True}
    if body.action == "REJECT" and not (body.note or "").strip():
        raise HTTPException(422, "Rejection reason is required")
    now = _utcnow()
    updated = await leave_requests.find_one_and_update(
        {"_id": current["_id"], "status": "PENDING"},
        {"$set": {
            "status": target,
            "decision_note": (body.note or "").strip() or None,
            "decided_by": ctx["user_id"],
            "decided_at": now,
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "Leave request changed concurrently; refresh and retry")
    await write_audit(ctx["user_id"], f"workforce.leave.{target.lower()}", "leave_request", request_id, {"plant_id": current["plant_id"]})
    await record_notification(
        current["user_id"], f"workforce_leave_{target.lower()}", f"Leave {target.lower()}",
        f"Your leave request for {current['start_date']} to {current['end_date']} was {target.lower()}.",
    )
    return {"leave_request": _serialize(updated)}


@router.post("/owner/visits/{visit_id}/decision")
async def owner_visit_decision(visit_id: str, body: DecisionBody, ctx: dict = Depends(owner_only)):
    current = await client_visits.find_one({"_id": oid(visit_id)})
    if not current:
        raise HTTPException(404, "Client visit not found")
    await _owner_can_access(ctx, current["plant_id"])
    target = "APPROVED" if body.action == "APPROVE" else "REJECTED"
    if current.get("status") == target:
        return {"client_visit": _serialize(current), "idempotent": True}
    if current.get("status") != "PENDING":
        raise HTTPException(409, "Client visit has already been handled")
    if body.action == "REJECT" and not (body.note or "").strip():
        raise HTTPException(422, "Rejection reason is required")
    now = _utcnow()
    updated = await client_visits.find_one_and_update(
        {"_id": current["_id"], "status": "PENDING"},
        {"$set": {
            "status": target,
            "decision_note": (body.note or "").strip() or None,
            "decided_by": ctx["user_id"],
            "decided_at": now,
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "Client visit changed concurrently; refresh and retry")
    await write_audit(ctx["user_id"], f"workforce.visit.{target.lower()}", "client_visit", visit_id, {"plant_id": current["plant_id"]})
    await record_notification(
        current["user_id"], f"workforce_visit_{target.lower()}", f"Client visit {target.lower()}",
        f"Your visit to {current.get('client_name') or 'client'} was {target.lower()}.",
    )
    return {"client_visit": _serialize(updated)}


@router.post("/owner/expenses/{claim_id}/decision")
async def owner_expense_decision(claim_id: str, body: DecisionBody, ctx: dict = Depends(owner_only)):
    current = await expense_claims.find_one({"_id": oid(claim_id)})
    if not current:
        raise HTTPException(404, "Expense claim not found")
    await _owner_can_access(ctx, current["plant_id"])
    if current.get("status") == "APPROVED" and body.action == "APPROVE":
        return {"expense_claim": _serialize(current), "idempotent": True}
    if body.action == "APPROVE" and current.get("status") != "VERIFIED":
        raise HTTPException(409, "Accountant verification is required before owner approval")
    if body.action == "REJECT" and current.get("status") not in ("SUBMITTED", "VERIFIED"):
        raise HTTPException(409, "Expense claim cannot be rejected from its current status")
    if body.action == "REJECT" and not (body.note or "").strip():
        raise HTTPException(422, "Rejection reason is required")

    now = _utcnow()
    if body.action == "REJECT":
        updated = await expense_claims.find_one_and_update(
            {"_id": current["_id"], "status": current["status"]},
            {"$set": {
                "status": "REJECTED",
                "owner_id": ctx["user_id"],
                "owner_note": body.note.strip(),
                "owner_decided_at": now,
                "updated_at": now,
            }},
            return_document=ReturnDocument.AFTER,
        )
        if not updated:
            raise HTTPException(409, "Expense claim changed concurrently; refresh and retry")
        await write_audit(ctx["user_id"], "workforce.expense.rejected", "expense_claim", claim_id, {"plant_id": current["plant_id"]})
        await record_notification(
            current["user_id"], "workforce_expense_rejected", "Expense claim rejected",
            f"Your ₹{float(current.get('amount') or 0):,.2f} expense claim was rejected.",
        )
        return {"expense_claim": _serialize(updated)}

    claimed = await expense_claims.find_one_and_update(
        {"_id": current["_id"], "status": "VERIFIED"},
        {"$set": {"status": "POSTING", "owner_id": ctx["user_id"], "updated_at": now}},
        return_document=ReturnDocument.AFTER,
    )
    if not claimed:
        latest = await expense_claims.find_one({"_id": current["_id"]})
        if latest and latest.get("status") == "APPROVED":
            return {"expense_claim": _serialize(latest), "idempotent": True}
        raise HTTPException(409, "Expense claim changed concurrently; refresh and retry")

    finance_doc = {
        "plant_id": current["plant_id"],
        "category": current["category"],
        "amount": current["amount"],
        "expense_date": current["expense_date"],
        "description": current["description"],
        "reference": current.get("receipt_reference"),
        "claim_id": claim_id,
        "source": "WORKFORCE_CLAIM",
        "created_by": current["user_id"],
        "approved_by": ctx["user_id"],
        "created_at": now,
    }
    try:
        result = await expenses.insert_one(finance_doc)
    except DuplicateKeyError:
        existing = await expenses.find_one({"claim_id": claim_id})
        if not existing:
            await expense_claims.update_one(
                {"_id": current["_id"], "status": "POSTING"},
                {"$set": {"status": "VERIFIED", "updated_at": _utcnow()}},
            )
            raise HTTPException(409, "Expense ledger posting conflicted; refresh and retry")
        result_id = existing["_id"]
    except Exception:
        await expense_claims.update_one(
            {"_id": current["_id"], "status": "POSTING"},
            {"$set": {"status": "VERIFIED", "updated_at": _utcnow()}},
        )
        raise
    else:
        result_id = result.inserted_id

    updated = await expense_claims.find_one_and_update(
        {"_id": current["_id"], "status": "POSTING"},
        {"$set": {
            "status": "APPROVED",
            "finance_expense_id": str(result_id),
            "owner_note": (body.note or "").strip() or None,
            "owner_decided_at": _utcnow(),
            "updated_at": _utcnow(),
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "Expense was posted but claim finalization needs reconciliation")
    await write_audit(
        ctx["user_id"], "workforce.expense.approved", "expense_claim", claim_id,
        {"plant_id": current["plant_id"], "finance_expense_id": str(result_id)},
    )
    await record_notification(
        current["user_id"], "workforce_expense_approved", "Expense claim approved",
        f"Your ₹{float(current.get('amount') or 0):,.2f} expense claim was approved and posted to finance.",
    )
    return {"expense_claim": _serialize(updated)}
