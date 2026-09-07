"""Plant Owner and staff email-OTP bootstrap authentication.

Email OTP remains the safe first-login/bootstrap path. Once an approved Plant
Staff account activates Authenticator App MFA, email OTP can no longer issue a
normal session; phishing-resistant passkey or Authenticator verification becomes
the login authority instead. Customer/Driver mobile OTP is untouched.
"""
from datetime import timedelta

from fastapi import APIRouter, HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from config import settings
from database import otps, sessions
from models import RequestOtpBody, VerifyOtpBody
from notifications import delivery, provider_status
from roles import Role
from routers.auth import _assert_account_available, _find_login_user, _issue_session
from security import (
    as_aware,
    generate_code,
    identifier_key,
    issue_jwt,
    new_session_id,
    normalize_identifier,
    otp_digest,
    utcnow,
    verify_code,
)

router = APIRouter(prefix="/api/auth/staff", tags=["staff-auth"])

STAFF_EMAIL_ROLES = {
    Role.AUTHORITY.value,
    Role.PLANT_OWNER.value,
    Role.ADMIN.value,
    Role.DISPATCHER.value,
    Role.OPERATOR.value,
    Role.SUPERVISOR.value,
    Role.ACCOUNTANT.value,
    Role.QUALITY_ENGINEER.value,
    Role.FLEET_MANAGER.value,
    Role.STORE_MANAGER.value,
}


def _mfa_bootstrap_role_allowed(user: dict) -> bool:
    """Allow approved Central Admins to bootstrap TOTP, but never normal staff login."""
    if _staff_role_allowed(user.get("primary_role")):
        return True
    if user.get("primary_role") != Role.CENTRAL_ADMIN.value:
        return False
    from control_center_security import APPROVED_CONTROL_CENTER_EMAILS

    return (user.get("email") or "").strip().casefold() in APPROVED_CONTROL_CENTER_EMAILS


def _staff_role_allowed(role: str | None) -> bool:
    return role in STAFF_EMAIL_ROLES


def _staff_mfa_enabled(user: dict) -> bool:
    mfa = user.get("mfa") if isinstance(user.get("mfa"), dict) else {}
    return bool(mfa.get("enabled") and mfa.get("totp_secret"))


def _staff_passkey_enabled(user: dict) -> bool:
    mfa = user.get("mfa") if isinstance(user.get("mfa"), dict) else {}
    passkeys = mfa.get("passkeys") if isinstance(mfa.get("passkeys"), list) else []
    return any(isinstance(item, dict) and item.get("active", True) for item in passkeys)


async def _issue_mfa_bootstrap_session(user: dict):
    """Issue a session that can only reach /me + MFA enrollment until TOTP is confirmed."""
    _assert_account_available(user)
    role = user.get("primary_role")
    sid = new_session_id()
    token, full_expires = issue_jwt(str(user["_id"]), sid, role)
    bootstrap_expires = utcnow() + timedelta(minutes=15)
    await sessions.insert_one(
        {
            "_id": sid,
            "user_id": str(user["_id"]),
            "role": role,
            "revoked": False,
            "mfa_bootstrap_only": True,
            "created_at": utcnow(),
            "expires_at": bootstrap_expires,
            "post_mfa_expires_at": full_expires,
        }
    )
    await write_audit(
        str(user["_id"]),
        "auth.mfa_bootstrap_login",
        "session",
        sid,
        {"login_method": "staff_email_otp_bootstrap"},
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": bootstrap_expires.isoformat(),
        "role": role,
        "name": user.get("name"),
        "mfa_setup_required": True,
    }


