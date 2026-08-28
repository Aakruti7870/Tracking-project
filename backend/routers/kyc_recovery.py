"""Recovery endpoints for incomplete DigiLocker KYC sessions.

Authority users may see KYC sessions that are still IN_PROGRESS and reset only
those incomplete sessions so the customer can start a fresh DigiLocker flow.
Completed/PENDING/VERIFIED decisions remain owned by the existing KYC review
routes and cannot be changed here.
"""
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from audit import write_audit
from database import kyc_profiles, users
from notifications import record_notification
from roles import Role
from security import require_role

router = APIRouter(prefix="/api/staff/kyc-recovery", tags=["staff-kyc-recovery"])
authority_only = require_role(Role.AUTHORITY.value)


def _oid(value: str):
    try:
        return ObjectId(value)
    except Exception:
        return value


def can_reset_status(status: str | None) -> bool:
    return status == "IN_PROGRESS"


@router.get("")
async def list_incomplete_kyc(ctx: dict = Depends(authority_only)):
    del ctx
    docs = await kyc_profiles.find({"status": "IN_PROGRESS"}).sort("updated_at", -1).to_list(500)
    items = []
    for profile in docs:
        user = await users.find_one({"_id": _oid(str(profile.get("user_id") or ""))})
        updated_at = profile.get("updated_at")
        items.append({
            "id": str(profile["_id"]),
            "name": (user or {}).get("name") or "User",
            "contact": (user or {}).get("phone") or (user or {}).get("email"),
            "purpose": profile.get("purpose", "CUSTOMER"),
            "status": "IN_PROGRESS",
            "provider": profile.get("provider") or "DIGILOCKER",
            "provider_status": profile.get("provider_status"),
            "updated_at": updated_at.isoformat() if updated_at else None,
        })
    return {"title": "Incomplete DigiLocker sessions", "items": items}


@router.post("/{profile_id}/reset")
async def reset_incomplete_kyc(profile_id: str, ctx: dict = Depends(authority_only)):
    profile = await kyc_profiles.find_one({"_id": _oid(profile_id)})
    if not profile:
        raise HTTPException(404, "KYC profile not found")
    if not can_reset_status(profile.get("status")):
        raise HTTPException(409, "Only an incomplete DigiLocker session can be reset")

    now = datetime.now(timezone.utc)
    result = await kyc_profiles.update_one(
        {"_id": profile["_id"], "status": "IN_PROGRESS"},
        {
            "$set": {
                "status": "REQUIRES_REVERIFICATION",
                "provider_status": "RESET_BY_AUTHORITY",
                "updated_at": now,
            },
            "$unset": {
                "provider_session_id": "",
                "provider_transaction_id": "",
                "consent_verified_at": "",
            },
        },
    )
    if result.modified_count != 1:
        raise HTTPException(409, "KYC status changed; refresh before retrying")

    await write_audit(
        ctx["user_id"],
        "kyc.reset_for_retry",
        "kyc_profile",
        profile_id,
        {"purpose": profile.get("purpose", "CUSTOMER")},
    )
    if profile.get("user_id"):
        await record_notification(
            profile["user_id"],
            "kyc",
            "KYC ready to retry",
            "Your incomplete DigiLocker session was reset. Please start KYC again.",
        )
    return {"status": "REQUIRES_REVERIFICATION"}
