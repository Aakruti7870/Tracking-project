"""Authority review for Google-discovered and self-onboarded RMC plants."""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from database import plant_listing_requests, plants, users
from notifications import record_notification
from routers.maps import _fetch_place_detail, _key
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
            {
                "$set": {
                    "name": body.name.strip(),
                    "email": email or owner.get("email"),
                    "phone": phone or owner.get("phone"),
                },
                "$addToSet": {
                    "identifier_keys": {"$each": keys},
                    "roles": Role.PLANT_OWNER.value,
                },
            },
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
        "request_number": doc.get("request_number"),
        "source": doc.get("source"),
        "google_place_id": doc.get("google_place_id"),
        "name": doc.get("name"),
        "address": doc.get("address"),
        "city": doc.get("city"),
        "taluka": doc.get("taluka"),
        "district": doc.get("district"),
        "state": doc.get("state"),
        "lat": doc.get("lat"),
        "lng": doc.get("lng"),
        "contact_phone": doc.get("contact_phone"),
        "google_maps_uri": doc.get("google_maps_uri"),
        "business_status": doc.get("business_status"),
        "status": doc.get("status"),
        "requested_by": doc.get("requested_by"),
        "requested_role": doc.get("requested_role"),
        "claim_requested": bool(doc.get("claim_requested")),
        "applicant_owner_name": doc.get("applicant_owner_name"),
        "applicant_email": doc.get("applicant_email"),
        "applicant_mobile": doc.get("applicant_mobile"),
        "plant_id": doc.get("plant_id"),
        "reject_reason": doc.get("reject_reason"),
        "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
    }


@router.get("/requests")
async def list_requests(ctx: dict = Depends(reviewer_only)):
    del ctx
    docs = await plant_listing_requests.find({"status": "PENDING"}).sort("updated_at", -1).to_list(500)
    return {"requests": [_serialize(d) for d in docs]}


class BulkGoogleImportBody(BaseModel):
    place_ids: list[str] = Field(min_length=1, max_length=20)


class BulkApproveBody(BaseModel):
    request_ids: list[str] = Field(min_length=1, max_length=50)


@router.post("/requests/bulk-import")
async def bulk_import_google_places(body: BulkGoogleImportBody, ctx: dict = Depends(reviewer_only)):
    """Import selected Google places into Pending Review, never directly into plants."""
    if not _key():
        raise HTTPException(409, "Maps NOT_CONFIGURED")
    place_ids = list(dict.fromkeys(value.strip() for value in body.place_ids if value.strip()))
    imported = []
    skipped = []
    now = datetime.now(timezone.utc)
    for place_id in place_ids:
        if await plants.find_one({"google_place_id": place_id}):
            skipped.append({"place_id": place_id, "reason": "ALREADY_REGISTERED"})
            continue
        existing = await plant_listing_requests.find_one({"google_place_id": place_id})
        if existing and existing.get("status") in ("PENDING", "APPROVED"):
            skipped.append({"place_id": place_id, "reason": existing.get("status")})
            continue
        detail = await _fetch_place_detail(place_id)
        payload = {
            "google_place_id": place_id,
            "name": detail.get("name"),
            "address": detail.get("address"),
            "city": detail.get("city"),
            "taluka": detail.get("taluka"),
            "district": detail.get("district"),
            "state": detail.get("state"),
            "lat": detail.get("lat"),
            "lng": detail.get("lng"),
            "contact_phone": detail.get("contact_phone"),
            "google_maps_uri": detail.get("google_maps_uri"),
            "business_status": detail.get("business_status"),
            "source": "google_places_authority_bulk",
            "status": "PENDING",
            "requested_by": ctx["user_id"],
            "requested_role": ctx.get("role"),
            "claim_requested": False,
            "updated_at": now,
        }
        if existing:
            await plant_listing_requests.update_one({"_id": existing["_id"]}, {"$set": payload})
            request_id = str(existing["_id"])
        else:
            payload["created_at"] = now
            result = await plant_listing_requests.insert_one(payload)
            request_id = str(result.inserted_id)
        await write_audit(
            ctx["user_id"],
            "plant_listing.bulk_import",
            "plant_listing_request",
            request_id,
            {"google_place_id": place_id},
        )
        imported.append({"place_id": place_id, "request_id": request_id})
    return {"status": "PENDING_REVIEW", "imported": imported, "skipped": skipped}


@router.post("/requests/bulk-approve")
async def bulk_approve_listings(body: BulkApproveBody, ctx: dict = Depends(reviewer_only)):
    """Approve reviewed requests; self-onboarding carries its submitted owner details."""
    request_ids = list(dict.fromkeys(body.request_ids))
    approved = []
    skipped = []
    for request_id in request_ids:
        try:
            result = await approve_listing(request_id, None, ctx)
            approved.append({"request_id": request_id, "plant_id": result.get("plant_id")})
        except HTTPException as exc:
            skipped.append({"request_id": request_id, "reason": str(exc.detail)})
    return {"status": "COMPLETED", "approved": approved, "skipped": skipped}


