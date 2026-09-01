"""Customer role endpoints (server-side authorized to the customer role)."""
from datetime import datetime, time, timedelta, timezone
import logging
import math

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.errors import DuplicateKeyError
from pydantic import Field
from validation import StrictModel

from audit import write_audit
from database import (
    challans,
    customer_sites,
    kyc_profiles,
    notifications,
    order_loads,
    order_status_history,
    orders,
    plants,
    plant_promotions,
    proof_of_delivery,
    pour_plans,
    quotation_requests,
    quotations,
    rate_cards,
    receiving_records,
    users,
    vehicle_locations,
    next_sequence,
)
from business_models import CustomerCubeTestResultBody, CustomerPourPlanBody, CustomerReceivingRecordBody
from models import CreateOrderBody
from notifications import record_notification
from order_service import CANCELLED, DRAFT, PENDING, transition_order
from roles import Role
from security import require_role
from services.digilocker import (
    DigiLockerConfigurationError,
    DigiLockerProviderError,
    get_digilocker_session_status,
    get_digilocker_user_profile,
    initiate_digilocker_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/customer", tags=["customer"])
customer_only = require_role(Role.CUSTOMER.value)

# Discovery visibility and order eligibility are intentionally separate.
# Customers should be able to discover registered RMC plants even while a
# plant is inactive or awaiting verification. Only explicitly removed plants
# are hidden from discovery; order creation remains protected below.
CUSTOMER_HIDDEN_PLANT_STATUSES = ("deleted", "disabled")


def _customer_visible_plant_filter() -> dict:
    return {"status": {"$nin": list(CUSTOMER_HIDDEN_PLANT_STATUSES)}}


def _plant_state(doc: dict) -> tuple[str, bool, bool]:
    status = str(doc.get("status") or "active").lower()
    verified = bool(doc.get("verified", False))
    order_enabled = status == "active" and verified
    return status, verified, order_enabled


def _plant_discovery_sort_key(doc: dict) -> tuple[int, int, int, str]:
    status, verified, order_enabled = _plant_state(doc)
    return (0 if doc.get("promoted") else 1, 0 if order_enabled else 1, 0 if verified else 1, str(doc.get("name") or "").lower())


async def _attach_active_promotions(rows: list[dict]) -> None:
    """Annotate customer-facing plants without changing the source documents."""
    if not rows:
        return
    ids = [str(row["_id"]) for row in rows]
    active = await plant_promotions.find({
        "plant_id": {"$in": ids}, "status": "ACTIVE", "ends_at": {"$gt": datetime.now(timezone.utc)},
    }).to_list(len(ids))
    promoted = {row["plant_id"]: row for row in active}
    for row in rows:
        promotion = promoted.get(str(row["_id"]))
        row["promoted"] = bool(promotion)
        row["promotion_ends_at"] = promotion.get("ends_at") if promotion else None


def _serialize_order(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]), "order_number": doc.get("order_number"),
        "plant_id": doc.get("plant_id"), "plant_name": doc.get("plant_name"), "site_id": doc.get("site_id"),
        "grade": doc.get("grade"), "quantity": doc.get("quantity"),
        "delivered_quantity": doc.get("delivered_quantity"),
        "site_name": doc.get("site_name"), "site_address": doc.get("site_address"),
        "delivery_date": doc.get("delivery_date"), "delivery_time": doc.get("delivery_time"),
        "delivery_mode": doc.get("delivery_mode", "DELIVERY"), "status": doc.get("status"),
        "payment_status": doc.get("payment_status"), "tm_number": doc.get("tm_number"),
        "driver_name": doc.get("driver_name"), "driver_mobile": doc.get("driver_mobile"),
        "challan_number": doc.get("challan_number"), "active_load_id": doc.get("active_load_id"),
        "invoice_number": doc.get("invoice_number"),
    }


def _serialize_plant(doc: dict) -> dict:
    status, verified, order_enabled = _plant_state(doc)
    return {
        "id": str(doc["_id"]), "name": doc.get("name"), "city": doc.get("city"),
        "district": doc.get("district"), "address": doc.get("address"),
        "lat": doc.get("lat"), "lng": doc.get("lng"), "grades": doc.get("grades", []),
        "contact_phone": doc.get("contact_phone"), "service_area_km": doc.get("service_area_km"),
        "status": status, "verified": verified, "order_enabled": order_enabled,
        "promoted": bool(doc.get("promoted")), "promotion_ends_at": doc.get("promotion_ends_at"),
    }


def _serialize_load(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]), "load_code": doc.get("load_code"),
        "load_number": doc.get("load_number"), "quantity_m3": doc.get("quantity_m3"),
        "delivered_quantity": doc.get("delivered_quantity"), "status": doc.get("status"),
        "tm_number": doc.get("tm_number"), "driver_name": doc.get("driver_name"),
        "driver_mobile": doc.get("driver_mobile"),
        "challan_number": doc.get("challan_number"), "gate_pass_number": doc.get("gate_pass_number"),
        "dispatched_at": doc.get("dispatched_at").isoformat() if doc.get("dispatched_at") else None,
        "delivered_at": doc.get("delivered_at").isoformat() if doc.get("delivered_at") else None,
    }


def _serialize_pod(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]), "load_id": doc.get("load_id"), "trip_id": doc.get("trip_id"),
        "receiver_name": doc.get("receiver_name"), "delivered_quantity": doc.get("delivered_quantity"),
        "remarks": doc.get("remarks"), "photo_path": doc.get("photo_path"),
        "signature": doc.get("signature"),
        "at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
    }


