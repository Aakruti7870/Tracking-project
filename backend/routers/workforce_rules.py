"""Shift, roster, geofence and attendance-rule engine for plant workforce.

PR33 builds on PR31 attendance records and PR32 reporting. It keeps raw punch
records intact while adding explicit plant-local shift rules, roster evidence,
geofence review flags and audited correction requests.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from audit import write_audit
from business_access import oid, visible_plant_ids
from database import db, staff_attendance, users
from notifications import record_notification
from roles import Role
from security import require_role
from routers.workforce import EMPLOYEE_ROLES, LocationEvidence, _employee_plant

router = APIRouter(prefix="/api/workforce-rules", tags=["workforce-rules"])
shadow_router = APIRouter(prefix="/api/workforce", tags=["workforce"])

shift_templates = db.workforce_shift_templates
rosters = db.workforce_rosters
attendance_settings = db.workforce_attendance_settings
attendance_corrections = db.workforce_attendance_corrections

employee_only = require_role(*EMPLOYEE_ROLES)
owner_only = require_role(Role.PLANT_OWNER.value)
report_access = require_role(Role.PLANT_OWNER.value, Role.ACCOUNTANT.value)


class AttendanceSettingsBody(BaseModel):
    center_lat: float = Field(ge=-90, le=90)
    center_lng: float = Field(ge=-180, le=180)
    radius_m: float = Field(default=250, ge=25, le=10_000)
    timezone_name: str = Field(default="Asia/Kolkata", min_length=3, max_length=80)
    enabled: bool = True
    max_accuracy_m: float = Field(default=250, ge=10, le=5000)


class ShiftTemplateBody(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    start_time: str = Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    end_time: str = Field(pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")
    grace_minutes: int = Field(default=10, ge=0, le=180)
    half_day_minutes: int = Field(default=240, ge=30, le=720)
    full_day_minutes: int = Field(default=480, ge=60, le=1440)
    overtime_after_minutes: int = Field(default=540, ge=60, le=1440)
    active: bool = True


class RosterAssignmentBody(BaseModel):
    shift_id: str | None = Field(default=None, max_length=128)
    week_off: bool = False
    note: str | None = Field(default=None, max_length=500)


class AttendanceCorrectionBody(BaseModel):
    attendance_date: date
    requested_check_in: datetime | None = None
    requested_check_out: datetime | None = None
    reason: str = Field(min_length=5, max_length=1000)


class DecisionBody(BaseModel):
    action: Literal["APPROVE", "REJECT"]
    note: str | None = Field(default=None, max_length=1000)


class GeofenceReviewBody(BaseModel):
    action: Literal["ACCEPT", "FLAG"]
    note: str = Field(min_length=3, max_length=1000)


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


def _tz(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or "Asia/Kolkata")
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(422, "Invalid IANA timezone") from exc


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    earth_m = 6_371_000.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return round(2 * earth_m * asin(sqrt(a)), 1)


def _clock(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def shift_bounds(day: date, shift: dict, timezone_name: str) -> tuple[datetime, datetime]:
    zone = _tz(timezone_name)
    start = datetime.combine(day, _clock(str(shift["start_time"])), zone)
    end = datetime.combine(day, _clock(str(shift["end_time"])), zone)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def classify_attendance(doc: dict | None, roster: dict | None, shift: dict | None, timezone_name: str) -> dict:
    if roster and roster.get("week_off"):
        return {
            "classification": "WEEK_OFF_WORK" if doc and doc.get("check_in") else "WEEK_OFF",
            "worked_minutes": 0,
            "late_minutes": 0,
            "early_departure_minutes": 0,
            "overtime_minutes": 0,
        }
    if not doc or not doc.get("check_in"):
        return {"classification": "ABSENT", "worked_minutes": 0, "late_minutes": 0, "early_departure_minutes": 0, "overtime_minutes": 0}
    if not doc.get("check_out"):
        return {"classification": "OPEN", "worked_minutes": 0, "late_minutes": 0, "early_departure_minutes": 0, "overtime_minutes": 0}

    check_in = doc["check_in"]
    check_out = doc["check_out"]
    if check_in.tzinfo is None:
        check_in = check_in.replace(tzinfo=timezone.utc)
    if check_out.tzinfo is None:
        check_out = check_out.replace(tzinfo=timezone.utc)
    worked = max(0, int((check_out - check_in).total_seconds() // 60))
    result = {
        "classification": "PRESENT",
        "worked_minutes": worked,
        "late_minutes": 0,
        "early_departure_minutes": 0,
        "overtime_minutes": 0,
    }
    if not shift:
        return result

    local_day = date.fromisoformat(str(doc.get("date")))
    scheduled_start, scheduled_end = shift_bounds(local_day, shift, timezone_name)
    local_in = check_in.astimezone(_tz(timezone_name))
    local_out = check_out.astimezone(_tz(timezone_name))
    grace = int(shift.get("grace_minutes") or 0)
    result["late_minutes"] = max(0, int((local_in - scheduled_start).total_seconds() // 60) - grace)
    result["early_departure_minutes"] = max(0, int((scheduled_end - local_out).total_seconds() // 60))
    result["overtime_minutes"] = max(0, worked - int(shift.get("overtime_after_minutes") or 540))
    if worked < int(shift.get("half_day_minutes") or 240):
        result["classification"] = "HALF_DAY"
    return result


async def ensure_indexes() -> None:
    await shift_templates.create_index([("plant_id", 1), ("name", 1)], unique=True)
    await shift_templates.create_index([("plant_id", 1), ("active", 1)])
    await rosters.create_index([("plant_id", 1), ("user_id", 1), ("date", 1)], unique=True)
    await rosters.create_index([("plant_id", 1), ("date", 1)])
    await attendance_settings.create_index("plant_id", unique=True)
    await attendance_corrections.create_index([("plant_id", 1), ("status", 1), ("created_at", -1)])
    await attendance_corrections.create_index([("user_id", 1), ("attendance_date", -1)])


async def _owner_plant(ctx: dict, plant_id: str) -> None:
    if plant_id not in await visible_plant_ids(ctx):
        raise HTTPException(403, "Plant access denied")


async def _settings(plant_id: str) -> dict:
    return await attendance_settings.find_one({"plant_id": plant_id}) or {
        "plant_id": plant_id,
        "enabled": False,
        "timezone_name": "Asia/Kolkata",
        "radius_m": 250,
        "max_accuracy_m": 250,
    }


async def _roster_for(plant_id: str, user_id: str, day_key: str) -> tuple[dict | None, dict | None]:
    roster = await rosters.find_one({"plant_id": plant_id, "user_id": user_id, "date": day_key})
    shift = None
    if roster and roster.get("shift_id"):
        shift = await shift_templates.find_one({"_id": oid(roster["shift_id"]), "plant_id": plant_id})
    return roster, shift


def _geofence_result(settings: dict, body: LocationEvidence) -> dict:
    if not settings.get("enabled") or settings.get("center_lat") is None or settings.get("center_lng") is None:
        return {"status": "UNCONFIGURED", "distance_m": None}
    distance = haversine_m(float(settings["center_lat"]), float(settings["center_lng"]), body.lat, body.lng)
    if body.accuracy_m is not None and body.accuracy_m > float(settings.get("max_accuracy_m") or 250):
        return {"status": "LOW_ACCURACY", "distance_m": distance}
    return {"status": "IN_RANGE" if distance <= float(settings.get("radius_m") or 250) else "OUTSIDE", "distance_m": distance}


@shadow_router.post("/attendance/punch-in")
async def punch_in_with_rules(body: LocationEvidence, ctx: dict = Depends(employee_only)):
    plant_id = _employee_plant(ctx)
    settings = await _settings(plant_id)
    zone = _tz(settings.get("timezone_name"))
    now = _utcnow()
    day_key = now.astimezone(zone).date().isoformat()
    existing = await staff_attendance.find_one({"user_id": ctx["user_id"], "date": day_key})
    if existing and existing.get("check_in"):
        if existing.get("plant_id") != plant_id:
            raise HTTPException(409, "Attendance is already recorded against another plant today")
        raise HTTPException(409, "Already punched in today")

    geo = _geofence_result(settings, body)
    needs_review = geo["status"] in ("OUTSIDE", "LOW_ACCURACY")
    await staff_attendance.update_one(
        {"user_id": ctx["user_id"], "date": day_key},
        {"$set": {
            "plant_id": plant_id,
            "user_name": ctx["user"].get("name"),
            "role": ctx["role"],
            "check_in": now,
            "check_in_lat": body.lat,
            "check_in_lng": body.lng,
            "check_in_accuracy_m": body.accuracy_m,
            "check_in_note": body.note,
            "check_in_geofence_status": geo["status"],
            "check_in_distance_m": geo["distance_m"],
            "geofence_review_status": "PENDING" if needs_review else "NOT_REQUIRED",
            "updated_at": now,
        }, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    await write_audit(ctx["user_id"], "workforce.attendance.punch_in", "staff_attendance", day_key, {"plant_id": plant_id, "geofence": geo})
    return {"status": "checked_in", "at": now.isoformat(), "geofence": geo, "review_required": needs_review}


@shadow_router.post("/attendance/punch-out")
async def punch_out_with_rules(body: LocationEvidence, ctx: dict = Depends(employee_only)):
    plant_id = _employee_plant(ctx)
    settings = await _settings(plant_id)
    zone = _tz(settings.get("timezone_name"))
    now = _utcnow()
    day_key = now.astimezone(zone).date().isoformat()
    doc = await staff_attendance.find_one({"user_id": ctx["user_id"], "plant_id": plant_id, "date": day_key})
    if not doc or not doc.get("check_in"):
        raise HTTPException(409, "Punch in before punching out")
    if doc.get("check_out"):
        raise HTTPException(409, "Already punched out today")

    geo = _geofence_result(settings, body)
    needs_review = geo["status"] in ("OUTSIDE", "LOW_ACCURACY") or doc.get("geofence_review_status") == "PENDING"
    updated = await staff_attendance.find_one_and_update(
        {"_id": doc["_id"], "check_out": {"$exists": False}},
        {"$set": {
            "check_out": now,
            "check_out_lat": body.lat,
            "check_out_lng": body.lng,
            "check_out_accuracy_m": body.accuracy_m,
            "check_out_note": body.note,
            "check_out_geofence_status": geo["status"],
            "check_out_distance_m": geo["distance_m"],
            "geofence_review_status": "PENDING" if needs_review else "NOT_REQUIRED",
            "updated_at": now,
        }},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "Attendance changed concurrently; refresh and retry")
    roster, shift = await _roster_for(plant_id, ctx["user_id"], day_key)
    evaluation = classify_attendance(updated, roster, shift, str(settings.get("timezone_name") or "Asia/Kolkata"))
    await staff_attendance.update_one({"_id": updated["_id"]}, {"$set": {"rule_evaluation": evaluation}})
    await write_audit(ctx["user_id"], "workforce.attendance.punch_out", "staff_attendance", day_key, {"plant_id": plant_id, "geofence": geo, "evaluation": evaluation})
    return {"status": "checked_out", "at": now.isoformat(), "geofence": geo, "review_required": needs_review, "evaluation": evaluation}


@router.get("/me")
async def my_rules(ctx: dict = Depends(employee_only)):
    plant_id = _employee_plant(ctx)
    settings = await _settings(plant_id)
    zone = _tz(settings.get("timezone_name"))
    today = _utcnow().astimezone(zone).date()
    end = today + timedelta(days=14)
    roster_rows = await rosters.find({"plant_id": plant_id, "user_id": ctx["user_id"], "date": {"$gte": today.isoformat(), "$lte": end.isoformat()}}).sort("date", 1).to_list(31)
    shifts = await shift_templates.find({"plant_id": plant_id, "active": True}).to_list(100)
    shift_map = {str(row["_id"]): row for row in shifts}
    corrections = await attendance_corrections.find({"plant_id": plant_id, "user_id": ctx["user_id"]}).sort("created_at", -1).to_list(20)
    return {
        "plant_id": plant_id,
        "timezone_name": settings.get("timezone_name"),
        "geofence_enabled": bool(settings.get("enabled")),
        "roster": [{**_serialize(row), "shift": _serialize(shift_map.get(str(row.get("shift_id"))))} for row in roster_rows],
        "corrections": [_serialize(row) for row in corrections],
    }


@router.put("/plants/{plant_id}/settings")
async def save_settings(plant_id: str, body: AttendanceSettingsBody, ctx: dict = Depends(owner_only)):
    await _owner_plant(ctx, plant_id)
    _tz(body.timezone_name)
    now = _utcnow()
    await attendance_settings.update_one({"plant_id": plant_id}, {"$set": {**body.model_dump(), "plant_id": plant_id, "updated_by": ctx["user_id"], "updated_at": now}, "$setOnInsert": {"created_at": now}}, upsert=True)
    doc = await attendance_settings.find_one({"plant_id": plant_id})
    await write_audit(ctx["user_id"], "workforce.rules.settings", "attendance_settings", plant_id, {"enabled": body.enabled, "radius_m": body.radius_m})
    return {"settings": _serialize(doc)}


@router.post("/plants/{plant_id}/shifts")
async def create_shift(plant_id: str, body: ShiftTemplateBody, ctx: dict = Depends(owner_only)):
    await _owner_plant(ctx, plant_id)
    if body.overtime_after_minutes < body.half_day_minutes:
        raise HTTPException(422, "Overtime threshold cannot be below half-day minutes")
    now = _utcnow()
    doc = {**body.model_dump(), "plant_id": plant_id, "created_by": ctx["user_id"], "created_at": now, "updated_at": now}
    try:
        result = await shift_templates.insert_one(doc)
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise HTTPException(409, "A shift with this name already exists") from exc
        raise
    doc["_id"] = result.inserted_id
    await write_audit(ctx["user_id"], "workforce.rules.shift.create", "shift_template", str(result.inserted_id), {"plant_id": plant_id, "name": body.name})
    return {"shift": _serialize(doc)}


@router.put("/plants/{plant_id}/roster/{day_key}/{user_id}")
async def assign_roster(plant_id: str, day_key: date, user_id: str, body: RosterAssignmentBody, ctx: dict = Depends(owner_only)):
    await _owner_plant(ctx, plant_id)
    employee = await users.find_one({"_id": oid(user_id), "plant_id": plant_id, "primary_role": {"$in": list(EMPLOYEE_ROLES)}})
    if not employee:
        raise HTTPException(404, "Staff member not found")
    shift = None
    if not body.week_off:
        if not body.shift_id:
            raise HTTPException(422, "Shift is required unless this is a week off")
        shift = await shift_templates.find_one({"_id": oid(body.shift_id), "plant_id": plant_id, "active": True})
        if not shift:
            raise HTTPException(404, "Active shift not found")
    now = _utcnow()
    payload = {"plant_id": plant_id, "user_id": user_id, "user_name": employee.get("name") or "Staff", "date": day_key.isoformat(), "shift_id": str(shift["_id"]) if shift else None, "week_off": body.week_off, "note": body.note, "updated_by": ctx["user_id"], "updated_at": now}
    await rosters.update_one({"plant_id": plant_id, "user_id": user_id, "date": day_key.isoformat()}, {"$set": payload, "$setOnInsert": {"created_at": now}}, upsert=True)
    doc = await rosters.find_one({"plant_id": plant_id, "user_id": user_id, "date": day_key.isoformat()})
    await record_notification(user_id, "workforce_roster_update", "Work roster updated", f"Your roster for {day_key.isoformat()} was updated.")
    await write_audit(ctx["user_id"], "workforce.rules.roster.assign", "workforce_roster", str((doc or {}).get("_id")), {"plant_id": plant_id, "date": day_key.isoformat(), "week_off": body.week_off})
    return {"roster": _serialize(doc)}


@router.post("/attendance-corrections")
async def request_correction(body: AttendanceCorrectionBody, ctx: dict = Depends(employee_only)):
    plant_id = _employee_plant(ctx)
    if body.attendance_date > _utcnow().date():
        raise HTTPException(422, "Future attendance cannot be corrected")
    if not body.requested_check_in and not body.requested_check_out:
        raise HTTPException(422, "Provide a corrected punch-in or punch-out time")
    if body.requested_check_in and body.requested_check_out and body.requested_check_out <= body.requested_check_in:
        raise HTTPException(422, "Corrected punch-out must be after punch-in")
    existing_pending = await attendance_corrections.find_one({"plant_id": plant_id, "user_id": ctx["user_id"], "attendance_date": body.attendance_date.isoformat(), "status": "PENDING"})
    if existing_pending:
        raise HTTPException(409, "A correction request is already pending for this date")
    now = _utcnow()
    doc = {"plant_id": plant_id, "user_id": ctx["user_id"], "user_name": ctx["user"].get("name"), "attendance_date": body.attendance_date.isoformat(), "requested_check_in": body.requested_check_in, "requested_check_out": body.requested_check_out, "reason": body.reason.strip(), "status": "PENDING", "created_at": now, "updated_at": now}
    result = await attendance_corrections.insert_one(doc)
    doc["_id"] = result.inserted_id
    await write_audit(ctx["user_id"], "workforce.rules.correction.submit", "attendance_correction", str(result.inserted_id), {"plant_id": plant_id, "date": body.attendance_date.isoformat()})
    return {"correction": _serialize(doc)}


@router.post("/plants/{plant_id}/corrections/{correction_id}/decision")
async def decide_correction(plant_id: str, correction_id: str, body: DecisionBody, ctx: dict = Depends(owner_only)):
    await _owner_plant(ctx, plant_id)
    current = await attendance_corrections.find_one({"_id": oid(correction_id), "plant_id": plant_id})
    if not current:
        raise HTTPException(404, "Correction request not found")
    if current.get("status") != "PENDING":
        raise HTTPException(409, "Correction request is already decided")
    now = _utcnow()
    updated = await attendance_corrections.find_one_and_update({"_id": current["_id"], "status": "PENDING"}, {"$set": {"status": "APPROVED" if body.action == "APPROVE" else "REJECTED", "decision_note": (body.note or "").strip() or None, "decided_by": ctx["user_id"], "decided_at": now, "updated_at": now}}, return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(409, "Correction changed concurrently; refresh and retry")
    if body.action == "APPROVE":
        changes = {"corrected_by": ctx["user_id"], "corrected_at": now, "updated_at": now}
        if current.get("requested_check_in"):
            changes["check_in"] = current["requested_check_in"]
        if current.get("requested_check_out"):
            changes["check_out"] = current["requested_check_out"]
        await staff_attendance.update_one({"plant_id": plant_id, "user_id": current["user_id"], "date": current["attendance_date"]}, {"$set": changes})
    await record_notification(current["user_id"], "workforce_attendance_correction_decision", "Attendance correction updated", f"Your attendance correction for {current['attendance_date']} was {updated['status'].lower()}.")
    await write_audit(ctx["user_id"], f"workforce.rules.correction.{updated['status'].lower()}", "attendance_correction", correction_id, {"plant_id": plant_id, "date": current["attendance_date"]})
    return {"correction": _serialize(updated)}


@router.post("/plants/{plant_id}/attendance/{day_key}/{user_id}/geofence-review")
async def review_geofence(plant_id: str, day_key: date, user_id: str, body: GeofenceReviewBody, ctx: dict = Depends(owner_only)):
    await _owner_plant(ctx, plant_id)
    now = _utcnow()
    updated = await staff_attendance.find_one_and_update({"plant_id": plant_id, "user_id": user_id, "date": day_key.isoformat(), "geofence_review_status": "PENDING"}, {"$set": {"geofence_review_status": "ACCEPTED" if body.action == "ACCEPT" else "FLAGGED", "geofence_review_note": body.note.strip(), "geofence_reviewed_by": ctx["user_id"], "geofence_reviewed_at": now, "updated_at": now}}, return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(409, "No pending geofence exception found for this attendance record")
    await write_audit(ctx["user_id"], "workforce.rules.geofence.review", "staff_attendance", str(updated["_id"]), {"plant_id": plant_id, "date": day_key.isoformat(), "action": body.action})
    return {"attendance": _serialize(updated)}


@router.get("/owner/control")
async def owner_control(ctx: dict = Depends(owner_only)):
    plant_ids = await visible_plant_ids(ctx)
    today = _utcnow().date().isoformat()
    out = []
    for plant_id in plant_ids:
        settings = await _settings(plant_id)
        shifts = await shift_templates.find({"plant_id": plant_id}).sort("name", 1).to_list(100)
        roster_rows = await rosters.find({"plant_id": plant_id, "date": {"$gte": today}}).sort("date", 1).to_list(1000)
        pending = await attendance_corrections.find({"plant_id": plant_id, "status": "PENDING"}).sort("created_at", -1).to_list(200)
        exceptions = await staff_attendance.find({"plant_id": plant_id, "geofence_review_status": "PENDING"}).sort("date", -1).to_list(200)
        staff = await users.find({"plant_id": plant_id, "primary_role": {"$in": list(EMPLOYEE_ROLES)}, "status": {"$nin": ["suspended", "disabled", "deleted"]}}).sort("name", 1).to_list(1000)
        out.append({"plant_id": plant_id, "settings": _serialize(settings), "shifts": [_serialize(row) for row in shifts], "roster": [_serialize(row) for row in roster_rows], "pending_corrections": [_serialize(row) for row in pending], "geofence_exceptions": [_serialize(row) for row in exceptions], "employees": [{"user_id": str(row["_id"]), "name": row.get("name") or "Staff", "role": row.get("primary_role")} for row in staff]})
    return {"mode": "owner", "plants": out}


@router.get("/monthly/{month}")
async def monthly_rules_report(month: str, ctx: dict = Depends(report_access)):
    try:
        first = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    except ValueError as exc:
        raise HTTPException(422, "Month must use YYYY-MM format") from exc
    next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    last = next_month - timedelta(days=1)
    if ctx.get("role") == Role.PLANT_OWNER.value:
        plant_ids = await visible_plant_ids(ctx)
    else:
        assigned = ctx.get("plant_id") or ctx.get("user", {}).get("plant_id")
        if not assigned:
            raise HTTPException(403, "Plant assignment required")
        plant_ids = [str(assigned)]
    reports = []
    for plant_id in plant_ids:
        settings = await _settings(plant_id)
        rows = await staff_attendance.find({"plant_id": plant_id, "date": {"$gte": first.isoformat(), "$lte": last.isoformat()}}).sort("date", 1).to_list(10000)
        evidence = []
        for row in rows:
            roster, shift = await _roster_for(plant_id, str(row.get("user_id")), str(row.get("date")))
            evaluation = classify_attendance(row, roster, shift, str(settings.get("timezone_name") or "Asia/Kolkata"))
            evidence.append({"attendance_id": str(row["_id"]), "user_id": str(row.get("user_id")), "user_name": row.get("user_name"), "date": row.get("date"), "geofence_review_status": row.get("geofence_review_status", "NOT_REQUIRED"), **evaluation})
        reports.append({"plant_id": plant_id, "month": month, "evidence": evidence})
    return {"month": month, "reports": reports}
