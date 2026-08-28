"""Permanent production access rules for Play review and verified DigiLocker KYC.

The Google Play demo OTP is intentionally reusable, but only for the four exact,
non-production reviewer identities below. Normal customers, drivers, plant staff
and permanent Authority accounts continue through the normal OTP/MFA providers.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from config import settings
from database import kyc_profiles, users
from models import RequestOtpBody, User, VerifyOtpBody
from notifications import record_notification
from play_review import play_review_user
from roles import Role
from routers import auth as auth_routes
from routers import customer as customer_routes
from routers import staff_auth as staff_auth_routes
from security import identifier_key, normalize_identifier
from services.digilocker import (
    DigiLockerConfigurationError,
    DigiLockerProviderError,
    get_digilocker_session_status,
)

router = APIRouter(tags=["permanent-access"])

DEMO_OTP = "123456"

# Stable Google Play Console reviewer credentials. These identities are isolated
# from real customer/staff identities and are the only accounts allowed to use
# the reusable demo OTP.
DEMO_CUSTOMER_PHONE = "+919000009901"
DEMO_DRIVER_PHONE = "+919000009902"
DEMO_OWNER_EMAIL = "play-review-owner@trackmyrmc.test"
DEMO_AUTHORITY_EMAIL = "play-review-authority@trackmyrmc.test"

PERMANENT_AUTHORITY_EMAILS = (
    "support@goldetech.com",
    "support@trackmyrmc.com",
)


def _mobile_digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def demo_mobile_role(value: str) -> str | None:
    digits = _mobile_digits(value)
    aliases = {
        "919000009901": Role.CUSTOMER.value,
        "9000009901": Role.CUSTOMER.value,
        "919000009902": Role.DRIVER.value,
        "9000009902": Role.DRIVER.value,
    }
    return aliases.get(digits)


def demo_staff_role(value: str) -> str | None:
    email = value.strip().lower()
    return {
        DEMO_OWNER_EMAIL: Role.PLANT_OWNER.value,
        DEMO_AUTHORITY_EMAIL: Role.AUTHORITY.value,
    }.get(email)


async def _ensure_authority(email: str) -> None:
    """Idempotently guarantee a production Authority identity by email.

    No fixed/demo OTP is granted here. These support accounts use the normal
    Plant Staff email OTP and MFA policy.
    """
    normalized = email.strip().lower()
    key = identifier_key(normalized)
    existing = await users.find_one({"identifier_keys": key})
    if existing:
        await users.update_one(
            {"_id": existing["_id"]},
            {
                "$set": {
                    "email": normalized,
                    "primary_role": Role.AUTHORITY.value,
                    "status": "active",
                    "permanent_authority": True,
                },
                "$addToSet": {"roles": Role.AUTHORITY.value},
            },
        )
        return

    name = (
        "GOLD-e Tech Support Authority"
        if normalized == "support@goldetech.com"
        else "TrackMyRMC Support Authority"
    )
    user = User(
        name=name,
        email=normalized,
        identifier_keys=[key],
        roles=[Role.AUTHORITY.value],
        primary_role=Role.AUTHORITY.value,
    ).to_mongo()
    user["permanent_authority"] = True
    try:
        await users.insert_one(user)
    except DuplicateKeyError:
        # Another startup worker may have created it concurrently.
        existing = await users.find_one({"identifier_keys": key})
        if not existing:
            raise


async def ensure_permanent_access() -> None:
    """Apply idempotent production bootstrap/migration rules at startup."""
    for email in PERMANENT_AUTHORITY_EMAILS:
        await _ensure_authority(email)

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


@router.post("/api/auth/request-otp")
async def request_otp(body: RequestOtpBody):
    channel, value = normalize_identifier(body.identifier)
    if channel == "sms":
        role = demo_mobile_role(value)
        if role:
            await play_review_user(role)
            return {
                "status": "OTP_SENT",
                "channel": "sms",
                "expires_in": settings.OTP_TTL_SECONDS,
                "delivery": {"adapter": "google_play_demo", "configured": True},
                "message": "Use the permanent Google Play review OTP supplied in Play Console.",
            }
    return await auth_routes.request_otp(body)


@router.post("/api/auth/verify-otp")
async def verify_otp(body: VerifyOtpBody):
    channel, value = normalize_identifier(body.identifier)
    role = demo_mobile_role(value) if channel == "sms" else None
    if role:
        if body.code != DEMO_OTP:
            raise HTTPException(400, "Invalid or expired code")
        user = await play_review_user(role)
        return await auth_routes._issue_session(user, "permanent_google_play_demo_otp")
    return await auth_routes.verify_otp(body)


@router.post("/api/auth/staff/request-otp")
async def request_staff_otp(body: RequestOtpBody):
    channel, value = normalize_identifier(body.identifier)
    role = demo_staff_role(value) if channel == "email" else None
    if role:
        user = await play_review_user(role)
        auth_routes._assert_account_available(user)
        return {
            "status": "OTP_SENT",
            "channel": "email",
            "expires_in": settings.OTP_TTL_SECONDS,
            "delivery": {"adapter": "google_play_demo", "configured": True},
            "mfa_setup_required": False,
            "message": "Use the permanent Google Play review OTP supplied in Play Console.",
        }
    return await staff_auth_routes.request_staff_otp(body)


@router.post("/api/auth/staff/verify-otp")
async def verify_staff_otp(body: VerifyOtpBody):
    channel, value = normalize_identifier(body.identifier)
    role = demo_staff_role(value) if channel == "email" else None
    if role:
        if body.code != DEMO_OTP:
            raise HTTPException(400, "Invalid or expired code")
        user = await play_review_user(role)
        return await auth_routes._issue_session(user, "permanent_google_play_demo_otp")
    return await staff_auth_routes.verify_staff_otp(body)


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