def _serialize_challan(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]), "load_id": doc.get("load_id"), "load_code": doc.get("load_code"),
        "challan_number": doc.get("challan_number"), "order_number": doc.get("order_number"),
        "plant_name": doc.get("plant_name"), "customer_name": doc.get("customer_name"),
        "site_name": doc.get("site_name"), "site_address": doc.get("site_address"),
        "grade": doc.get("grade"), "quantity": doc.get("quantity"), "tm_number": doc.get("tm_number"),
        "driver_name": doc.get("driver_name"), "driver_mobile": doc.get("driver_mobile"),
        "batcher": doc.get("batcher"), "supervisor": doc.get("supervisor"),
        "quality_engineer": doc.get("quality_engineer"), "remarks": doc.get("remarks"),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
    }


ACTIVE_STATUSES = {
    "ACCEPTED", "SCHEDULED", "IN_PRODUCTION", "PRODUCTION_COMPLETE", "TM_ASSIGNED",
    "DRIVER_ASSIGNED", "READY_TO_DISPATCH", "DISPATCHED", "EN_ROUTE", "AT_SITE",
    "UNLOADING", "POD_PENDING",
}
ACTIVE_LOAD_STATUSES = {"DISPATCHED", "EN_ROUTE", "ARRIVED", "UNLOADING", "POD_PENDING"}


@router.get("/home")
async def home(ctx: dict = Depends(customer_only)):
    uid = ctx["user_id"]
    user = ctx["user"]
    kyc = await kyc_profiles.find_one({"user_id": uid, "purpose": "CUSTOMER"})
    my_orders = await orders.find({"customer_id": uid}).sort("created_at", -1).to_list(50)
    active = next((o for o in my_orders if o.get("status") in ACTIVE_STATUSES), None)
    visible_plants = await plants.find(_customer_visible_plant_filter()).to_list(500)
    await _attach_active_promotions(visible_plants)
    nearby = sorted(visible_plants, key=_plant_discovery_sort_key)[:5]
    unread = await notifications.count_documents({"user_id": uid, "read": False})
    return {
        "name": user.get("name"), "kyc_status": (kyc or {}).get("status", "NOT_STARTED"),
        "active_order": _serialize_order(active) if active else None,
        "recent_orders": [_serialize_order(o) for o in my_orders[:5]],
        "nearby_plants": [_serialize_plant(p) for p in nearby], "unread_notifications": unread,
    }


@router.get("/orders")
async def list_orders(ctx: dict = Depends(customer_only)):
    docs = await orders.find({"customer_id": ctx["user_id"]}).sort("created_at", -1).to_list(200)
    return {"orders": [_serialize_order(o) for o in docs]}


@router.get("/plants")
async def nearby_plants(ctx: dict = Depends(customer_only)):
    docs = await plants.find(_customer_visible_plant_filter()).to_list(500)
    await _attach_active_promotions(docs)
    docs.sort(key=_plant_discovery_sort_key)
    return {"plants": [_serialize_plant(p) for p in docs]}


def _distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    value = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


@router.get("/compare-plants")
async def compare_plants(
    grade: str = Query(pattern=r"^M(?:10|15|20|25|30|35|40|45|50|55|60)(?:[-_ ]?PILE)?$"),
    quantity: float = Query(gt=0, le=100000),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    pump_required: bool = False,
    ctx: dict = Depends(customer_only),
):
    """Return fair, rate-card-backed estimates; promoted status never changes sorting."""
    plant_rows = await plants.find({"status": "active", "verified": True, "grades": grade}).to_list(500)
    estimates = []
    for plant in plant_rows:
        pid = str(plant["_id"])
        cards = await rate_cards.find({"plant_id": pid, "grade": grade, "active": True}).sort("effective_from", -1).to_list(1)
        if not cards:
            continue
        card = cards[0]
        distance = None
        if lat is not None and lng is not None and plant.get("lat") is not None and plant.get("lng") is not None:
            distance = _distance_km(lat, lng, float(plant["lat"]), float(plant["lng"]))
        base_amount = float(card.get("rate_per_m3") or 0) * quantity
        transport = float(card.get("transport_rate_per_km") or 0) * distance if distance is not None else None
        pumping = float(card.get("pumping_rate_per_m3") or 0) * quantity if pump_required else 0
        subtotal_known = base_amount + (transport or 0) + pumping
        gst_rate = float(card.get("gst_rate") or 0)
        gst_amount = subtotal_known * gst_rate / 100
        total = subtotal_known + gst_amount
        service_area = float(plant.get("service_area_km") or 0)
        estimates.append({
            "plant_id": pid,
            "plant_name": plant.get("name"),
            "city": plant.get("city"),
            "district": plant.get("district"),
            "verified": True,
            "grade": grade,
            "quantity": quantity,
            "rate_per_m3": card.get("rate_per_m3"),
            "distance_km": round(distance, 2) if distance is not None else None,
            "service_area_km": service_area,
            "within_service_area": (distance <= service_area) if distance is not None and service_area > 0 else None,
            "base_amount": round(base_amount, 2),
            "transport_rate_per_km": card.get("transport_rate_per_km", 0),
            "transport_amount": round(transport, 2) if transport is not None else None,
            "pumping_rate_per_m3": card.get("pumping_rate_per_m3", 0),
            "pumping_amount": round(pumping, 2),
            "gst_rate": gst_rate,
            "gst_amount": round(gst_amount, 2),
            "estimated_total": round(total, 2),
            "transport_included": transport is not None,
            "effective_from": card.get("effective_from"),
        })
    estimates.sort(key=lambda row: (row["estimated_total"], row["distance_km"] if row["distance_km"] is not None else float("inf"), row["plant_name"] or ""))
    return {"estimates": estimates, "count": len(estimates), "disclaimer": "Estimate only. Final price, delivery eligibility and tax invoice require plant confirmation."}


