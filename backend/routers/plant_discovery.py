"""Authority review for Google-discovered RMC plant listing requests."""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from database import plant_listing_requests, plants
from notifications import record_notification
from roles import Role
from security import require_role

router = APIRouter(prefix="/api/plant-discovery", tags=["plant-discovery"])
reviewer_only = require_role(Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value)


class RejectListingBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


def _oid(value: str):
    try:
        return ObjectId(value)
    except Exception:
        return value


def _serialize(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "google_place_id": doc.get("google_place_id"),
        "name": doc.get("name"),
        "address": doc.get("address"),
        "city": doc.get("city"),
        "district": doc.get("district"),
        "lat": doc.get("lat"),
        "lng": doc.get("lng"),
        "contact_phone": doc.get("contact_phone"),
        "google_maps_uri": doc.get("google_maps_uri"),
        "business_status": doc.get("business_status"),
        "status": doc.get("status"),
        "requested_by": doc.get("requested_by"),
        "requested_role": doc.get("requested_role"),
        "claim_requested": bool(doc.get("claim_requested")),
        "plant_id": doc.get("plant_id"),
        "reject_reason": doc.get("reject_reason"),
        "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
    }


@router.get("/requests")
async def list_requests(ctx: dict = Depends(reviewer_only)):
    docs = await plant_listing_requests.find({"status": "PENDING"}).sort("updated_at", -1).to_list(500)
    return {"requests": [_serialize(d) for d in docs]}


@router.post("/requests/{request_id}/approve")
async def approve_listing(request_id: str, ctx: dict = Depends(reviewer_only)):
    req = await plant_listing_requests.find_one({"_id": _oid(request_id)})
    if not req:
        raise HTTPException(404, "Plant listing request not found")
    if req.get("status") == "APPROVED" and req.get("plant_id"):
        return {"status": "APPROVED", "plant_id": req.get("plant_id")}
    if req.get("status") != "PENDING":
        raise HTTPException(409, "Only pending plant listings can be approved")

    place_id = req.get("google_place_id")
    existing = await plants.find_one({"google_place_id": place_id})
    now = datetime.now(timezone.utc)
    if existing:
        plant_id = str(existing["_id"])
    else:
        # Google confirms the business/location, but TrackMyRMC still requires
        # operational setup (grades/rates/owner details) before order placement.
        plant_doc = {
            "name": req.get("name"),
            "city": req.get("city"),
            "district": req.get("district"),
            "address": req.get("address"),
            "lat": req.get("lat"),
            "lng": req.get("lng"),
            "grades": [],
            "contact_phone": req.get("contact_phone"),
            "service_area_km": 0,
            "status": "pending_setup",
            "verified": True,
            "google_place_id": place_id,
            "google_maps_uri": req.get("google_maps_uri"),
            "source": "google_places",
            "approved_by": ctx["user_id"],
            "approved_at": now,
            "created_at": now,
            "updated_at": now,
        }
        if req.get("claim_requested") and req.get("requested_role") == Role.PLANT_OWNER.value:
            plant_doc["owner_id"] = req.get("requested_by")
        try:
            result = await plants.insert_one(plant_doc)
            plant_id = str(result.inserted_id)
        except DuplicateKeyError:
            existing = await plants.find_one({"google_place_id": place_id})
            if not existing:
                raise HTTPException(409, "This Google plant is already registered")
            plant_id = str(existing["_id"])

    await plant_listing_requests.update_one(
        {"_id": req["_id"]},
        {"$set": {
            "status": "APPROVED",
            "plant_id": plant_id,
            "reviewed_by": ctx["user_id"],
            "reviewed_at": now,
            "updated_at": now,
        }},
    )
    await write_audit(
        ctx["user_id"],
        "plant_listing.approve",
        "plant_listing_request",
        request_id,
        {"plant_id": plant_id, "google_place_id": place_id},
    )
    if req.get("requested_by"):
        await record_notification(
            req["requested_by"],
            "plant_listing",
            "RMC plant listing approved",
            f"{req.get('name') or 'The plant'} is now listed in TrackMyRMC. Ordering stays disabled until plant setup is completed.",
        )
    return {"status": "APPROVED", "plant_id": plant_id}


@router.post("/requests/{request_id}/reject")
async def reject_listing(
    request_id: str,
    body: RejectListingBody,
    ctx: dict = Depends(reviewer_only),
):
    req = await plant_listing_requests.find_one({"_id": _oid(request_id)})
    if not req:
        raise HTTPException(404, "Plant listing request not found")
    if req.get("status") != "PENDING":
        raise HTTPException(409, "Only pending plant listings can be rejected")
    now = datetime.now(timezone.utc)
    reason = (body.reason or "Not approved by Authority").strip()
    await plant_listing_requests.update_one(
        {"_id": req["_id"]},
        {"$set": {
            "status": "REJECTED",
            "reject_reason": reason,
            "reviewed_by": ctx["user_id"],
            "reviewed_at": now,
            "updated_at": now,
        }},
    )
    await write_audit(
        ctx["user_id"],
        "plant_listing.reject",
        "plant_listing_request",
        request_id,
        {"reason": reason},
    )
    if req.get("requested_by"):
        await record_notification(
            req["requested_by"],
            "plant_listing",
            "RMC plant listing not approved",
            reason,
        )
    return {"status": "REJECTED"}
