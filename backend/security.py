"""Security helpers: identifier normalization, OTP hashing, JWT, auth deps."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest
from hmac import new as hmac_new
from secrets import randbelow, token_urlsafe

import jwt
from fastapi import Depends, Header, HTTPException, Request, status

from config import settings
from database import sessions, users

PLANT_SCOPED_STAFF_ROLES = {
    "admin", "dispatcher", "operator", "supervisor", "accountant",
    "quality_engineer", "fleet_manager", "store_manager",
}
CENTRAL_ADMIN_ROLE = "central_admin"
CONTROL_CENTER_SESSION_FLAG = "control_center_mfa_authenticated"
CONTROL_CENTER_AUTH_SURFACE = "control_center_web"

MFA_BOOTSTRAP_ALLOWED_PATHS = {
    "/api/me",
    "/api/auth/logout",
    "/api/auth/staff/mfa/status",
    "/api/auth/staff/mfa/enroll/start",
    "/api/auth/staff/mfa/enroll/confirm",
}

# A fully authenticated Central Admin is deliberately fail-closed to the
# dedicated web administration surfaces. Legacy operational routers often still
# include central_admin in historical RBAC lists for compatibility, but those
# declarations must not become permission-bypass paths for a Control Center
# bearer. Authority remains unaffected and keeps its operational Plant Staff
# routes.
CENTRAL_ADMIN_CONTROL_CENTER_PREFIXES = (
    "/api/admin/",
    "/api/control-center/",
)
CENTRAL_ADMIN_CONTROL_CENTER_PATHS = {
    "/api/me",
    "/api/auth/logout",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_aware(dt: datetime) -> datetime:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def detect_channel(identifier: str) -> str:
    return "email" if "@" in identifier else "sms"


def normalize_identifier(identifier: str) -> tuple[str, str]:
    raw = identifier.strip()
    channel = detect_channel(raw)
    if channel == "email":
        value = raw.lower()
        local, sep, domain = value.partition("@")
        if not sep or not local or "." not in domain or len(value) > 254:
            raise HTTPException(422, "Enter a valid email address")
    else:
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) < 8 or len(digits) > 15:
            raise HTTPException(422, "Enter a valid mobile number")
        value = f"+{digits}" if raw.startswith("+") else digits
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


def _is_control_center_session(session: dict) -> bool:
    return bool(
        session.get(CONTROL_CENTER_SESSION_FLAG)
        and session.get("auth_surface") == CONTROL_CENTER_AUTH_SURFACE
    )


def _central_admin_path_allowed(request_path: str) -> bool:
    return bool(
        request_path in CENTRAL_ADMIN_CONTROL_CENTER_PATHS
        or any(request_path.startswith(prefix) for prefix in CENTRAL_ADMIN_CONTROL_CENTER_PREFIXES)
    )


async def current_user(
    request: Request = None,
    authorization: str = Header(default=""),
) -> dict:
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

    latest_session = await sessions.find_one(
        {"user_id": payload["sub"]},
        sort=[("created_at", -1), ("_id", -1)],
    )
    if not latest_session or latest_session.get("_id") != payload["sid"]:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Session ended because this account was signed in on another device",
        )

    request_path = request.url.path if request is not None else ""
    if session.get("mfa_bootstrap_only"):
        if request is None or request_path not in MFA_BOOTSTRAP_ALLOWED_PATHS:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Authenticator App setup is required before this Plant Staff session can access the app",
            )

    user = await users.find_one({"_id": _oid(payload["sub"])})
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    if user.get("status") == "suspended":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account suspended")
    if user.get("status") in ("disabled", "deleted"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account not available")

    role = user.get("primary_role")
    if role in PLANT_SCOPED_STAFF_ROLES and not user.get("plant_id"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Plant assignment required for this staff account",
        )

    if role == CENTRAL_ADMIN_ROLE and not _is_control_center_session(session):
        bootstrap_allowed = bool(
            session.get("mfa_bootstrap_only")
            and request_path in MFA_BOOTSTRAP_ALLOWED_PATHS
        )
        if not bootstrap_allowed and request_path != "/api/auth/logout":
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Central Admin access requires the web Control Center",
            )

    if role == CENTRAL_ADMIN_ROLE and _is_control_center_session(session):
        if request is None or not _central_admin_path_allowed(request_path):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Central Admin must use the permission-gated Control Center route",
            )

    # Safe metadata for the Sessions workspace. This never stores credentials,
    # bearer values, or request bodies.
    now = utcnow()
    await sessions.update_one(
        {"_id": payload["sid"], "user_id": payload["sub"], "revoked": False},
        {"$set": {"last_activity_at": now}},
    )
    session["last_activity_at"] = now

    return {
        "user_id": payload["sub"],
        "sid": payload["sid"],
        "role": role,
        "roles": user.get("roles", []),
        "plant_id": user.get("plant_id"),
        "user": user,
        "session": session,
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