class QuotationRequestBody(StrictModel):
    plant_id: str
    site_id: str | None = Field(default=None, max_length=128)
    grade: str = Field(pattern=r"^M(?:10|15|20|25|30|35|40|45|50|55|60)(?:[-_ ]?PILE)?$")
    quantity: float = Field(gt=0, le=100000)
    site_name: str = Field(min_length=1, max_length=180)
    site_address: str = Field(min_length=5, max_length=1000)
    estimated_total: float | None = Field(default=None, ge=0, le=1_000_000_000)
    pump_required: bool = False


@router.post("/quotation-requests")
async def request_quotation(body: QuotationRequestBody, ctx: dict = Depends(customer_only)):
    if body.site_id:
        site = await customer_sites.find_one({"_id": await _oid(body.site_id), "customer_id": ctx["user_id"]})
        if not site:
            raise HTTPException(422, "Saved site not found")
    plant = await plants.find_one({"_id": await _oid(body.plant_id), "status": "active", "verified": True})
    if not plant:
        raise HTTPException(404, "Plant not available")
    if body.grade not in plant.get("grades", []):
        raise HTTPException(422, "Selected grade not offered by this plant")
    now = datetime.now(timezone.utc)
    doc = {
        **body.model_dump(),
        "customer_id": ctx["user_id"],
        "customer_name": ctx["user"].get("name"),
        "customer_mobile": ctx["user"].get("phone"),
        "plant_name": plant.get("name"),
        "status": "REQUESTED",
        "created_at": now,
        "updated_at": now,
    }
    result = await quotation_requests.insert_one(doc)
    request_id = str(result.inserted_id)
    await write_audit(ctx["user_id"], "quotation.request", "quotation_request", request_id, {"plant_id": body.plant_id, "grade": body.grade, "quantity": body.quantity})
    if plant.get("owner_id"):
        await record_notification(
            plant["owner_id"], "quotation_request", "New quotation request",
            f"{ctx['user'].get('name') or 'A customer'} requested {body.quantity} m³ of {body.grade} for {body.site_name}.",
        )
    return {"id": request_id, "status": "REQUESTED"}


@router.get("/quotation-requests")
async def list_my_quotation_requests(ctx: dict = Depends(customer_only)):
    docs = await quotation_requests.find(
        {"customer_id": ctx["user_id"]}
    ).sort("created_at", -1).to_list(500)
    rows = []
    for doc in docs:
        row = {**doc, "id": str(doc["_id"])}
        row.pop("_id", None)
        for key, value in list(row.items()):
            if isinstance(value, ObjectId):
                row[key] = str(value)
            elif hasattr(value, "isoformat"):
                row[key] = value.isoformat()
        rows.append(row)
    return {"requests": rows}


def _site_key(name: str | None, address: str | None) -> str:
    return " ".join(f"{name or ''} {address or ''}".lower().split())


@router.get("/project-sites")
async def project_sites(ctx: dict = Depends(customer_only)):
    uid = ctx["user_id"]
    site_docs = await customer_sites.find({"customer_id": uid}).sort([("is_default", -1), ("created_at", -1)]).to_list(500)
    order_docs = await orders.find({"customer_id": uid}).sort("created_at", -1).to_list(2000)
    request_docs = await quotation_requests.find({"customer_id": uid}).sort("created_at", -1).to_list(2000)
    quote_docs = await quotations.find({"customer_id": uid}).sort("created_at", -1).to_list(2000)
    plan_docs = await pour_plans.find({"customer_id": uid}).sort("pour_date", -1).to_list(2000)
    receiving_docs = await receiving_records.find({"customer_id": uid}).sort("created_at", -1).to_list(2000)
    rows = []
    terminal = {"DELIVERED", "REJECTED", "CANCELLED"}
    for site in site_docs:
        sid = str(site["_id"])
        key = _site_key(site.get("name"), site.get("address"))
        def belongs(doc: dict) -> bool:
            return doc.get("site_id") == sid or (not doc.get("site_id") and _site_key(doc.get("site_name"), doc.get("site_address")) == key)
        site_orders = [doc for doc in order_docs if belongs(doc)]
        site_requests = [doc for doc in request_docs if belongs(doc)]
        site_quotes = [doc for doc in quote_docs if belongs(doc)]
        site_plans = [doc for doc in plan_docs if doc.get("site_id") == sid]
        site_receiving = [doc for doc in receiving_docs if doc.get("site_id") == sid]
        active_orders = [doc for doc in site_orders if doc.get("status") not in terminal and doc.get("status") != "DRAFT"]
        delivered = [doc for doc in site_orders if doc.get("status") == "DELIVERED"]
        upcoming = sorted(
            [doc for doc in active_orders if doc.get("delivery_date")],
            key=lambda doc: str(doc.get("delivery_date")),
        )
        latest = site_orders[0] if site_orders else None
        rows.append({
            "id": sid,
            "name": site.get("name"),
            "address": site.get("address"),
            "lat": site.get("lat"),
            "lng": site.get("lng"),
            "contact_person": site.get("contact_person"),
            "contact_mobile": site.get("contact_mobile"),
            "is_default": bool(site.get("is_default")),
            "orders_count": len(site_orders),
            "active_orders": len(active_orders),
            "delivered_orders": len(delivered),
            "ordered_m3": round(sum(float(doc.get("quantity") or 0) for doc in site_orders), 2),
            "delivered_m3": round(sum(float(doc.get("delivered_quantity") or doc.get("quantity") or 0) for doc in delivered), 2),
            "pour_plans": len(site_plans),
            "receiving_records": len(site_receiving),
            "pending_cube_tests": sum(_serialize_receiving_record(doc)["pending_cube_tests"] for doc in site_receiving),
            "overdue_cube_tests": sum(_serialize_receiving_record(doc)["overdue_cube_tests"] for doc in site_receiving),
            "quotation_requests": len(site_requests),
            "official_quotations": len(site_quotes),
            "open_quotations": sum(1 for doc in site_quotes if doc.get("status") in ("OPEN", "ACCEPTED")),
            "upcoming_delivery": {
                "order_id": str(upcoming[0]["_id"]),
                "order_number": upcoming[0].get("order_number"),
                "delivery_date": upcoming[0].get("delivery_date"),
                "delivery_time": upcoming[0].get("delivery_time"),
                "grade": upcoming[0].get("grade"),
                "quantity": upcoming[0].get("quantity"),
                "status": upcoming[0].get("status"),
            } if upcoming else None,
            "latest_order": {
                "id": str(latest["_id"]),
                "order_number": latest.get("order_number"),
                "status": latest.get("status"),
            } if latest else None,
        })
    return {"sites": rows, "count": len(rows)}


