"""Customer role endpoints (server-side authorized to the customer role)."""
from datetime import datetime, timezone
import math

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.errors import DuplicateKeyError
from pydantic import BaseModel, Field

from audit import write_audit
from database import (
    challans,
    kyc_profiles,
    notifications,
    order_loads,
    order_status_history,
    orders,
    plants,
    plant_promotions,
    proof_of_delivery,
    quotation_requests,
    quotations,
    rate_cards,
    vehicle_locations,
    next_sequence,
)
from models import CreateOrderBody
from notifications import record_notification
from order_service import CANCELLED, DRAFT, PENDING, transition_order
from roles import Role
from security import require_role
from services.digilocker import (
    DigiLockerConfigurationError,
    DigiLockerProviderError,
    get_digilocker_session_status,
    initiate_digilocker_session,
)

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
        "plant_id": doc.get("plant_id"), "plant_name": doc.get("plant_name"),
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


class QuotationRequestBody(BaseModel):
    plant_id: str
    grade: str = Field(pattern=r"^M(?:10|15|20|25|30|35|40|45|50|55|60)(?:[-_ ]?PILE)?$")
    quantity: float = Field(gt=0, le=100000)
    site_name: str = Field(min_length=1, max_length=180)
    site_address: str = Field(min_length=5, max_length=1000)
    estimated_total: float | None = Field(default=None, ge=0, le=1_000_000_000)
    pump_required: bool = False


@router.post("/quotation-requests")
async def request_quotation(body: QuotationRequestBody, ctx: dict = Depends(customer_only)):
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


@router.get("/kyc")
async def get_kyc(ctx: dict = Depends(customer_only)):
    uid = ctx["user_id"]
    kyc = await kyc_profiles.find_one({"user_id": uid, "purpose": "CUSTOMER"})
    if not kyc:
        return {"status": "NOT_STARTED"}

    status = kyc.get("status", "NOT_STARTED")
    session_id = kyc.get("provider_session_id")
    if status == "IN_PROGRESS" and session_id:
        try:
            provider = await get_digilocker_session_status(session_id)
        except (DigiLockerConfigurationError, DigiLockerProviderError):
            # Never convert a transient provider/configuration problem into a
            # successful or rejected KYC decision.
            return {"status": "IN_PROGRESS", "provider": "DIGILOCKER", "refresh_failed": True}

        if provider["status"] == "SUCCEEDED":
            status = "PENDING"
            await kyc_profiles.update_one(
                {"_id": kyc["_id"], "status": "IN_PROGRESS"},
                {"$set": {
                    "status": status,
                    "provider_status": provider["provider_status"],
                    "provider_transaction_id": provider["transaction_id"],
                    "consent_verified_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }},
            )
            await write_audit(uid, "kyc.digilocker.completed", "kyc_profile", str(kyc["_id"]), {"purpose": "CUSTOMER"})
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
        "quantity": body.quantity, "site_name": body.site_name, "site_address": body.site_address,
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
