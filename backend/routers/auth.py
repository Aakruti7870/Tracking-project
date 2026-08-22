"""Auth router: OTP request/verify, logout. Passwordless + JWT sessions."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException

from audit import write_audit
from config import settings
from database import otps, sessions, users
from models import RequestOtpBody, VerifyOtpBody
from notifications import delivery, provider_status
from roles import ROLE_LOGIN_CHANNELS, Role
from security import (
    current_user,
    generate_code,
    identifier_key,
    issue_jwt,
    new_session_id,
    normalize_identifier,
    otp_digest,
    utcnow,
    verify_code,
)
from security import as_aware

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/request-otp")
async def request_otp(body: RequestOtpBody):
    channel, value = normalize_identifier(body.identifier)
    key = identifier_key(value)

    # Resend throttle: block if an unconsumed, unexpired code is too fresh.
    existing = await otps.find_one(
        {"identifier_key": key, "consumed": False, "expires_at": {"$gt": utcnow()}},
        sort=[("created_at", -1)],
    )
    if existing:
        age = (utcnow() - as_aware(existing["created_at"])).total_seconds()
        if age < settings.OTP_RESEND_SECONDS:
            wait = int(settings.OTP_RESEND_SECONDS - age)
            raise HTTPException(429, f"Please wait {wait}s before requesting another code")

    from bson import ObjectId

    challenge_id = ObjectId()
    code = generate_code()
    await otps.insert_one(
        {
            "_id": challenge_id,
            "identifier_key": key,
            "channel": channel,
            "code_hash": otp_digest(code, str(challenge_id)),
            "attempts": 0,
            "consumed": False,
            "created_at": utcnow(),
            "expires_at": utcnow() + timedelta(seconds=settings.OTP_TTL_SECONDS),
        }
    )

    await delivery.send(channel, value, f"Your TrackMyRMC OTP is {code}")

    response = {
        "status": "OTP_SENT",
        "channel": channel,
        "expires_in": settings.OTP_TTL_SECONDS,
        "delivery": provider_status(),
    }
    # Dev convenience: surface the OTP in non-prod so the preview stays testable
    # (the seeded demo numbers are not real and cannot receive a live SMS).
    if settings.is_dev and settings.DEBUG_OTP:
        response["dev_otp"] = code
    return response


@router.post("/verify-otp")
async def verify_otp(body: VerifyOtpBody):
    channel, value = normalize_identifier(body.identifier)
    key = identifier_key(value)

    doc = await otps.find_one(
        {"identifier_key": key, "consumed": False}, sort=[("created_at", -1)]
    )
    if not doc or as_aware(doc["expires_at"]) <= utcnow():
        raise HTTPException(400, "Invalid or expired code")
    if doc["attempts"] >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(429, "Too many attempts. Request a new code")

    if not verify_code(body.code, doc["code_hash"], str(doc["_id"])):
        await otps.update_one({"_id": doc["_id"]}, {"$inc": {"attempts": 1}})
        raise HTTPException(400, "Invalid or expired code")

    # Atomic single-use consumption.
    from pymongo import ReturnDocument

    consumed = await otps.find_one_and_update(
        {"_id": doc["_id"], "consumed": False},
        {"$set": {"consumed": True}},
        return_document=ReturnDocument.AFTER,
    )
    if not consumed:
        raise HTTPException(400, "Invalid or expired code")

    # Resolve the account server-side. Pre-provisioned staff must exist already;
    # unknown identifiers self-register as customers (mobile only).
    user = await users.find_one({"identifier_keys": key})
    if not user:
        if channel != "sms":
            raise HTTPException(403, "No account found for this email. Contact your plant/admin.")
        from models import User

        new_user = User(
            name="New Customer",
            phone=value,
            identifier_keys=[key],
            roles=[Role.CUSTOMER.value],
            primary_role=Role.CUSTOMER.value,
        )
        insert = await users.insert_one(new_user.to_mongo())
        user = await users.find_one({"_id": insert.inserted_id})
        await write_audit(str(user["_id"]), "user.self_register", "user", str(user["_id"]))

    role = user.get("primary_role")

    # Enforce channel-per-role policy.
    allowed = ROLE_LOGIN_CHANNELS.get(role, {"sms", "email"})
    if channel not in allowed:
        raise HTTPException(403, f"This account must sign in with {' or '.join(sorted(allowed))} OTP")

    # Account status gate.
    status_val = user.get("status", "active")
    if status_val == "suspended":
        raise HTTPException(403, "Your account is suspended")
    if status_val in ("disabled", "deleted"):
        raise HTTPException(403, "Your account is no longer active")

    sid = new_session_id()
    token, expires = issue_jwt(str(user["_id"]), sid, role)
    await sessions.insert_one(
        {
            "_id": sid,
            "user_id": str(user["_id"]),
            "role": role,
            "revoked": False,
            "created_at": utcnow(),
            "expires_at": expires,
        }
    )
    await write_audit(str(user["_id"]), "auth.login", "session", sid)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires.isoformat(),
        "role": role,
        "name": user.get("name"),
    }


@router.post("/logout")
async def logout(ctx: dict = Depends(current_user)):
    await sessions.update_one({"_id": ctx["sid"]}, {"$set": {"revoked": True}})
    await write_audit(ctx["user_id"], "auth.logout", "session", ctx["sid"])
    return {"status": "ok"}