def _serialize_receiving_record(doc: dict) -> dict:
    row = {**doc, "id": str(doc["_id"])}
    row.pop("_id", None)
    for key, value in list(row.items()):
        if isinstance(value, ObjectId):
            row[key] = str(value)
        elif hasattr(value, "isoformat"):
            row[key] = value.isoformat()

    results = row.get("cube_test_results") or []
    completed = {(str(item.get("sample_id") or "").lower(), int(item.get("age_days") or 0)) for item in results}
    today = datetime.now(timezone.utc).date()
    follow_up = []
    for sample_id in row.get("cube_sample_ids") or []:
        for age_days, due_value in ((7, row.get("cube_7d_date")), (28, row.get("cube_28d_date"))):
            if not due_value:
                continue
            key = (str(sample_id).lower(), age_days)
            due_date = datetime.fromisoformat(str(due_value)).date()
            status = "RECORDED" if key in completed else ("OVERDUE" if due_date < today else ("DUE" if due_date == today else "UPCOMING"))
            follow_up.append({"sample_id": sample_id, "age_days": age_days, "due_date": str(due_value), "status": status})
    row["cube_follow_up"] = follow_up
    row["pending_cube_tests"] = sum(1 for item in follow_up if item["status"] != "RECORDED")
    row["overdue_cube_tests"] = sum(1 for item in follow_up if item["status"] == "OVERDUE")
    return row


@router.get("/receiving-records")
async def list_receiving_records(site_id: str | None = Query(default=None), ctx: dict = Depends(customer_only)):
    query: dict = {"customer_id": ctx["user_id"]}
    if site_id:
        query["site_id"] = site_id
    docs = await receiving_records.find(query).sort("created_at", -1).to_list(500)
    return {"records": [_serialize_receiving_record(doc) for doc in docs]}


@router.post("/receiving-records")
async def create_receiving_record(body: CustomerReceivingRecordBody, ctx: dict = Depends(customer_only)):
    site = await customer_sites.find_one({"_id": await _oid(body.site_id), "customer_id": ctx["user_id"]})
    if not site:
        raise HTTPException(422, "Saved site not found")
    order = None
    if body.order_id:
        order = await orders.find_one({"_id": await _oid(body.order_id), "customer_id": ctx["user_id"]})
        if not order:
            raise HTTPException(422, "Customer order not found")
        if order.get("site_id") and order.get("site_id") != body.site_id:
            raise HTTPException(422, "Order does not belong to this saved site")
        if order.get("grade") != body.grade:
            raise HTTPException(422, "Receiving grade must match the linked order")
    recorded_times = [body.arrival_time, body.unloading_start_time, body.unloading_end_time]
    present_times = [value for value in recorded_times if value]
    if len(present_times) > 1 and present_times != sorted(present_times):
        raise HTTPException(422, "Receiving times must be in chronological order")
    if body.sample_cast_date and body.sample_cast_date > datetime.now(timezone.utc).date():
        raise HTTPException(422, "Sample casting date cannot be in the future")
    allowed_checks = {"challan", "tm", "seal", "time", "visual", "access"}
    checklist = {key: bool(value) for key, value in body.checklist.items() if key in allowed_checks}
    cube_ids = [value.strip() for value in body.cube_sample_ids if value.strip()]
    if len(cube_ids) != len(set(value.lower() for value in cube_ids)):
        raise HTTPException(422, "Cube sample IDs must be unique within this record")
    now = datetime.now(timezone.utc)
    doc = {
        **body.model_dump(mode="json"),
        "cube_sample_ids": cube_ids,
        "checklist": checklist,
        "customer_id": ctx["user_id"],
        "site_name": site.get("name"),
        "site_address": site.get("address"),
        "order_number": order.get("order_number") if order else None,
        "cube_7d_date": (body.sample_cast_date + timedelta(days=7)).isoformat() if body.sample_cast_date else None,
        "cube_28d_date": (body.sample_cast_date + timedelta(days=28)).isoformat() if body.sample_cast_date else None,
        "record_type": "CUSTOMER_OBSERVATION",
        "created_at": now,
        "updated_at": now,
    }
    result = await receiving_records.insert_one(doc)
    doc["_id"] = result.inserted_id
    await write_audit(ctx["user_id"], "receiving_record.create", "receiving_record", str(result.inserted_id), {"site_id": body.site_id, "order_id": body.order_id})
    return {"record": _serialize_receiving_record(doc)}


