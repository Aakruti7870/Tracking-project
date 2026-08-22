"""Security helpers: identifier normalization, OTP hashing, JWT, auth deps."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest
from hmac import new as hmac_new
from secrets import randbelow, token_urlsafe

import jwt
from fastapi import Depends, Header, HTTPException, status

from config import settings
from database import sessions, users


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_aware(dt: datetime) -> datetime:
    """Mongo returns naive UTC datetimes; coerce to tz-aware for comparison."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def detect_channel(identifier: str) -> str:
    return "email" if "@" in identifier else "sms"


def normalize_identifier(identifier: str) -> tuple[str, str]:
    """Return (channel, normalized_value)."""
    raw = identifier.strip()
    channel = detect_channel(raw)
    if channel == "email":
        value = raw.lower()
        if "@" not in value or len(value) > 254:
            raise HTTPException(422, "Enter a valid email address")
    else:
        value = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
        digits = value.lstrip("+")
        if len(digits) < 8:
            raise HTTPException(422, "Enter a valid mobile number")
    return channel, value


def identifier_key(value: str) -> str:
    return hmac_new(settings.OTP_PEPPER.encode(), value.encode(), sha256).hexdigest()


def otp_digest(code: str, challenge_id: str) -> str:
    return hmac_new(
        settings.OTP_PEPPER.encode(), f"{challenge_id}:{code}".encode(), sha256
    ).hexdigest()


def generate_code() -> str:
    upper = 10 ** settings.OTP_LENGTH
    return str(randbelow(upper)).zfill(settings.OTP_LENGTH)


def verify_code(code: str, code_hash: str, challenge_id: str) -> bool:
    return compare_digest(code_hash, otp_digest(code, challenge_id))


def new_session_id() -> str:
    return token_urlsafe(24)


def issue_jwt(user_id: str, sid: str, role: str) -> tuple[str, datetime]:
    expires = utcnow() + timedelta(seconds=settings.SESSION_TTL_SECONDS)
    claims = {
        "sub": user_id,
        "sid": sid,
        "role": role,
        "iat": utcnow(),
        "exp": expires,
    }
    token = jwt.encode(claims, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, expires


async def current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bearer token required")
    try:
        payload = jwt.decode(
            authorization[7:],
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "sid", "exp"]},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    session = await sessions.find_one(
        {"_id": payload["sid"], "user_id": payload["sub"], "revoked": False}
    )
    if not session or as_aware(session["expires_at"]) <= utcnow():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or revoked")

    user = await users.find_one({"_id": _oid(payload["sub"])})
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    if user.get("status") == "suspended":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account suspended")
    if user.get("status") in ("disabled", "deleted"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account not available")

    return {
        "user_id": payload["sub"],
        "sid": payload["sid"],
        "role": user.get("primary_role"),
        "roles": user.get("roles", []),
        "plant_id": user.get("plant_id"),
        "user": user,
    }


def require_role(*allowed: str):
    async def dependency(ctx: dict = Depends(current_user)) -> dict:
        if ctx["role"] not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return ctx

    return dependency


def _oid(value: str):
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return value
