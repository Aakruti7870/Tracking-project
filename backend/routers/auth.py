"""Authentication routes: mobile OTP for customers/drivers and Google OAuth for staff."""
from datetime import timedelta
from secrets import token_urlsafe
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from audit import write_audit
from config import settings
from database import otps, sessions, users
from models import RequestOtpBody, VerifyOtpBody
from notifications import delivery, provider_status
from roles import GOOGLE_LOGIN_ROLES, ROLE_LOGIN_CHANNELS, Role
from security import (
    PLANT_SCOPED_STAFF_ROLES,
    as_aware,
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

router = APIRouter(prefix="/api/auth", tags=["auth"])

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_STATE_TTL_SECONDS = 600
GOOGLE_EXCHANGE_TTL_SECONDS = 120


class GoogleExchangeBody(BaseModel):
    code: str = Field(min_length=20, max_length=512)


def _login_identifier_keys(channel: str, value: str) -> list[str]:
    """Return canonical plus legacy login hashes without widening phone identity.

    The redesigned India mobile field always submits +91 followed by ten digits.
    Older builds could persist the same number as 10 digits or 91+10 digits.
    Looking up all three representations prevents a legacy Driver/Customer from
    being mistaken for a new Customer. New registrations remain canonical +91.
    """
    values = [value]
    if channel == "sms":
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) == 12 and digits.startswith("91"):
            values.extend([digits, digits[2:]])
        elif len(digits) == 10:
            values.extend([f"+91{digits}", f"91{digits}"])

    keys: list[str] = []
    for candidate in values:
        key = identifier_key(candidate)
        if key not in keys:
            keys.append(key)
    return keys


async def _find_login_user(channel: str, value: str) -> dict | None:
    keys = _login_identifier_keys(channel, value)
    return await users.find_one({"identifier_keys": {"$in": keys}})


def _assert_account_available(user: dict) -> None:
    status_val = user.get("status", "active")
    if status_val == "suspended":
        raise HTTPException(403, "Your account is suspended")
    if status_val in ("disabled", "deleted"):
        raise HTTPException(403, "Your account is no longer active")
    role = user.get("primary_role")
    if role in PLANT_SCOPED_STAFF_ROLES and not user.get("plant_id"):
        raise HTTPException(403, "Plant assignment required for this staff account")


async def _issue_session(user: dict, login_method: str):
    _assert_account_available(user)
    role = user.get("primary_role")
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
    await write_audit(
        str(user["_id"]),
        "auth.login",
        "session",
        sid,
        {"login_method": login_method},
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires.isoformat(),
        "role": role,
        "name": user.get("name"),
    }


def _google_app_redirect(**params: str) -> RedirectResponse:
    query = urlencode(params)
    return RedirectResponse(
        url=f"{settings.GOOGLE_OAUTH_APP_REDIRECT_URI}?{query}",
        status_code=302,
    )


@router.post("/request-otp")
async def request_otp(body: RequestOtpBody):
    channel, value = normalize_identifier(body.identifier)
    key = identifier_key(value)
    now = utcnow()

    # Mongo's TTL monitor is asynchronous, so an expired challenge may remain
    # physically present briefly. Consume it before relying on the unique index.
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
                "channel": channel,
                "code_hash": otp_digest(code, str(challenge_id)),
                "attempts": 0,
                "consumed": False,
                "created_at": now,
                "expires_at": now + timedelta(seconds=settings.OTP_TTL_SECONDS),
            }
        )
    except DuplicateKeyError:
        raise HTTPException(429, "A verification code was just issued. Please wait before retrying")

    sent = await delivery.send(channel, value, f"Your TrackMyRMC OTP is {code}")
    if not sent and not (settings.is_dev and settings.DEBUG_OTP):
        await otps.update_one(
            {"_id": challenge_id},
            {"$set": {"consumed": True, "delivery_failed_at": utcnow()}},
        )
        raise HTTPException(503, f"{channel.upper()} verification service is temporarily unavailable")

    response = {
        "status": "OTP_SENT",
        "channel": channel,
        "expires_in": settings.OTP_TTL_SECONDS,
        "delivery": provider_status(),
    }
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

    # Resolve canonical +91 and legacy Indian phone representations before any
    # self-registration. Staff identities must be provisioned in advance.
    user = await _find_login_user(channel, value)
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
        try:
            insert = await users.insert_one(new_user.to_mongo())
            user = await users.find_one({"_id": insert.inserted_id})
            await write_audit(
                str(user["_id"]), "user.self_register", "user", str(user["_id"])
            )
        except DuplicateKeyError:
            # A concurrent request or an existing legacy representation won the
            # race; resolve all accepted aliases again rather than duplicate it.
            user = await _find_login_user(channel, value)
            if not user:
                raise HTTPException(409, "Account registration conflict; retry login")

    role = user.get("primary_role")
    if role in GOOGLE_LOGIN_ROLES:
        raise HTTPException(403, "This account must sign in with Google")

    allowed = ROLE_LOGIN_CHANNELS.get(role, set())
    if channel not in allowed:
        raise HTTPException(403, "This account must sign in with mobile OTP")

    return await _issue_session(user, "mobile_otp")