@router.patch("/receiving-records/{record_id}/cube-results")
async def record_cube_test_result(
    record_id: str,
    body: CustomerCubeTestResultBody,
    ctx: dict = Depends(customer_only),
):
    record = await receiving_records.find_one({"_id": await _oid(record_id), "customer_id": ctx["user_id"]})
    if not record:
        raise HTTPException(404, "Receiving record not found")
    samples = {str(value).lower(): str(value) for value in record.get("cube_sample_ids") or []}
    sample_key = body.sample_id.strip().lower()
    if sample_key not in samples:
        raise HTTPException(422, "Cube sample ID is not part of this receiving record")
    if body.tested_on > datetime.now(timezone.utc).date():
        raise HTTPException(422, "Test date cannot be in the future")
    cast_value = record.get("sample_cast_date")
    cast_date = datetime.fromisoformat(str(cast_value)).date() if cast_value else None
    if cast_date and body.tested_on < cast_date:
        raise HTTPException(422, "Test date cannot be before the sample casting date")

    result = {
        **body.model_dump(mode="json"),
        "sample_id": samples[sample_key],
        "recorded_at": datetime.now(timezone.utc),
        "recorded_by": ctx["user_id"],
        "record_type": "CUSTOMER_RECORDED_LAB_RESULT",
        "acceptance_status": None,
    }
    existing = record.get("cube_test_results") or []
    updated = [
        item for item in existing
        if not (str(item.get("sample_id") or "").lower() == sample_key and int(item.get("age_days") or 0) == body.age_days)
    ]
    updated.append(result)
    now = datetime.now(timezone.utc)
    await receiving_records.update_one(
        {"_id": record["_id"], "customer_id": ctx["user_id"]},
        {"$set": {"cube_test_results": updated, "updated_at": now}},
    )
    record["cube_test_results"] = updated
    record["updated_at"] = now
    await write_audit(
        ctx["user_id"], "receiving_record.cube_result", "receiving_record", record_id,
        {"sample_id": samples[sample_key], "age_days": body.age_days, "result_mpa": body.result_mpa},
    )
    return {
        "record": _serialize_receiving_record(record),
        "disclaimer": "Recorded result only. Acceptance must follow the approved project specification and authorised engineer or laboratory assessment.",
    }


@router.delete("/receiving-records/{record_id}")
async def delete_receiving_record(record_id: str, ctx: dict = Depends(customer_only)):
    result = await receiving_records.delete_one({"_id": await _oid(record_id), "customer_id": ctx["user_id"]})
    if result.deleted_count != 1:
        raise HTTPException(404, "Receiving record not found")
    await write_audit(ctx["user_id"], "receiving_record.delete", "receiving_record", record_id, {})
    return {"status": "deleted"}


def _serialize_pour_plan(doc: dict) -> dict:
    row = {**doc, "id": str(doc["_id"])}
    row.pop("_id", None)
    for key, value in list(row.items()):
        if isinstance(value, ObjectId):
            row[key] = str(value)
        elif hasattr(value, "isoformat"):
            row[key] = value.isoformat()
    return row


@router.get("/pour-plans")
async def list_pour_plans(site_id: str | None = Query(default=None), ctx: dict = Depends(customer_only)):
    query: dict = {"customer_id": ctx["user_id"]}
    if site_id:
        query["site_id"] = site_id
    docs = await pour_plans.find(query).sort([("pour_date", -1), ("created_at", -1)]).to_list(500)
    return {"plans": [_serialize_pour_plan(doc) for doc in docs]}


@router.post("/pour-plans")
async def create_pour_plan(body: CustomerPourPlanBody, ctx: dict = Depends(customer_only)):
    site = await customer_sites.find_one({"_id": await _oid(body.site_id), "customer_id": ctx["user_id"]})
    if not site:
        raise HTTPException(422, "Saved site not found")
    total = float(body.total_quantity_m3)
    capacity = float(body.mixer_capacity_m3)
    loads_count = math.ceil(total / capacity)
    if loads_count > 500:
        raise HTTPException(422, "Pour plan exceeds the maximum of 500 mixer loads")
    if body.pour_date < datetime.now(timezone.utc).date():
        raise HTTPException(422, "Pour date cannot be in the past")
    start_at = datetime.combine(body.pour_date, time.fromisoformat(body.start_time))
    quantities = [round(min(capacity, total - (index * capacity)), 2) for index in range(loads_count)]
    loads = [{
        "load_number": index + 1,
        "quantity_m3": quantity,
        "suggested_arrival": (start_at + timedelta(minutes=index * body.unload_minutes)).strftime("%H:%M"),
    } for index, quantity in enumerate(quantities)]
    estimated_end = start_at + timedelta(minutes=loads_count * body.unload_minutes)
    now = datetime.now(timezone.utc)
    doc = {
        **body.model_dump(mode="json"),
        "customer_id": ctx["user_id"],
        "site_name": site.get("name"),
        "site_address": site.get("address"),
        "loads_count": loads_count,
        "loads": loads,
        "estimated_end_time": estimated_end.strftime("%H:%M"),
        "status": "PLANNED",
        "created_at": now,
        "updated_at": now,
    }
    result = await pour_plans.insert_one(doc)
    doc["_id"] = result.inserted_id
    await write_audit(ctx["user_id"], "pour_plan.create", "pour_plan", str(result.inserted_id), {"site_id": body.site_id, "loads": loads_count})
    return {"plan": _serialize_pour_plan(doc)}