async def _issue_email_challenge(value: str) -> dict:
    key = identifier_key(value)
    now = utcnow()
    await otps.update_many(
        {"identifier_key": key, "consumed": False, "expires_at": {"$lte": now}},
        {"$set": {"consumed": True, "expired_at": now}},
    )
    existing = await otps.find_one(
        {"identifier_key": key, "consumed": False, "expires_at": {"$gt": now}},
        sort=[("created_at", -1)],
    )
    if existing:
        age = (now - as_aware(existing["created_at"])).total_seconds()
        if age < settings.OTP_RESEND_SECONDS:
            wait = max(1, int(settings.OTP_RESEND_SECONDS - age))
            raise HTTPException(429, f"Please wait {wait}s before requesting another code")
        await otps.update_one(
            {"_id": existing["_id"], "consumed": False},
            {"$set": {"consumed": True, "invalidated_at": now}},
        )

    from bson import ObjectId

    challenge_id = ObjectId()
    code = generate_code()
    try:
        await otps.insert_one(
            {
                "_id": challenge_id,
                "identifier_key": key,
                "channel": "email",
                "purpose": "staff_login",
                "code_hash": otp_digest(code, str(challenge_id)),
                "attempts": 0,
                "consumed": False,
                "created_at": now,
                "expires_at": now + timedelta(seconds=settings.OTP_TTL_SECONDS),
            }
        )
    except DuplicateKeyError:
        raise HTTPException(429, "A verification code was just issued. Please wait before retrying")

    sent = await delivery.send("email", value, f"Your TrackMyRMC Plant Staff OTP is {code}")
    if not sent and not (settings.is_dev and settings.DEBUG_OTP):
        await otps.update_one(
            {"_id": challenge_id},
            {"$set": {"consumed": True, "delivery_failed_at": utcnow()}},
        )
        raise HTTPException(503, "Email verification service is temporarily unavailable")

    response = {
        "status": "OTP_SENT",
        "channel": "email",
        "expires_in": settings.OTP_TTL_SECONDS,
        "delivery": provider_status(),
        "mfa_setup_required": True,
    }
    if settings.is_dev and settings.DEBUG_OTP:
        response["dev_otp"] = code
    return response


@router.post("/request-otp")
async def request_staff_otp(body: RequestOtpBody):
    channel, value = normalize_identifier(body.identifier)
    if channel != "email":
        raise HTTPException(422, "Plant Staff Login requires a valid email address")

    user = await _find_login_user(channel, value)
    if not user:
        return {
            "status": "ONBOARDING_REQUIRED",
            "channel": "email",
            "email": value,
            "message": "This email is not yet approved for Plant Staff access.",
        }

    role = user.get("primary_role")
    if not _mfa_bootstrap_role_allowed(user):
        raise HTTPException(403, "This account cannot use Plant Staff Login")
    _assert_account_available(user)

    if _staff_mfa_enabled(user):
        if role == Role.CENTRAL_ADMIN.value:
            raise HTTPException(403, "Use the Control Center to sign in")
        passkey_available = _staff_passkey_enabled(user)
        return {
            "status": "AUTHENTICATOR_REQUIRED",
            "channel": "passkey" if passkey_available else "totp",
            "email": value,
            "passkey_available": passkey_available,
            "message": (
                "Use your passkey, or choose Authenticator as a fallback."
                if passkey_available
                else "Enter the 6-digit code from your Authenticator App."
            ),
        }
    return await _issue_email_challenge(value)


@router.post("/verify-otp")
async def verify_staff_otp(body: VerifyOtpBody):
    channel, value = normalize_identifier(body.identifier)
    if channel != "email":
        raise HTTPException(422, "Plant Staff Login requires a valid email address")

    user = await _find_login_user(channel, value)
    if not user or not _mfa_bootstrap_role_allowed(user):
        raise HTTPException(403, "This email is not approved for Plant Staff access")
    _assert_account_available(user)
    if _staff_mfa_enabled(user):
        raise HTTPException(403, "Passkey or Authenticator verification is required for this account")

    key = identifier_key(value)
    doc = await otps.find_one(
        {
            "identifier_key": key,
            "channel": "email",
            "purpose": "staff_login",
            "consumed": False,
        },
        sort=[("created_at", -1)],
    )
    if not doc or as_aware(doc["expires_at"]) <= utcnow():
        raise HTTPException(400, "Invalid or expired code")
    if doc.get("attempts", 0) >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(429, "Too many attempts. Request a new code")

    if not verify_code(body.code, doc["code_hash"], str(doc["_id"])):
        attempted = await otps.find_one_and_update(
            {
                "_id": doc["_id"],
                "consumed": False,
                "attempts": {"$lt": settings.OTP_MAX_ATTEMPTS},
                "expires_at": {"$gt": utcnow()},
            },
            {"$inc": {"attempts": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if not attempted or attempted.get("attempts", 0) >= settings.OTP_MAX_ATTEMPTS:
            raise HTTPException(429, "Too many attempts. Request a new code")
        raise HTTPException(400, "Invalid or expired code")

    consumed = await otps.find_one_and_update(
        {
            "_id": doc["_id"],
            "consumed": False,
            "attempts": {"$lt": settings.OTP_MAX_ATTEMPTS},
            "expires_at": {"$gt": utcnow()},
        },
        {"$set": {"consumed": True, "consumed_at": utcnow()}},
        return_document=ReturnDocument.AFTER,
    )
    if not consumed:
        raise HTTPException(400, "Invalid or expired code")

    if settings.MFA_ENCRYPTION_KEY and len(settings.MFA_ENCRYPTION_KEY) >= 32:
        return await _issue_mfa_bootstrap_session(user)
    return await _issue_session(user, "staff_email_otp_bootstrap")
