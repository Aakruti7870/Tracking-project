"""Authority review for Google-discovered RMC plant listing requests."""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from database import plant_listing_requests, plants, users
from notifications import record_notification
from models import User
from roles import Role
from security import identifier_key, normalize_identifier, require_role

router = APIRouter(prefix="/api/plant-discovery", tags=["plant-discovery"])
reviewer_only = require_role(Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value)


class RejectListingBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class OwnerAssignmentBody(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=32)


async def _provision_plant_owner(body: OwnerAssignmentBody) -> dict:
    """Create or reuse a Plant Owner without converting another role silently."""
    identifiers: list[tuple[str, str]] = []
    if body.email and body.email.strip():
        channel, value = normalize_identifier(body.email)
        if channel != "email":
            raise HTTPException(422, "Enter a valid owner email address")
        identifiers.append((channel, value))
    if body.phone and body.phone.strip():
        channel, value = normalize_identifier(body.phone)
        if channel != "sms":
            raise HTTPException(422, "Enter a valid owner mobile number")
        identifiers.append((channel, value))
    if not identifiers:
        raise HTTPException(422, "Owner email or mobile number is required")

    keys = [identifier_key(value) for _, value in identifiers]
    matches = await users.find({"identifier_keys": {"$in": keys}}).to_list(2)
    if len(matches) > 1:
        raise HTTPException(409, "Owner email and mobile belong to different accounts")

    email = next((value for channel, value in identifiers if channel == "email"), None)
    phone = next((value for channel, value in identifiers if channel == "sms"), None)
    if matches:
        owner = matches[0]
        if owner.get("primary_role") != Role.PLANT_OWNER.value:
            raise HTTPException(409, "This email or mobile already belongs to another account")
        await users.update_one(
            {"_id": owner["_id"]},
            {"$set": {"name": body.name.strip(), "email": email or owner.get("email"), "phone": phone or owner.get("phone")},
             "$addToSet": {"identifier_keys": {"$each": keys}, "roles": Role.PLANT_OWNER.value}},
        )
        return {"id": str(owner["_id"]), "created": False}

    owner = User(
        name=body.name.strip(),
        email=email,
        phone=phone,
        identifier_keys=keys,
        roles=[Role.PLANT_OWNER.value],
        primary_role=Role.PLANT_OWNER.value,
    )
    try:
        result = await users.insert_one(owner.to_mongo())
    except DuplicateKeyError:
        raise HTTPException(409, "Owner account was created concurrently; retry assignment")
    return {"id": str(result.inserted_id), "created": True}


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
async def approve_listing(
    request_id: str,
    body: OwnerAssignmentBody | None = None,
    ctx: dict = Depends(reviewer_only),
):
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
    owner = await _provision_plant_owner(body) if body else None
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
        if owner:
            plant_doc["owner_id"] = owner["id"]
        elif req.get("claim_requested") and req.get("requested_role") == Role.PLANT_OWNER.value:
            plant_doc["owner_id"] = req.get("requested_by")
        try:
            result = await plants.insert_one(plant_doc)
            plant_id = str(result.inserted_id)
        except DuplicateKeyError:
            existing = await plants.find_one({"google_place_id": place_id})
            if not existing:
                raise HTTPException(409, "This Google plant is already registered")
            plant_id = str(existing["_id"])

    if existing and owner:
        current_owner = existing.get("owner_id")
        if current_owner and current_owner != owner["id"]:
            raise HTTPException(409, "Plant already has a different owner")
        await plants.update_one({"_id": existing["_id"]}, {"$set": {"owner_id": owner["id"], "updated_at": now}})

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
        {"plant_id": plant_id, "google_place_id": place_id, "owner_id": owner["id"] if owner else None},
    )
    if owner:
        await write_audit(
            ctx["user_id"], "plant_owner.assign", "plant", plant_id,
            {"owner_id": owner["id"], "account_created": owner["created"]},
        )
        await record_notification(
            owner["id"], "plant_owner", "Plant Owner access enabled",
            f"You can now sign in with OTP and manage {req.get('name') or 'your RMC plant'}.",
        )
    if req.get("requested_by"):
        await record_notification(
            req["requested_by"],
            "plant_listing",
            "RMC plant listing approved",
            f"{req.get('name') or 'The plant'} is now listed in TrackMyRMC. Ordering stays disabled until plant setup is completed.",
        )
    return {"status": "APPROVED", "plant_id": plant_id, "owner_id": owner["id"] if owner else None}


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