@router.delete("/pour-plans/{plan_id}")
async def delete_pour_plan(plan_id: str, ctx: dict = Depends(customer_only)):
    result = await pour_plans.delete_one({"_id": await _oid(plan_id), "customer_id": ctx["user_id"]})
    if result.deleted_count != 1:
        raise HTTPException(404, "Pour plan not found")
    await write_audit(ctx["user_id"], "pour_plan.delete", "pour_plan", plan_id, {})
    return {"status": "deleted"}


async def _sync_customer_verified_name(uid: str, kyc: dict) -> bool:
    """Fetch the DigiLocker-verified name and persist it to the customer profile.

    Provider success (VERIFIED) is authoritative and is never rolled back by a
    name-fetch failure. If the verified name cannot be fetched right now we flag
    the profile for a safe retry instead of fabricating a name. Returns True when
    the verified name was persisted, False when it was deferred for retry.
    """
    session_id = kyc.get("provider_session_id")
    if not session_id:
        return False
    now = datetime.now(timezone.utc)
    try:
        profile = await get_digilocker_user_profile(session_id)
    except (DigiLockerConfigurationError, DigiLockerProviderError):
        # Do not expose or log the raw provider payload / KYC data.
        logger.warning("Customer KYC verified-name sync deferred (user=%s)", uid)
        await kyc_profiles.update_one(
            {"_id": kyc["_id"]},
            {"$set": {"name_sync_pending": True, "updated_at": now}},
        )
        return False

    verified_name = profile["name"]  # already trimmed/normalized in the service
    await users.update_one(
        {"_id": await _oid(uid)},
        {"$set": {"name": verified_name, "updated_at": now}},
    )
    await kyc_profiles.update_one(
        {"_id": kyc["_id"]},
        {"$set": {"kyc_name": verified_name, "name_sync_pending": False, "updated_at": now}},
    )
    await write_audit(uid, "kyc.name_synced", "user", uid, {"source": "DIGILOCKER"})
    return True


@router.get("/kyc")
async def get_kyc(ctx: dict = Depends(customer_only)):
    uid = ctx["user_id"]
    kyc = await kyc_profiles.find_one({"user_id": uid, "purpose": "CUSTOMER"})
    if not kyc:
        return {"status": "NOT_STARTED"}

    status = kyc.get("status", "NOT_STARTED")
    session_id = kyc.get("provider_session_id")

    # Reconciliation: KYC is genuinely VERIFIED but the verified name could not
    # be persisted earlier. Retry the profile sync without touching KYC status.
    if status == "VERIFIED" and kyc.get("name_sync_pending") and session_id:
        await _sync_customer_verified_name(uid, kyc)
        return {"status": status, "provider": kyc.get("provider", "DIGILOCKER")}

    if status == "IN_PROGRESS" and session_id:
        try:
            provider = await get_digilocker_session_status(session_id)
        except (DigiLockerConfigurationError, DigiLockerProviderError):
            # Never convert a transient provider/configuration problem into a
            # successful or rejected KYC decision.
            return {"status": "IN_PROGRESS", "provider": "DIGILOCKER", "refresh_failed": True}

        if provider["status"] == "SUCCEEDED":
            # Customer KYC: a provider-confirmed successful DigiLocker session is
            # authoritative and transitions the customer straight to VERIFIED.
            # Authority retains visibility/audit but is not a routine blocker.
            status = "VERIFIED"
            now = datetime.now(timezone.utc)
            result = await kyc_profiles.update_one(
                {"_id": kyc["_id"], "status": "IN_PROGRESS"},
                {"$set": {
                    "status": status,
                    "provider_status": provider["provider_status"],
                    "provider_transaction_id": provider["transaction_id"],
                    "consent_verified_at": now,
                    "verified_at": now,
                    "verified_by": "DIGILOCKER_AUTO",
                    "name_sync_pending": True,
                    "updated_at": now,
                }},
            )
            if result.modified_count == 1:
                await write_audit(uid, "kyc.digilocker.verified", "kyc_profile", str(kyc["_id"]), {"purpose": "CUSTOMER"})
                fresh = await kyc_profiles.find_one({"_id": kyc["_id"]})
                await _sync_customer_verified_name(uid, fresh or kyc)
        elif provider["status"] == "FAILED":
            status = "REQUIRES_REVERIFICATION"
            await kyc_profiles.update_one(
                {"_id": kyc["_id"], "status": "IN_PROGRESS"},
                {"$set": {
                    "status": status,
                    "provider_status": provider["provider_status"],
                    "provider_transaction_id": provider["transaction_id"],
                    "updated_at": datetime.now(timezone.utc),
                }},
            )
            await write_audit(uid, "kyc.digilocker.failed", "kyc_profile", str(kyc["_id"]), {"purpose": "CUSTOMER"})

    return {"status": status, "provider": "DIGILOCKER"}