@router.get("/google/start")
async def google_start():
    if not (
        settings.GOOGLE_OAUTH_CLIENT_ID
        and settings.GOOGLE_OAUTH_CLIENT_SECRET
        and settings.GOOGLE_OAUTH_REDIRECT_URI
    ):
        raise HTTPException(503, "Google sign-in is not configured")

    state = jwt.encode(
        {
            "purpose": "google_staff_login",
            "nonce": token_urlsafe(16),
            "iat": utcnow(),
            "exp": utcnow() + timedelta(seconds=GOOGLE_STATE_TTL_SECONDS),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    authorization_url = GOOGLE_AUTHORIZE_URL + "?" + urlencode(
        {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
            "access_type": "online",
        }
    )
    return {"authorization_url": authorization_url}


@router.get("/google/callback")
async def google_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        return _google_app_redirect(error="google_cancelled")
    if not code or not state:
        return _google_app_redirect(error="google_invalid_response")

    try:
        state_claims = jwt.decode(
            state,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["purpose", "exp"]},
        )
        if state_claims.get("purpose") != "google_staff_login":
            raise jwt.InvalidTokenError("wrong OAuth state purpose")
    except jwt.InvalidTokenError:
        return _google_app_redirect(error="google_invalid_state")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                    "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
        if token_response.status_code != 200:
            return _google_app_redirect(error="google_exchange_failed")
        google_tokens = token_response.json()
    except (httpx.HTTPError, ValueError):
        return _google_app_redirect(error="google_unavailable")

    raw_id_token = google_tokens.get("id_token")
    if not raw_id_token:
        return _google_app_redirect(error="google_missing_identity")

    try:
        claims = google_id_token.verify_oauth2_token(
            raw_id_token,
            google_auth_requests.Request(),
            settings.GOOGLE_OAUTH_CLIENT_ID,
        )
    except (ValueError, TypeError):
        return _google_app_redirect(error="google_identity_invalid")

    email = str(claims.get("email") or "").strip().lower()
    if not email or claims.get("email_verified") not in (True, "true"):
        return _google_app_redirect(error="google_email_unverified")

    try:
        channel, normalized_email = normalize_identifier(email)
    except HTTPException:
        return _google_app_redirect(error="google_email_invalid")
    if channel != "email":
        return _google_app_redirect(error="google_email_invalid")

    user = await users.find_one({"identifier_keys": identifier_key(normalized_email)})
    if not user:
        return _google_app_redirect(error="account_not_provisioned")

    role = user.get("primary_role")
    if role not in GOOGLE_LOGIN_ROLES:
        return _google_app_redirect(error="use_mobile_login")

    try:
        _assert_account_available(user)
    except HTTPException as exc:
        if exc.status_code == 403 and "Plant assignment" in str(exc.detail):
            return _google_app_redirect(error="account_not_ready")
        return _google_app_redirect(error="account_unavailable")

    exchange_code = token_urlsafe(32)
    exchange_key = identifier_key(f"google-exchange:{exchange_code}")
    now = utcnow()
    try:
        await otps.insert_one(
            {
                "identifier_key": exchange_key,
                "channel": "google_exchange",
                "user_id": str(user["_id"]),
                "consumed": False,
                "attempts": 0,
                "created_at": now,
                "expires_at": now + timedelta(seconds=GOOGLE_EXCHANGE_TTL_SECONDS),
            }
        )
    except DuplicateKeyError:
        return _google_app_redirect(error="google_retry")

    return _google_app_redirect(code=exchange_code)


@router.post("/google/exchange")
async def google_exchange(body: GoogleExchangeBody):
    from bson import ObjectId
    from bson.errors import InvalidId

    exchange_key = identifier_key(f"google-exchange:{body.code.strip()}")
    doc = await otps.find_one_and_update(
        {
            "identifier_key": exchange_key,
            "channel": "google_exchange",
            "consumed": False,
            "expires_at": {"$gt": utcnow()},
        },
        {"$set": {"consumed": True, "consumed_at": utcnow()}},
        return_document=ReturnDocument.AFTER,
    )
    if not doc:
        raise HTTPException(400, "Google login code is invalid or expired")

    user_id = doc.get("user_id")
    try:
        lookup_id = ObjectId(user_id)
    except (InvalidId, TypeError):
        lookup_id = user_id
    user = await users.find_one({"_id": lookup_id})
    if not user or user.get("primary_role") not in GOOGLE_LOGIN_ROLES:
        raise HTTPException(403, "Google staff account is not available")

    return await _issue_session(user, "google_oauth")


@router.post("/logout")
async def logout(ctx: dict = Depends(current_user)):
    await sessions.update_one({"_id": ctx["sid"]}, {"$set": {"revoked": True}})
    await write_audit(ctx["user_id"], "auth.logout", "session", ctx["sid"])
    return {"status": "ok"}
