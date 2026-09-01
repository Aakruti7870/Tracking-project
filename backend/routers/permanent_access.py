"""Verified DigiLocker KYC compatibility routes.

Reviewer access is deliberately implemented only by ``routers.play_review``.
That endpoint is disabled by default and validates a deployment secret.  This
module must not override the normal OTP routes or provision privileged users.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from audit import write_audit
from database import kyc_profiles
from notifications import record_notification
from routers import customer as customer_routes
from services.digilocker import (
    DigiLockerConfigurationError,
    DigiLockerProviderError,
    get_digilocker_session_status,
)

router = APIRouter(tags=["permanent-access"])

async def ensure_permanent_access() -> None:
    """Apply the idempotent legacy KYC migration at startup."""
    # Older builds converted a successful DigiLocker consent into PENDING and
    # waited for Authority review. Provider success is the verification event,
    # so safely upgrade only those legacy DigiLocker-completed records.
    now = datetime.now(timezone.utc)
    await kyc_profiles.update_many(
        {
            "status": "PENDING",
            "provider": "DIGILOCKER",
            "consent_verified_at": {"$exists": True},
        },
        {
            "$set": {
                "status": "VERIFIED",
                "verified_at": now,
                "verification_method": "DIGILOCKER_PROVIDER_SUCCESS",
                "legacy_pending_migrated_at": now,
                "updated_at": now,
            }
        },
    )


@router.get("/api/customer/kyc")
async def get_customer_kyc(ctx: dict = Depends(customer_routes.customer_only)):
    """Treat a successful DigiLocker provider result as final KYC verification."""
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
            return {
                "status": "IN_PROGRESS",
                "provider": "DIGILOCKER",
                "refresh_failed": True,
            }

        now = datetime.now(timezone.utc)
        if provider["status"] == "SUCCEEDED":
            status = "VERIFIED"
            result = await kyc_profiles.update_one(
                {"_id": kyc["_id"], "status": "IN_PROGRESS"},
                {
                    "$set": {
                        "status": status,
                        "provider_status": provider["provider_status"],
                        "provider_transaction_id": provider["transaction_id"],
                        "consent_verified_at": now,
                        "verified_at": now,
                        "verification_method": "DIGILOCKER_PROVIDER_SUCCESS",
                        "updated_at": now,
                    }
                },
            )
            if result.modified_count == 1:
                await write_audit(
                    uid,
                    "kyc.digilocker.verified",
                    "kyc_profile",
                    str(kyc["_id"]),
                    {"purpose": "CUSTOMER"},
                )
                await record_notification(
                    uid,
                    "kyc",
                    "KYC Verified",
                    "Your DigiLocker verification is complete. You can now place live orders.",
                )
        elif provider["status"] == "FAILED":
            status = "REQUIRES_REVERIFICATION"
            await kyc_profiles.update_one(
                {"_id": kyc["_id"], "status": "IN_PROGRESS"},
                {
                    "$set": {
                        "status": status,
                        "provider_status": provider["provider_status"],
                        "provider_transaction_id": provider["transaction_id"],
                        "updated_at": now,
                    }
                },
            )
            await write_audit(
                uid,
                "kyc.digilocker.failed",
                "kyc_profile",
                str(kyc["_id"]),
                {"purpose": "CUSTOMER"},
            )

    return {"status": status, "provider": "DIGILOCKER"}