@router.post("/kyc/start")
async def start_kyc(ctx: dict = Depends(customer_only)):
    uid = ctx["user_id"]
    existing = await kyc_profiles.find_one({"user_id": uid, "purpose": "CUSTOMER"})
    if existing and existing.get("status") == "VERIFIED":
        raise HTTPException(409, "KYC already verified")
    if existing and existing.get("status") == "PENDING":
        raise HTTPException(409, "KYC is awaiting Authority review")

    try:
        session = await initiate_digilocker_session()
    except DigiLockerConfigurationError as exc:
        raise HTTPException(503, str(exc)) from exc
    except DigiLockerProviderError as exc:
        raise HTTPException(502, str(exc)) from exc

    now = datetime.now(timezone.utc)
    await kyc_profiles.update_one(
        {"user_id": uid, "purpose": "CUSTOMER"},
        {"$set": {
            "status": "IN_PROGRESS",
            "provider": "DIGILOCKER",
            "provider_session_id": session["session_id"],
            "provider_transaction_id": session["transaction_id"],
            "reject_reason": None,
            "updated_at": now,
        }, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    await write_audit(uid, "kyc.digilocker.start", "kyc_profile", uid, {"purpose": "CUSTOMER"})
    return {
        "status": "IN_PROGRESS",
        "provider": "DIGILOCKER",
        "authorization_url": session["authorization_url"],
    }


async def _oid(value: str):
    try:
        return ObjectId(value)
    except Exception:
        return value


@router.post("/orders")
async def create_order(body: CreateOrderBody, ctx: dict = Depends(customer_only)):
    uid = ctx["user_id"]
    if not body.save_draft:
        kyc = await kyc_profiles.find_one({"user_id": uid, "purpose": "CUSTOMER"})
        if (kyc or {}).get("status") != "VERIFIED":
            raise HTTPException(403, "KYC_REQUIRED")
    site = None
    if body.site_id:
        site = await customer_sites.find_one({"_id": await _oid(body.site_id), "customer_id": uid})
        if not site:
            raise HTTPException(422, "Saved site not found")
    plant = await plants.find_one({"_id": await _oid(body.plant_id)})
    if not plant or plant.get("status") != "active" or not plant.get("verified"):
        raise HTTPException(404, "Plant not available")
    if body.grade not in plant.get("grades", []):
        raise HTTPException(422, "Selected grade not offered by this plant")

    quote = None
    if body.quotation_id:
        quote = await quotations.find_one({
            "_id": await _oid(body.quotation_id),
            "customer_id": uid,
            "plant_id": str(plant["_id"]),
            "status": "ACCEPTED",
        })
        if not quote:
            raise HTTPException(409, "Accepted quotation is not available for order creation")
        if quote.get("order_id"):
            raise HTTPException(409, "An order already exists for this quotation")
        if quote.get("grade") != body.grade or float(quote.get("quantity_m3") or 0) != float(body.quantity):
            raise HTTPException(422, "Order grade and quantity must match the accepted quotation")

    seq = await next_sequence("order_number")
    order_number = f"RMC-{1000 + seq}"
    now = datetime.now(timezone.utc)
    status = DRAFT if body.save_draft else PENDING
    doc = {
        "order_number": order_number, "customer_id": uid, "customer_name": ctx["user"].get("name"),
        "plant_id": str(plant["_id"]), "plant_name": plant.get("name"), "grade": body.grade,
        "quantity": body.quantity, "site_id": body.site_id, "site_name": body.site_name, "site_address": body.site_address,
        "lat": body.lat, "lng": body.lng, "delivery_date": body.delivery_date,
        "delivery_time": body.delivery_time, "delivery_mode": body.delivery_mode,
        "contact_person": body.contact_person, "contact_mobile": body.contact_mobile, "notes": body.notes,
        "quotation_id": body.quotation_id, "quotation_number": quote.get("quotation_number") if quote else None,
        "quoted_total": quote.get("total") if quote else None,
        "status": status, "payment_status": "UNPAID", "created_at": now, "updated_at": now,
    }
    try:
        res = await orders.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "An order already exists for this quotation")
    oid = str(res.inserted_id)
    if quote:
        await quotations.update_one(
            {"_id": quote["_id"], "status": "ACCEPTED", "order_id": {"$exists": False}},
            {"$set": {"status": "ORDER_CREATED", "order_id": oid, "order_number": order_number, "updated_at": now}},
        )
    await order_status_history.insert_one(
        {"order_id": oid, "from_status": None, "to_status": status, "actor_id": uid,
         "note": "Order created", "created_at": now}
    )
    await write_audit(uid, "order.create", "order", oid, {"status": status, "delivery_mode": body.delivery_mode, "quotation_id": body.quotation_id})
    if status == PENDING and plant.get("owner_id"):
        await record_notification(
            plant["owner_id"], "new_order", f"New order {order_number}",
            f"{ctx['user'].get('name')} ordered {body.quantity} m³ of {body.grade}.",
        )
    doc["_id"] = res.inserted_id
    return {"id": oid, "order": _serialize_order(doc)}


@router.get("/orders/{order_id}")
async def order_detail(order_id: str, ctx: dict = Depends(customer_only)):
    order = await orders.find_one({"_id": await _oid(order_id), "customer_id": ctx["user_id"]})
    if not order:
        raise HTTPException(404, "Order not found")
    history = await order_status_history.find({"order_id": order_id}).sort("created_at", 1).to_list(200)
    loads = await order_loads.find({"order_id": order_id}).sort("load_number", 1).to_list(500)
    pods = await proof_of_delivery.find({"order_id": order_id}).sort("created_at", 1).to_list(500)
    pod_rows = [_serialize_pod(p) for p in pods]
    return {
        "order": _serialize_order(order), "contact_person": order.get("contact_person"),
        "contact_mobile": order.get("contact_mobile"), "notes": order.get("notes"),
        "loads": [_serialize_load(x) for x in loads], "pods": pod_rows,
        "pod": pod_rows[-1] if pod_rows else None,
        "history": [
            {"from": h.get("from_status"), "to": h.get("to_status"), "note": h.get("note"),
             "at": h.get("created_at").isoformat() if h.get("created_at") else None}
            for h in history
        ],
    }


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, ctx: dict = Depends(customer_only)):
    order = await orders.find_one({"_id": await _oid(order_id), "customer_id": ctx["user_id"]})
    if not order:
        raise HTTPException(404, "Order not found")
    active_loads = await order_loads.count_documents(
        {"order_id": order_id, "status": {"$nin": ["PLANNED", "ASSIGNED", "CANCELLED"]}}
    )
    if active_loads:
        raise HTTPException(409, "Order cannot be cancelled after a delivery load is prepared")
    plant = await plants.find_one({"_id": await _oid(order["plant_id"])})
    notify = [plant["owner_id"]] if plant and plant.get("owner_id") else []
    await transition_order(order_id, CANCELLED, ctx["user_id"], note="Cancelled by customer",
                           notify_user_ids=notify, event="order_cancelled")
    await order_loads.update_many(
        {"order_id": order_id, "status": {"$in": ["PLANNED", "ASSIGNED"]}},
        {"$set": {"status": "CANCELLED", "cancelled_at": datetime.now(timezone.utc)}},
    )
    return {"status": CANCELLED}