def _submitted_owner(req: dict) -> OwnerAssignmentBody | None:
    if req.get("source") != "self_onboarding":
        return None
    name = str(req.get("applicant_owner_name") or "").strip()
    email = str(req.get("applicant_email") or "").strip() or None
    phone = str(req.get("applicant_mobile") or "").strip() or None
    if len(name) < 2 or not (email or phone):
        return None
    return OwnerAssignmentBody(name=name, email=email, phone=phone)


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

    if body is None:
        body = _submitted_owner(req)

    place_id = req.get("google_place_id")
    real_google_place = bool(place_id and not str(place_id).startswith("onboarding:"))
    existing = await plants.find_one({"google_place_id": place_id}) if real_google_place else None
    if existing and existing.get("owner_id") and body:
        raise HTTPException(409, "Plant already has an owner; use the controlled owner-replacement flow")

    if req.get("source") == "self_onboarding" and body is None:
        raise HTTPException(422, "Self-onboarding request is missing valid Plant Owner details")

    now = datetime.now(timezone.utc)
    owner = await _provision_plant_owner(body) if body else None
    if existing:
        plant_id = str(existing["_id"])
    else:
        plant_doc = {
            "name": req.get("name"),
            "city": req.get("city"),
            "taluka": req.get("taluka"),
            "district": req.get("district"),
            "state": req.get("state"),
            "address": req.get("address"),
            "lat": req.get("lat"),
            "lng": req.get("lng"),
            "grades": [],
            "contact_phone": req.get("contact_phone"),
            "service_area_km": 0,
            "status": "pending_setup",
            "verified": True,
            "google_maps_uri": req.get("google_maps_uri"),
            "source": "google_places" if real_google_place else "self_onboarding",
            "approved_by": ctx["user_id"],
            "approved_at": now,
            "created_at": now,
            "updated_at": now,
        }
        if real_google_place:
            plant_doc["google_place_id"] = place_id
        if owner:
            plant_doc["owner_id"] = owner["id"]
        elif req.get("claim_requested") and req.get("requested_role") == Role.PLANT_OWNER.value and req.get("requested_by"):
            plant_doc["owner_id"] = req.get("requested_by")
        try:
            result = await plants.insert_one(plant_doc)
            plant_id = str(result.inserted_id)
        except DuplicateKeyError:
            if not real_google_place:
                raise HTTPException(409, "Plant registration conflict; reload and retry")
            existing = await plants.find_one({"google_place_id": place_id})
            if not existing:
                raise HTTPException(409, "This Google plant is already registered")
            plant_id = str(existing["_id"])

    if existing and owner:
        current_owner = existing.get("owner_id")
        if current_owner and current_owner != owner["id"]:
            raise HTTPException(409, "Plant already has a different owner")
        await plants.update_one(
            {"_id": existing["_id"]},
            {"$set": {"owner_id": owner["id"], "updated_at": now}},
        )

    await plant_listing_requests.update_one(
        {"_id": req["_id"]},
        {
            "$set": {
                "status": "APPROVED",
                "plant_id": plant_id,
                "reviewed_by": ctx["user_id"],
                "reviewed_at": now,
                "updated_at": now,
            }
        },
    )
    await write_audit(
        ctx["user_id"],
        "plant_listing.approve",
        "plant_listing_request",
        request_id,
        {"plant_id": plant_id, "google_place_id": place_id if real_google_place else None, "owner_id": owner["id"] if owner else None},
    )
    if owner:
        await write_audit(
            ctx["user_id"],
            "plant_owner.assign",
            "plant",
            plant_id,
            {"owner_id": owner["id"], "account_created": owner["created"]},
        )
        await record_notification(
            owner["id"],
            "plant_owner",
            "Plant Owner access enabled",
            f"You can now sign in with email OTP and manage {req.get('name') or 'your RMC plant'}.",
        )
    if req.get("requested_by"):
        await record_notification(
            req["requested_by"],
            "plant_listing",
            "RMC plant listing approved",
            f"{req.get('name') or 'The plant'} is now listed in TrackMyRMC. Ordering stays disabled until plant setup is completed.",
        )
    return {"status": "APPROVED", "plant_id": plant_id, "owner_id": owner["id"] if owner else None}


@router.get("/unowned-plants")
async def list_unowned_plants(ctx: dict = Depends(reviewer_only)):
    del ctx
    docs = await plants.find(
        {
            "$or": [{"owner_id": None}, {"owner_id": {"$exists": False}}],
            "status": {"$ne": "deleted"},
        }
    ).sort("name", 1).to_list(500)
    return {
        "plants": [
            {
                "id": str(doc["_id"]),
                "name": doc.get("name"),
                "city": doc.get("city"),
                "address": doc.get("address"),
                "status": doc.get("status"),
            }
            for doc in docs
        ]
    }


@router.post("/plants/{plant_id}/assign-owner")
async def assign_first_owner(
    plant_id: str,
    body: OwnerAssignmentBody,
    ctx: dict = Depends(reviewer_only),
):
    plant = await plants.find_one({"_id": _oid(plant_id)})
    if not plant:
        raise HTTPException(404, "Plant not found")
    if plant.get("owner_id"):
        raise HTTPException(409, "Plant already has an owner; use the controlled owner-replacement flow")

    owner = await _provision_plant_owner(body)
    now = datetime.now(timezone.utc)
    updated = await plants.update_one(
        {
            "_id": plant["_id"],
            "$or": [{"owner_id": None}, {"owner_id": {"$exists": False}}],
        },
        {"$set": {"owner_id": owner["id"], "updated_at": now}},
    )
    if not updated.modified_count:
        raise HTTPException(409, "Plant ownership changed concurrently; reload and retry")

    await write_audit(
        ctx["user_id"],
        "plant_owner.assign",
        "plant",
        plant_id,
        {"owner_id": owner["id"], "account_created": owner["created"]},
    )
    await record_notification(
        owner["id"],
        "plant_owner",
        "Plant Owner access enabled",
        f"You can now sign in with email OTP and manage {plant.get('name') or 'your RMC plant'}.",
    )
    return {"status": "ASSIGNED", "plant_id": plant_id, "owner_id": owner["id"]}


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
        {
            "$set": {
                "status": "REJECTED",
                "reject_reason": reason,
                "reviewed_by": ctx["user_id"],
                "reviewed_at": now,
                "updated_at": now,
            }
        },
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
