"""Plant Staff TOTP MFA enrollment, login, recovery and privileged reset.

Passkeys are intentionally isolated from this router so native credential-manager
integration can ship in its own Android-reviewed change. This module establishes
the strong-auth foundation without weakening the existing Customer/Driver OTP
flows.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import re
import secrets
import time
from datetime import timedelta
from urllib.parse import quote

from bson import ObjectId
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from validation import StrictModel
from pymongo import ReturnDocument

from audit import write_audit
from config import settings
from database import plants, sessions, users
from roles import Role
from routers.auth import _assert_account_available, _find_login_user, _issue_session
from routers.staff_auth import _staff_role_allowed
from security import as_aware, current_user, normalize_identifier, utcnow

router = APIRouter(prefix="/api/auth/staff/mfa", tags=["staff-mfa"])

TOTP_PERIOD_SECONDS = 30
TOTP_DIGITS = 6
TOTP_WINDOW = 1
MFA_MAX_FAILURES = 5
MFA_LOCK_SECONDS = 300
MFA_ENROLL_TTL_SECONDS = 600
RECOVERY_CODE_COUNT = 10
RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class IdentifierBody(StrictModel):
    identifier: str = Field(min_length=3, max_length=254)


class TotpLoginBody(IdentifierBody):
    code: str = Field(min_length=6, max_length=8)


class ConfirmEnrollmentBody(StrictModel):
    code: str = Field(min_length=6, max_length=8)


class RecoveryLoginBody(IdentifierBody):
    recovery_code: str = Field(min_length=8, max_length=32)


class ResetUserMfaBody(StrictModel):
    target_user_id: str = Field(min_length=3, max_length=64)
    actor_code: str = Field(min_length=6, max_length=8)


def _ensure_mfa_configured() -> None:
    if not settings.MFA_ENCRYPTION_KEY or len(settings.MFA_ENCRYPTION_KEY) < 32:
        raise HTTPException(503, "Plant Staff MFA is not configured on the server yet")


def _fernet() -> Fernet:
    _ensure_mfa_configured()
    digest = hashlib.sha256(settings.MFA_ENCRYPTION_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("ascii")).decode("ascii")


def _decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("ascii")
    except (InvalidToken, ValueError, TypeError):
        raise HTTPException(500, "Stored MFA credential is unavailable")


def _decode_base32(secret: str) -> bytes:
    padding = "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(secret + padding, casefold=True)


def _totp_at(secret: str, for_time: int) -> str:
    counter = int(for_time // TOTP_PERIOD_SECONDS)
    digest = hmac.new(
        _decode_base32(secret), counter.to_bytes(8, "big"), hashlib.sha1
    ).digest()
    offset = digest[-1] & 0x0F
    binary = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return str(binary % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def _normalize_totp(code: str) -> str:
    return re.sub(r"\D", "", code or "")


def _verify_totp(secret: str, code: str, now_ts: int | None = None) -> bool:
    normalized = _normalize_totp(code)
    if len(normalized) != TOTP_DIGITS:
        return False
    ts = int(time.time() if now_ts is None else now_ts)
    for window in range(-TOTP_WINDOW, TOTP_WINDOW + 1):
        candidate = _totp_at(secret, ts + window * TOTP_PERIOD_SECONDS)
        if hmac.compare_digest(candidate, normalized):
            return True
    return False


def _new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _recovery_code() -> str:
    raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def _normalize_recovery_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _recovery_hash(user_id: str, value: str) -> str:
    _ensure_mfa_configured()
    normalized = _normalize_recovery_code(value)
    return hmac.new(
        settings.MFA_ENCRYPTION_KEY.encode("utf-8"),
        f"recovery:{user_id}:{normalized}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _mfa_doc(user: dict) -> dict:
    value = user.get("mfa")
    return value if isinstance(value, dict) else {}


def _mfa_enabled(user: dict) -> bool:
    mfa = _mfa_doc(user)
    return bool(mfa.get("enabled") and mfa.get("totp_secret"))


def _assert_not_locked(user: dict) -> None:
    locked_until = _mfa_doc(user).get("locked_until")
    if locked_until and as_aware(locked_until) > utcnow():
        remaining = max(1, int((as_aware(locked_until) - utcnow()).total_seconds()))
        raise HTTPException(429, f"Too many attempts. Try again in {remaining}s")


async def _record_failure(user: dict) -> None:
    now = utcnow()
    updated = await users.find_one_and_update(
        {"_id": user["_id"]},
        {
            "$inc": {"mfa.failed_attempts": 1},
            "$set": {"mfa.last_failed_at": now},
        },
        return_document=ReturnDocument.AFTER,
    )
    failures = int((_mfa_doc(updated or {})).get("failed_attempts", 0))
    if failures >= MFA_MAX_FAILURES:
        await users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "mfa.failed_attempts": 0,
                    "mfa.locked_until": now + timedelta(seconds=MFA_LOCK_SECONDS),
                }
            },
        )
        raise HTTPException(429, "Too many attempts. Authenticator login is temporarily locked")


async def _record_success(user: dict) -> None:
    await users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "mfa.failed_attempts": 0,
                "mfa.last_success_at": utcnow(),
            },
            "$unset": {"mfa.locked_until": ""},
        },
    )


async def _resolve_staff(identifier: str) -> tuple[str, dict]:
    channel, value = normalize_identifier(identifier)
    if channel != "email":
        raise HTTPException(422, "Plant Staff Login requires a valid email address")
    user = await _find_login_user(channel, value)
    if not user:
        raise HTTPException(403, "This email is not approved for Plant Staff access")
    if not _staff_role_allowed(user.get("primary_role")):
        raise HTTPException(403, "This account cannot use Plant Staff Login")
    _assert_account_available(user)
    return value, user


def _qr_data_uri(uri: str) -> str | None:
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage

        image = qrcode.make(uri, image_factory=SvgPathImage, box_size=8, border=3)
        buffer = io.BytesIO()
        image.save(buffer)
        return "data:image/svg+xml;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return None


@router.post("/method")
async def staff_auth_method(body: IdentifierBody):
    value, user = await _resolve_staff(body.identifier)
    if _mfa_enabled(user):
        return {
            "status": "AUTHENTICATOR_REQUIRED",
            "email": value,
            "method": "totp",
            "recovery_available": bool(_mfa_doc(user).get("recovery_code_hashes")),
        }
    return {
        "status": "EMAIL_OTP_REQUIRED",
        "email": value,
        "method": "email_otp",
        "message": "Verify your approved email once to activate Authenticator App security.",
    }


@router.post("/verify-totp")
async def verify_staff_totp(body: TotpLoginBody):
    _ensure_mfa_configured()
    _value, user = await _resolve_staff(body.identifier)
    if not _mfa_enabled(user):
        raise HTTPException(409, "Authenticator App is not activated for this account")
    _assert_not_locked(user)
    secret = _decrypt_secret(_mfa_doc(user)["totp_secret"])
    if not _verify_totp(secret, body.code):
        await _record_failure(user)
        raise HTTPException(400, "Invalid Authenticator code")
    await _record_success(user)
    return await _issue_session(user, "staff_totp")


@router.post("/verify-recovery")
async def verify_staff_recovery(body: RecoveryLoginBody):
    _ensure_mfa_configured()
    _value, user = await _resolve_staff(body.identifier)
    if not _mfa_enabled(user):
        raise HTTPException(409, "Authenticator App is not activated for this account")
    recovery_hash = _recovery_hash(str(user["_id"]), body.recovery_code)
    consumed = await users.find_one_and_update(
        {
            "_id": user["_id"],
            "mfa.enabled": True,
            "mfa.recovery_code_hashes": recovery_hash,
        },
        {
            "$pull": {"mfa.recovery_code_hashes": recovery_hash},
            "$set": {"mfa.last_recovery_at": utcnow()},
        },
        return_document=ReturnDocument.AFTER,
    )
    if not consumed:
        raise HTTPException(400, "Invalid or already used recovery code")
    await write_audit(
        str(user["_id"]),
        "auth.mfa_recovery_used",
        "user",
        str(user["_id"]),
    )
    return await _issue_session(consumed, "staff_recovery_code")


@router.get("/status")
async def mfa_status(ctx: dict = Depends(current_user)):
    user = ctx["user"]
    if not _staff_role_allowed(ctx.get("role")):
        raise HTTPException(403, "MFA settings are available only to Plant Staff accounts")
    mfa = _mfa_doc(user)
    return {
        "configured": bool(settings.MFA_ENCRYPTION_KEY and len(settings.MFA_ENCRYPTION_KEY) >= 32),
        "enabled": _mfa_enabled(user),
        "recovery_codes_remaining": len(mfa.get("recovery_code_hashes") or []),
        "enrolled_at": mfa.get("enrolled_at"),
    }


@router.post("/enroll/start")
async def start_totp_enrollment(ctx: dict = Depends(current_user)):
    _ensure_mfa_configured()
    user = ctx["user"]
    if not _staff_role_allowed(ctx.get("role")):
        raise HTTPException(403, "MFA enrollment is available only to Plant Staff accounts")
    if _mfa_enabled(user):
        raise HTTPException(409, "Authenticator App is already activated")

    secret = _new_totp_secret()
    now = utcnow()
    expires = now + timedelta(seconds=MFA_ENROLL_TTL_SECONDS)
    await users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "mfa.pending_totp_secret": _encrypt_secret(secret),
                "mfa.pending_expires_at": expires,
                "mfa.pending_started_at": now,
            }
        },
    )
    email = (user.get("email") or user.get("name") or str(user["_id"])).strip()
    issuer = settings.MFA_ISSUER or "TrackMyRMC"
    label = f"{issuer}:{email}"
    uri = (
        f"otpauth://totp/{quote(label, safe='')}?secret={secret}"
        f"&issuer={quote(issuer, safe='')}&algorithm=SHA1&digits=6&period=30"
    )
    await write_audit(
        str(user["_id"]), "auth.mfa_enrollment_started", "user", str(user["_id"])
    )
    return {
        "status": "MFA_ENROLLMENT_STARTED",
        "issuer": issuer,
        "account": email,
        "manual_key": secret,
        "otpauth_uri": uri,
        "qr_data_uri": _qr_data_uri(uri),
        "expires_in": MFA_ENROLL_TTL_SECONDS,
    }


@router.post("/enroll/confirm")
async def confirm_totp_enrollment(
    body: ConfirmEnrollmentBody,
    ctx: dict = Depends(current_user),
):
    _ensure_mfa_configured()
    user = await users.find_one({"_id": ObjectId(ctx["user_id"])})
    if not user or not _staff_role_allowed(user.get("primary_role")):
        raise HTTPException(403, "MFA enrollment is unavailable")
    if _mfa_enabled(user):
        raise HTTPException(409, "Authenticator App is already activated")
    mfa = _mfa_doc(user)
    pending = mfa.get("pending_totp_secret")
    expires = mfa.get("pending_expires_at")
    if not pending or not expires or as_aware(expires) <= utcnow():
        raise HTTPException(400, "Authenticator setup expired. Start setup again")
    secret = _decrypt_secret(pending)
    if not _verify_totp(secret, body.code):
        raise HTTPException(400, "Authenticator code did not match. Check device time and retry")

    plain_codes = [_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    hashes = [_recovery_hash(str(user["_id"]), code) for code in plain_codes]
    now = utcnow()
    await users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "mfa.enabled": True,
                "mfa.totp_secret": _encrypt_secret(secret),
                "mfa.enrolled_at": now,
                "mfa.recovery_code_hashes": hashes,
                "mfa.failed_attempts": 0,
            },
            "$unset": {
                "mfa.pending_totp_secret": "",
                "mfa.pending_expires_at": "",
                "mfa.pending_started_at": "",
                "mfa.locked_until": "",
            },
        },
    )
    await sessions.update_many(
        {
            "user_id": str(user["_id"]),
            "_id": {"$ne": ctx["sid"]},
            "revoked": False,
        },
        {
            "$set": {
                "revoked": True,
                "revoked_at": now,
                "revoke_reason": "mfa_enrolled",
            }
        },
    )

    session = ctx.get("session") or {}
    if session.get("mfa_bootstrap_only"):
        full_expires = session.get("post_mfa_expires_at")
        await sessions.update_one(
            {"_id": ctx["sid"], "user_id": ctx["user_id"], "revoked": False},
            {
                "$set": {
                    "mfa_bootstrap_only": False,
                    "auth_method": "staff_totp",
                    "mfa_completed_at": now,
                    **({"expires_at": full_expires} if full_expires else {}),
                },
                "$unset": {"post_mfa_expires_at": ""},
            },
        )
    await write_audit(
        str(user["_id"]),
        "auth.mfa_enrolled",
        "user",
        str(user["_id"]),
        {"method": "totp", "recovery_codes": RECOVERY_CODE_COUNT},
    )
    return {
        "status": "MFA_ENABLED",
        "recovery_codes": plain_codes,
        "message": "Save these recovery codes now. They will not be shown again.",
    }


async def _can_reset(actor: dict, target: dict) -> bool:
    actor_role = actor.get("primary_role")
    target_role = target.get("primary_role")
    if actor_role == Role.CENTRAL_ADMIN.value:
        return True
    if actor_role == Role.AUTHORITY.value:
        return target_role not in {Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value}
    if actor_role == Role.PLANT_OWNER.value:
        owner_id = actor.get("_id")
        plant = await plants.find_one(
            {"owner_id": {"$in": [str(owner_id), owner_id]}}
        )
        target_plant = target.get("plant_id")
        return bool(
            plant
            and target_plant
            and str(plant.get("_id")) == str(target_plant)
            and target_role not in {Role.PLANT_OWNER.value, Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value}
        )
    return False


@router.post("/reset-user")
async def reset_user_mfa(
    body: ResetUserMfaBody,
    ctx: dict = Depends(current_user),
):
    _ensure_mfa_configured()
    actor = ctx["user"]
    if actor.get("primary_role") not in {
        Role.PLANT_OWNER.value,
        Role.AUTHORITY.value,
        Role.CENTRAL_ADMIN.value,
    }:
        raise HTTPException(403, "Only an Owner or platform authority can reset staff MFA")
    if not _mfa_enabled(actor):
        raise HTTPException(403, "Activate your own Authenticator App before resetting another user")
    actor_secret = _decrypt_secret(_mfa_doc(actor)["totp_secret"])
    if not _verify_totp(actor_secret, body.actor_code):
        raise HTTPException(403, "Your Authenticator code is invalid")

    try:
        target_oid = ObjectId(body.target_user_id)
    except Exception:
        raise HTTPException(422, "Invalid target user id")
    target = await users.find_one({"_id": target_oid})
    if not target or not _staff_role_allowed(target.get("primary_role")):
        raise HTTPException(404, "Plant Staff account not found")
    if str(target["_id"]) == str(actor["_id"]):
        raise HTTPException(409, "Use recovery controls for your own account")
    if not await _can_reset(actor, target):
        raise HTTPException(403, "You cannot reset MFA for this account")

    now = utcnow()
    await users.update_one({"_id": target["_id"]}, {"$unset": {"mfa": ""}})
    await sessions.update_many(
        {"user_id": str(target["_id"]), "revoked": False},
        {"$set": {"revoked": True, "revoked_at": now, "revoke_reason": "mfa_reset"}},
    )
    await write_audit(
        str(actor["_id"]),
        "auth.mfa_reset",
        "user",
        str(target["_id"]),
        {"target_role": target.get("primary_role")},
    )
    return {
        "status": "MFA_RESET",
        "target_user_id": str(target["_id"]),
        "message": "Authenticator App was reset and active sessions were revoked.",
    }