@router.get("/plants/{plant_id}")
async def plant_detail(plant_id: str, ctx: dict = Depends(customer_only)):
    plant = await plants.find_one({"_id": await _oid(plant_id)})
    if not plant or str(plant.get("status") or "active").lower() in CUSTOMER_HIDDEN_PLANT_STATUSES:
        raise HTTPException(404, "Plant not found")
    return _serialize_plant(plant)


ACTIVE_TRACK = {"DISPATCHED", "EN_ROUTE", "AT_SITE", "UNLOADING", "POD_PENDING"}


@router.get("/orders/{order_id}/tracking")
async def track_order(order_id: str, ctx: dict = Depends(customer_only)):
    order = await orders.find_one({"_id": await _oid(order_id), "customer_id": ctx["user_id"]})
    if not order:
        raise HTTPException(404, "Order not found")
    loads = await order_loads.find({"order_id": order_id}).sort("load_number", 1).to_list(500)
    active_loads = [x for x in loads if x.get("status") in ACTIVE_LOAD_STATUSES]
    tracked_loads = []
    for load in active_loads:
        latest = await vehicle_locations.find({"load_id": str(load["_id"])}).sort("created_at", -1).to_list(1)
        location = None
        route_info = None
        if latest:
            location = {"lat": latest[0]["lat"], "lng": latest[0]["lng"],
                        "at": latest[0]["created_at"].isoformat() if latest[0].get("created_at") else None}
            if order.get("lat") is not None and order.get("lng") is not None:
                from routers.maps import compute_route
                route_info = await compute_route(location["lat"], location["lng"], order["lat"], order["lng"])
        tracked_loads.append({**_serialize_load(load), "location": location, "route": route_info})

    active = bool(active_loads) or order.get("status") in ACTIVE_TRACK
    latest_order = await vehicle_locations.find({"order_id": order_id}).sort("created_at", -1).to_list(1) if active else []
    loc = None
    route_info = None
    if latest_order:
        loc = {"lat": latest_order[0]["lat"], "lng": latest_order[0]["lng"],
               "at": latest_order[0]["created_at"].isoformat() if latest_order[0].get("created_at") else None}
        if order.get("lat") is not None and order.get("lng") is not None:
            from routers.maps import compute_route
            route_info = await compute_route(loc["lat"], loc["lng"], order["lat"], order["lng"])
    return {
        "active": active, "status": order.get("status"), "tm_number": order.get("tm_number"),
        "driver_name": order.get("driver_name"), "driver_mobile": order.get("driver_mobile"),
        "destination": {"lat": order.get("lat"), "lng": order.get("lng"),
                        "site_name": order.get("site_name"), "address": order.get("site_address")},
        "location": loc, "route": route_info, "active_loads": tracked_loads,
        "loads": [_serialize_load(x) for x in loads],
    }


@router.get("/orders/{order_id}/challan")
async def customer_challan(order_id: str, ctx: dict = Depends(customer_only)):
    order = await orders.find_one({"_id": await _oid(order_id), "customer_id": ctx["user_id"]})
    if not order:
        raise HTTPException(404, "Order not found")
    docs = await challans.find({"order_id": order_id}).sort("created_at", -1).to_list(500)
    if not docs:
        raise HTTPException(404, "Challan not available yet")
    rows = [_serialize_challan(d) for d in docs]
    return {"challan": rows[0], "challans": rows}
