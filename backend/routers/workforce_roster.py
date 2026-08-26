"""Shift, roster and geofenced attendance controls.

Attendance remains evidence for payroll, never an automatic salary decision.
Geofence results are recorded and flagged for Owner review rather than blindly
rejecting a punch, because mobile GPS accuracy can vary substantially.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from math import atan2, cos, radians, sin, sqrt
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from audit import write_audit
from business_access import oid, visible_plant_ids
from database import db, plants, staff_attendance, users
from notifications import record_notification
from roles import Role
from security import require_role
from routers.workforce import EMPLOYEE_ROLES, LocationEvidence, leave_requests

router = APIRouter(prefix="/api/workforce-roster", tags=["workforce-roster"])
attendance_router = APIRouter(prefix="/api/workforce", tags=["workforce-attendance"])

shifts = db.workforce_shifts
rosters = db.workforce_roster_assignments
attendance_configs = db.workforce_attendance_configs

employee_only = require_role(*EMPLOYEE_ROLES)
owner_only = require_role(Role.PLANT_OWNER.value)
report_read = require_role(Role.PLANT_OWNER.value, Role.ACCOUNTANT.value)


class ShiftBody(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    start_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    grace_minutes: int = Field(default=0, ge=0, le=180)
    half_day_threshold_minutes: int | None = Field(default=None, ge=30, le=720)
    active: bool = True


class RosterBody(BaseModel):
    shift_id: str | None = None
    week_off: bool = False
    note: str | None = Field(default=None, max_length=500)


class AttendanceConfigBody(BaseModel):
    radius_m: float | None = Field(default=None, ge=25, le=5000)
    timezone_name: str = Field(default="Asia/Kolkata", min_length=3, max_length=80)


class AttendanceOverrideBody(BaseModel):
    status: Literal["ACCEPTED", "EXCUSED", "CORRECTED"]
    reason: str = Field(min_length=3, max_length=1000)


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


def _parse_clock(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise HTTPException(422, "Shift time must use HH:MM") from exc


def shift_window(date_key: str, start_time: str, end_time: str, timezone_name: str = "Asia/Kolkata") -> tuple[datetime, datetime]:
    try:
        day = date.fromisoformat(date_key)
        zone = ZoneInfo(timezone_name)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise HTTPException(422, "Invalid attendance date or timezone") from exc
    start_clock = _parse_clock(start_time)
    end_clock = _parse_clock(end_time)
    start = datetime.combine(day, start_clock, tzinfo=zone)
    end = datetime.combine(day, end_clock, tzinfo=zone)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def haversine_distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6_371_000.0
    p1, p2 = radians(lat1), radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lng2 - lng1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return round(radius * 2 * atan2(sqrt(a), sqrt(1 - a)), 1)


def classify_shift(
    check_in: datetime | None,
    check_out: datetime | None,
    scheduled_start: datetime | None,
    scheduled_end: datetime | None,
    grace_minutes: int = 0,
    half_day_threshold_minutes: int | None = None,
) -> dict:
    result = {"late_minutes": 0, "early_departure_minutes": 0, "overtime_minutes": 0, "half_day_evidence": False, "missing_checkout": False}
    if not check_in:
        return result
    if check_in.tzinfo is None:
        check_in = check_in.replace(tzinfo=timezone.utc)
    if check_out and check_out.tzinfo is None:
        check_out = check_out.replace(tzinfo=timezone.utc)
    if scheduled_start:
        scheduled_start = scheduled_start.astimezone(check_in.tzinfo)
        late_seconds = (check_in - scheduled_start).total_seconds() - grace_minutes * 60
        result["late_minutes"] = max(0, round(late_seconds / 60))
    if not check_out:
        result["missing_checkout"] = True
        return result
    worked_minutes = max(0, round((check_out - check_in).total_seconds() / 60))
    if scheduled_end:
        scheduled_end = scheduled_end.astimezone(check_out.tzinfo)
        result["early_departure_minutes"] = max(0, round((scheduled_end - check_out).total_seconds() / 60))
        result["overtime_minutes"] = max(0, round((check_out - scheduled_end).total_seconds() / 60))
    if half_day_threshold_minutes is not None:
        result["half_day_evidence"] = worked_minutes < half_day_threshold_minutes
    return result


async def ensure_indexes() -> None:
    await shifts.create_index([("plant_id", 1), ("name", 1)], unique=True)
    await rosters.create_index([("plant_id", 1), ("user_id", 1), ("date", 1)], unique=True)
    await rosters.create_index([("plant_id", 1), ("date", 1), ("shift_id", 1)])
    await attendance_configs.create_index("plant_id", unique=True)


async def _owner_plant(ctx: dict, plant_id: str) -> None:
    if plant_id not in await visible_plant_ids(ctx):
        raise HTTPException(403, "Plant access denied")


def _employee_plant(ctx: dict) -> str:
    plant_id = ctx.get("plant_id") or ctx.get("user", {}).get("plant_id")
    if ctx.get("role") not in EMPLOYEE_ROLES or not plant_id:
        raise HTTPException(403, "Plant workforce assignment required")
    return str(plant_id)


async def _config(plant_id: str) -> dict:
    return await attendance_configs.find_one({"plant_id": plant_id}) or {"plant_id": plant_id, "radius_m": None, "timezone_name": "Asia/Kolkata"}


async def _plant_local_today(plant_id: str) -> tuple[str, ZoneInfo]:
    cfg = await _config(plant_id)
    try:
        zone = ZoneInfo(str(cfg.get("timezone_name") or "Asia/Kolkata"))
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(409, "Plant attendance timezone is invalid") from exc
    return _utcnow().astimezone(zone).date().isoformat(), zone


async def _roster_context(plant_id: str, user_id: str, date_key: str) -> tuple[dict | None, dict | None, dict]:
    roster = await rosters.find_one({"plant_id": plant_id, "user_id": user_id, "date": date_key})
    shift = None
    if roster and roster.get("shift_id"):
        shift = await shifts.find_one({"_id": oid(str(roster["shift_id"])), "plant_id": plant_id})
    return roster, shift, await _config(plant_id)


async def _geofence_evidence(plant_id: str, body: LocationEvidence) -> dict:
    cfg = await _config(plant_id)
    plant = await plants.find_one({"_id": oid(plant_id)})
    radius = cfg.get("radius_m")
    plat = (plant or {}).get("lat")
    plng = (plant or {}).get("lng")
    if radius is None or plat is None or plng is None:
        return {"geofence_configured": False, "within_geofence": None, "distance_m": None, "radius_m": radius}
    distance = haversine_distance_m(float(body.lat), float(body.lng), float(plat), float(plng))
    return {"geofence_configured": True, "within_geofence": distance <= float(radius), "distance_m": distance, "radius_m": float(radius)}


@router.get("/me")
async def my_roster(ctx: dict = Depends(employee_only)):
    plant_id = _employee_plant(ctx)
    today_key, _ = await _plant_local_today(plant_id)
    end_key = (date.fromisoformat(today_key) + timedelta(days=14)).isoformat()
    rows = await rosters.find({"plant_id": plant_id, "user_id": ctx["user_id"], "date": {"$gte": today_key, "$lte": end_key}}).sort("date", 1).to_list(31)
    shift_ids = [oid(str(row["shift_id"])) for row in rows if row.get("shift_id")]
    shift_rows = await shifts.find({"_id": {"$in": shift_ids}}).to_list(100) if shift_ids else []
    shift_map = {str(row["_id"]): row for row in shift_rows}
    return {
        "plant_id": plant_id,
        "today": today_key,
        "attendance_config": _serialize(await attendance_configs.find_one({"plant_id": plant_id})),
        "roster": [{**_serialize(row), "shift": _serialize(shift_map.get(str(row.get("shift_id"))))} for row in rows],
    }


@router.get("/overview/{date_key}")
async def roster_overview(date_key: str, ctx: dict = Depends(report_read)):
    try:
        target = date.fromisoformat(date_key)
    except ValueError as exc:
        raise HTTPException(422, "Date must use YYYY-MM-DD") from exc
    plant_ids = await visible_plant_ids(ctx) if ctx.get("role") == Role.PLANT_OWNER.value else [str(ctx.get("plant_id") or ctx.get("user", {}).get("plant_id") or "")]
    if not plant_ids or not plant_ids[0]:
        raise HTTPException(403, "Plant assignment required")
    output = []
    for plant_id in plant_ids:
        staff = await users.find({"plant_id": plant_id, "primary_role": {"$in": list(EMPLOYEE_ROLES)}, "status": {"$nin": ["suspended", "disabled", "deleted"]}}).sort("name", 1).to_list(2000)
        roster_rows = await rosters.find({"plant_id": plant_id, "date": date_key}).to_list(5000)
        roster_map = {str(row.get("user_id")): row for row in roster_rows}
        shift_rows = await shifts.find({"plant_id": plant_id, "active": True}).sort("name", 1).to_list(200)
        shift_map = {str(row["_id"]): row for row in shift_rows}
        attendance_rows = await staff_attendance.find({"plant_id": plant_id, "date": date_key}).to_list(5000)
        attendance_map = {str(row.get("user_id")): row for row in attendance_rows}
        approved_leaves = await leave_requests.find({"plant_id": plant_id, "status": "APPROVED", "start_date": {"$lte": date_key}, "end_date": {"$gte": date_key}}).to_list(5000)
        leave_users = {str(row.get("user_id")) for row in approved_leaves}
        employees = []
        for user in staff:
            uid = str(user["_id"])
            roster = roster_map.get(uid)
            attendance = attendance_map.get(uid)
            if roster and roster.get("week_off"):
                classification = "WEEK_OFF"
            elif uid in leave_users:
                classification = "LEAVE"
            elif attendance and attendance.get("check_in"):
                classification = "PRESENT" if attendance.get("check_out") else "INCOMPLETE"
            elif target < _utcnow().date():
                classification = "ABSENT"
            else:
                classification = "SCHEDULED"
            employees.append({
                "user_id": uid, "name": user.get("name") or "Staff", "role": user.get("primary_role"),
                "classification": classification, "roster": _serialize(roster),
                "shift": _serialize(shift_map.get(str((roster or {}).get("shift_id")))), "attendance": _serialize(attendance),
            })
        output.append({"plant_id": plant_id, "date": date_key, "shifts": [_serialize(row) for row in shift_rows], "employees": employees, "attendance_config": _serialize(await attendance_configs.find_one({"plant_id": plant_id}))})
    return {"date": date_key, "plants": output}


@router.post("/plants/{plant_id}/shifts")
async def create_shift(plant_id: str, body: ShiftBody, ctx: dict = Depends(owner_only)):
    await _owner_plant(ctx, plant_id)
    _parse_clock(body.start_time); _parse_clock(body.end_time)
    now = _utcnow()
    existing = await shifts.find_one({"plant_id": plant_id, "name": body.name.strip()})
    if existing:
        raise HTTPException(409, "Shift name already exists in this plant")
    doc = {**body.model_dump(), "name": body.name.strip(), "plant_id": plant_id, "created_by": ctx["user_id"], "created_at": now, "updated_at": now}
    result = await shifts.insert_one(doc); doc["_id"] = result.inserted_id
    await write_audit(ctx["user_id"], "workforce.shift.create", "workforce_shift", str(result.inserted_id), {"plant_id": plant_id, "name": body.name})
    return {"shift": _serialize(doc)}


@router.put("/plants/{plant_id}/shifts/{shift_id}")
async def update_shift(plant_id: str, shift_id: str, body: ShiftBody, ctx: dict = Depends(owner_only)):
    await _owner_plant(ctx, plant_id)
    _parse_clock(body.start_time); _parse_clock(body.end_time)
    current = await shifts.find_one({"_id": oid(shift_id), "plant_id": plant_id})
    if not current:
        raise HTTPException(404, "Shift not found")
    now = _utcnow()
    await shifts.update_one({"_id": current["_id"]}, {"$set": {**body.model_dump(), "name": body.name.strip(), "updated_by": ctx["user_id"], "updated_at": now}})
    updated = await shifts.find_one({"_id": current["_id"]})
    await write_audit(ctx["user_id"], "workforce.shift.update", "workforce_shift", shift_id, {"plant_id": plant_id})
    return {"shift": _serialize(updated)}


@router.put("/plants/{plant_id}/attendance-config")
async def save_attendance_config(plant_id: str, body: AttendanceConfigBody, ctx: dict = Depends(owner_only)):
    await _owner_plant(ctx, plant_id)
    try:
        ZoneInfo(body.timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(422, "Unknown timezone") from exc
    now = _utcnow()
    await attendance_configs.update_one({"plant_id": plant_id}, {"$set": {"plant_id": plant_id, **body.model_dump(), "updated_by": ctx["user_id"], "updated_at": now}, "$setOnInsert": {"created_at": now}}, upsert=True)
    config = await attendance_configs.find_one({"plant_id": plant_id})
    await write_audit(ctx["user_id"], "workforce.attendance_config.update", "attendance_config", plant_id, {"radius_m": body.radius_m, "timezone_name": body.timezone_name})
    return {"attendance_config": _serialize(config)}


@router.put("/plants/{plant_id}/roster/{date_key}/{user_id}")
async def save_roster(plant_id: str, date_key: str, user_id: str, body: RosterBody, ctx: dict = Depends(owner_only)):
    await _owner_plant(ctx, plant_id)
    try:
        date.fromisoformat(date_key)
    except ValueError as exc:
        raise HTTPException(422, "Date must use YYYY-MM-DD") from exc
    user = await users.find_one({"_id": oid(user_id), "plant_id": plant_id, "primary_role": {"$in": list(EMPLOYEE_ROLES)}})
    if not user:
        raise HTTPException(404, "Staff member not found")
    if body.week_off and body.shift_id:
        raise HTTPException(422, "Week-off roster cannot also have a shift")
    if body.shift_id:
        shift = await shifts.find_one({"_id": oid(body.shift_id), "plant_id": plant_id, "active": True})
        if not shift:
            raise HTTPException(404, "Active shift not found")
    now = _utcnow()
    payload = {"plant_id": plant_id, "user_id": user_id, "user_name": user.get("name") or "Staff", "date": date_key, "shift_id": body.shift_id, "week_off": body.week_off, "note": (body.note or "").strip() or None, "updated_by": ctx["user_id"], "updated_at": now}
    await rosters.update_one({"plant_id": plant_id, "user_id": user_id, "date": date_key}, {"$set": payload, "$setOnInsert": {"created_at": now}}, upsert=True)
    roster = await rosters.find_one({"plant_id": plant_id, "user_id": user_id, "date": date_key})
    await write_audit(ctx["user_id"], "workforce.roster.update", "workforce_roster", str((roster or {}).get("_id")), {"plant_id": plant_id, "user_id": user_id, "date": date_key})
    await record_notification(user_id, "workforce_roster_updated", "Work roster updated", f"Your roster for {date_key} was updated.")
    return {"roster": _serialize(roster)}


@router.post("/plants/{plant_id}/attendance/{attendance_id}/override")
async def override_attendance(plant_id: str, attendance_id: str, body: AttendanceOverrideBody, ctx: dict = Depends(owner_only)):
    await _owner_plant(ctx, plant_id)
    current = await staff_attendance.find_one({"_id": oid(attendance_id), "plant_id": plant_id})
    if not current:
        raise HTTPException(404, "Attendance record not found")
    now = _utcnow()
    updated = await staff_attendance.find_one_and_update({"_id": current["_id"]}, {"$set": {"owner_override_status": body.status, "owner_override_reason": body.reason.strip(), "owner_override_by": ctx["user_id"], "owner_override_at": now, "updated_at": now}}, return_document=ReturnDocument.AFTER)
    await write_audit(ctx["user_id"], "workforce.attendance.override", "staff_attendance", attendance_id, {"plant_id": plant_id, "status": body.status, "reason": body.reason.strip()})
    return {"attendance": _serialize(updated)}


@attendance_router.post("/attendance/punch-in")
async def punch_in_with_roster(body: LocationEvidence, ctx: dict = Depends(employee_only)):
    plant_id = _employee_plant(ctx)
    date_key, zone = await _plant_local_today(plant_id)
    now = _utcnow()
    existing = await staff_attendance.find_one({"user_id": ctx["user_id"], "date": date_key})
    if existing and existing.get("check_in"):
        if existing.get("plant_id") != plant_id:
            raise HTTPException(409, "Attendance is already recorded against another plant today")
        raise HTTPException(409, "Already punched in today")
    roster, shift, cfg = await _roster_context(plant_id, ctx["user_id"], date_key)
    geo = await _geofence_evidence(plant_id, body)
    schedule = None
    if shift:
        start, end = shift_window(date_key, shift["start_time"], shift["end_time"], str(cfg.get("timezone_name") or "Asia/Kolkata"))
        schedule = {"scheduled_start": start.astimezone(timezone.utc), "scheduled_end": end.astimezone(timezone.utc)}
    evidence = classify_shift(now, None, (schedule or {}).get("scheduled_start"), (schedule or {}).get("scheduled_end"), int((shift or {}).get("grace_minutes") or 0), (shift or {}).get("half_day_threshold_minutes"))
    payload = {
        "plant_id": plant_id, "user_name": ctx["user"].get("name"), "role": ctx["role"], "check_in": now,
        "check_in_lat": body.lat, "check_in_lng": body.lng, "check_in_accuracy_m": body.accuracy_m, "check_in_note": body.note,
        "check_in_geofence": geo, "roster_id": str((roster or {}).get("_id")) if roster else None, "shift_id": str((shift or {}).get("_id")) if shift else None,
        "attendance_timezone": getattr(zone, "key", "Asia/Kolkata"), **(schedule or {}), **evidence, "updated_at": now,
    }
    await staff_attendance.update_one({"user_id": ctx["user_id"], "date": date_key}, {"$set": payload, "$setOnInsert": {"created_at": now}}, upsert=True)
    await write_audit(ctx["user_id"], "workforce.attendance.punch_in", "staff_attendance", date_key, {"plant_id": plant_id, "distance_m": geo.get("distance_m"), "within_geofence": geo.get("within_geofence")})
    return {"status": "checked_in", "at": now.isoformat(), "geofence": geo, "shift_evidence": evidence}


@attendance_router.post("/attendance/punch-out")
async def punch_out_with_roster(body: LocationEvidence, ctx: dict = Depends(employee_only)):
    plant_id = _employee_plant(ctx)
    date_key, _ = await _plant_local_today(plant_id)
    now = _utcnow()
    doc = await staff_attendance.find_one({"user_id": ctx["user_id"], "plant_id": plant_id, "date": date_key})
    if not doc or not doc.get("check_in"):
        raise HTTPException(409, "Punch in before punching out")
    if doc.get("check_out"):
        raise HTTPException(409, "Already punched out today")
    shift = await shifts.find_one({"_id": oid(str(doc.get("shift_id"))), "plant_id": plant_id}) if doc.get("shift_id") else None
    geo = await _geofence_evidence(plant_id, body)
    evidence = classify_shift(doc.get("check_in"), now, doc.get("scheduled_start"), doc.get("scheduled_end"), int((shift or {}).get("grace_minutes") or 0), (shift or {}).get("half_day_threshold_minutes"))
    updated = await staff_attendance.find_one_and_update({"_id": doc["_id"], "check_out": {"$exists": False}}, {"$set": {"check_out": now, "check_out_lat": body.lat, "check_out_lng": body.lng, "check_out_accuracy_m": body.accuracy_m, "check_out_note": body.note, "check_out_geofence": geo, **evidence, "updated_at": now}}, return_document=ReturnDocument.AFTER)
    if not updated:
        raise HTTPException(409, "Attendance changed concurrently; refresh and retry")
    await write_audit(ctx["user_id"], "workforce.attendance.punch_out", "staff_attendance", date_key, {"plant_id": plant_id, "distance_m": geo.get("distance_m"), "within_geofence": geo.get("within_geofence"), "overtime_minutes": evidence.get("overtime_minutes")})
    return {"status": "checked_out", "at": now.isoformat(), "geofence": geo, "shift_evidence": evidence}
