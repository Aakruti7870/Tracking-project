"""Permanent production access rules for Play review and verified DigiLocker KYC.

Google Play review credentials are reusable only for the exact isolated reviewer
identities below. Every reviewer entry point obeys the same audited runtime
Control Center switch. Normal customers, drivers, plant staff and platform-admin
accounts continue through their normal OTP/MFA providers.
"""
import logging
from datetime import datetime, timezone
from secrets import compare_digest

from fastapi import APIRouter, Depends, HTTPException
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from config import settings
from control_center_security import APPROVED_CONTROL_CENTER_EMAILS
from database import kyc_profiles, users
from models import RequestOtpBody, User, VerifyOtpBody
from notifications import record_notification
from play_review import play_review_user
from reviewer_access import issue_reviewer_session, reviewer_access_enabled
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
logger = logging.getLogger(__name__)

DEMO_CUSTOMER_PHONE = "+919000009901"
DEMO_DRIVER_PHONE = "+919000009902"
DEMO_OWNER_EMAIL = "play-review-owner@trackmyrmc.test"

PERMANENT_AUTHORITY_EMAILS = (
    "support@goldetech.com",
)
PERMANENT_CENTRAL_ADMIN_EMAILS = tuple(sorted(APPROVED_CONTROL_CENTER_EMAILS))
PERMANENT_PLATFORM_ROLES = {
    **{email: Role.CENTRAL_ADMIN.value for email in PERMANENT_CENTRAL_ADMIN_EMAILS},
    "support@goldetech.com": Role.AUTHORITY.value,
}


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
    }.get(email)


def permanent_platform_role(value: str) -> str | None:
    return PERMANENT_PLATFORM_ROLES.get(value.strip().lower())


def _review_code_valid(code: str) -> bool:
    configured = settings.PLAY_REVIEW_ACCESS_CODE
    return bool(configured and compare_digest(code, configured))


async def _require_reviewer_access() -> None:
    if not await reviewer_access_enabled():
        raise HTTPException(404, "Reviewer access is not enabled")


def _platform_identity_role_is_safe(existing: dict, expected_role: str, email: str) -> bool:
    """Never convert an existing account into a privileged platform role.

    A configured permanent identity may be refreshed only when it is already
    provisioned with the exact expected primary role. A conflicting Customer,
    Owner, Authority, Central Admin, or Plant Staff identity is left untouched
    so startup cannot silently escalate or rewrite a real account.
    """
    current_role = existing.get("primary_role")
    if current_role == expected_role:
        return True
    logger.error(
        "Permanent platform-admin identity conflict for %s: existing role %r does not match expected role %r; account left unchanged",
        email,
        current_role,
        expected_role,
    )
    return False


async def _ensure_platform_admin(email: str) -> None:
    """Idempotently provision only non-conflicting configured platform identities."""
    normalized = email.strip().lower()
    role = permanent_platform_role(normalized)
    if role not in {Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value}:
        raise ValueError(f"Unsupported permanent platform-admin identity: {normalized}")

    key = identifier_key(normalized)
    existing = await users.find_one({"identifier_keys": key})
    flags = {
        "permanent_platform_admin": True,
        "permanent_authority": role == Role.AUTHORITY.value,
        "permanent_central_admin": role == Role.CENTRAL_ADMIN.value,
    }
    if existing:
        if not _platform_identity_role_is_safe(existing, role, normalized):
            return
        await users.update_one(
            {"_id": existing["_id"], "primary_role": role},
            {
                "$set": {
                    "email": normalized,
                    **flags,
                },
                "$addToSet": {"roles": role},
            },
        )
        return

    name = (
        "TrackMyRMC Super Admin"
        if role == Role.CENTRAL_ADMIN.value
        else "GOLD-e Tech Support Authority"
    )
    user = User(
        name=name,
        email=normalized,
        identifier_keys=[key],
        roles=[role],
        primary_role=role,
    ).to_mongo()
    user.update(flags)
    try:
        await users.insert_one(user)
    except DuplicateKeyError:
        existing = await users.find_one({"identifier_keys": key})
        if not existing:
            raise
        if not _platform_identity_role_is_safe(existing, role, normalized):
            return
        await users.update_one(
            {"_id": existing["_id"], "primary_role": role},
            {
                "$set": {
                    "email": normalized,
                    **flags,
                },
                "$addToSet": {"roles": role},
            },
        )


async def ensure_permanent_access() -> None:
    """Apply idempotent production bootstrap/migration rules at startup."""
    for email in (*PERMANENT_AUTHORITY_EMAILS, *PERMANENT_CENTRAL_ADMIN_EMAILS):
        await _ensure_platform_admin(email)

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
            await _require_reviewer_access()
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
        await _require_reviewer_access()
        if not _review_code_valid(body.code):
            raise HTTPException(400, "Invalid or expired code")
        user = await play_review_user(role)
        return await issue_reviewer_session(user, role, "permanent_google_play_demo_otp")
    return await auth_routes.verify_otp(body)


@router.post("/api/auth/staff/request-otp")
async def request_staff_otp(body: RequestOtpBody):
    channel, value = normalize_identifier(body.identifier)
    role = demo_staff_role(value) if channel == "email" else None
    if role:
        await _require_reviewer_access()
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
        await _require_reviewer_access()
        if not _review_code_valid(body.code):
            raise HTTPException(400, "Invalid or expired code")
        user = await play_review_user(role)
        return await issue_reviewer_session(user, role, "permanent_google_play_demo_otp")
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
