"""Plant Owner and staff email-OTP authentication.

This route intentionally reuses the hardened OTP/session primitives without
changing Customer/Driver mobile OTP or deleting the legacy Google OAuth backend.
The mobile app no longer needs Google OAuth as the Plant Staff entry point.
"""
from datetime import timedelta

from fastapi import APIRouter, HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from config import settings
from database import otps
from models import RequestOtpBody, VerifyOtpBody
from notifications import delivery, provider_status
from roles import Role
from routers.auth import _assert_account_available, _find_login_user, _issue_session
from security import as_aware, generate_code, identifier_key, normalize_identifier, otp_digest, utcnow, verify_code

router = APIRouter(prefix="/api/auth/staff", tags=["staff-auth"])

STAFF_EMAIL_ROLES = {
    Role.PLANT_OWNER.value,
    Role.ADMIN.value,
    Role.DISPATCHER.value,
    Role.OPERATOR.value,
    Role.SUPERVISOR.value,
    Role.ACCOUNTANT.value,
    Role.QUALITY_ENGINEER.value,
    Role.FLEET_MANAGER.value,
    Role.STORE_MANAGER.value,
    Role.AUTHORITY.value,
    Role.CENTRAL_ADMIN.value,
}


def _staff_role_allowed(role: str | None) -> bool:
    return role in STAFF_EMAIL_ROLES


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
    if not _staff_role_allowed(role):
        raise HTTPException(403, "This account cannot use Plant Staff Login")
    _assert_account_available(user)
    return await _issue_email_challenge(value)


@router.post("/verify-otp")
async def verify_staff_otp(body: VerifyOtpBody):
    channel, value = normalize_identifier(body.identifier)
    if channel != "email":
        raise HTTPException(422, "Plant Staff Login requires a valid email address")

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

    user = await _find_login_user(channel, value)
    if not user or not _staff_role_allowed(user.get("primary_role")):
        raise HTTPException(403, "This email is not approved for Plant Staff access")

    return await _issue_session(user, "staff_email_otp")
