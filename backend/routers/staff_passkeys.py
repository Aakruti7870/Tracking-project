"""High-assurance Plant Staff passkey/WebAuthn ceremonies.

Passkeys are a phishing-resistant login method layered on the approved-staff +
TOTP foundation. Authentication requires WebAuthn user verification. Creating or
removing a passkey additionally requires a fresh Authenticator code, so a stolen
session or compromised passkey cannot silently change credential ownership.

The mobile app runs the WebAuthn ceremony in the system browser on the canonical
https://trackmyrmc.com origin. No JWT is placed in a URL; all browser capabilities
and login handoffs are random, single-use and short-lived.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import timedelta
from typing import Any, Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from audit import write_audit
from config import settings
from database import passkey_handoffs, users, webauthn_challenges, webauthn_requests
from routers.auth import _assert_account_available, _issue_session
from routers.staff_auth import _staff_role_allowed
from routers.staff_mfa import (
    _assert_not_locked,
    _decrypt_secret,
    _mfa_doc,
    _mfa_enabled,
    _record_failure,
    _reset_failures,
    _resolve_staff,
    _verify_totp,
)
from security import current_user, utcnow

router = APIRouter(prefix="/api/auth/staff/passkey", tags=["staff-passkey"])

CHALLENGE_TTL_SECONDS = 180
REQUEST_TTL_SECONDS = 90
HANDOFF_TTL_SECONDS = 60
MAX_PASSKEYS_PER_USER = 5


class AuthenticationStartBody(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    return_mode: Literal["app", "web"] = "app"


class RequestBody(BaseModel):
    request_id: str = Field(min_length=24, max_length=128)


class CeremonyVerifyBody(RequestBody):
    ceremony_id: str = Field(min_length=24, max_length=128)
    credential: dict[str, Any]


class RegistrationStartBody(BaseModel):
    actor_code: str = Field(min_length=6, max_length=8)
    return_mode: Literal["app", "web"] = "app"


class HandoffBody(BaseModel):
    code: str = Field(min_length=24, max_length=256)


class RemovePasskeyBody(BaseModel):
    credential_id: str = Field(min_length=16, max_length=1024)
    actor_code: str = Field(min_length=6, max_length=8)


def _active_passkeys(user: dict) -> list[dict]:
    mfa = user.get("mfa") if isinstance(user.get("mfa"), dict) else {}
    raw = mfa.get("passkeys") if isinstance(mfa.get("passkeys"), list) else []
    return [item for item in raw if isinstance(item, dict) and item.get("active", True)]


def _passkey_user_handle(user: dict) -> str | None:
    mfa = user.get("mfa") if isinstance(user.get("mfa"), dict) else {}
    value = mfa.get("passkey_user_handle")
    return value if isinstance(value, str) and len(value) >= 16 else None


def _new_token(bytes_count: int = 32) -> str:
    return secrets.token_urlsafe(bytes_count)


def _handoff_digest(code: str) -> str:
    return hmac.new(
        settings.OTP_PEPPER.encode("utf-8"),
        f"staff-passkey-handoff:{code}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _android_apk_origin() -> str | None:
    fingerprint = os.getenv("PLAY_SIGNING_SHA256", "").strip().replace(":", "")
    if len(fingerprint) != 64:
        return None
    try:
        digest = bytes.fromhex(fingerprint)
    except ValueError:
        return None
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"android:apk-key-hash:{encoded}"


def _allowed_origins() -> list[str]:
    origins = [settings.PASSKEY_WEB_ORIGIN]
    android_origin = _android_apk_origin()
    if android_origin:
        origins.append(android_origin)
    return origins


def _ceremony_url(flow: Literal["authenticate", "register"], request_id: str) -> str:
    # Fragment values are not sent in HTTP request lines or Referer headers.
    return f"{settings.PASSKEY_WEB_ORIGIN}/passkey-ceremony#flow={flow}&request_id={request_id}"


def _credential_id_from_response(credential: dict[str, Any]) -> str:
    value = credential.get("id") or credential.get("rawId")
    if not isinstance(value, str) or len(value) < 16:
        raise HTTPException(400, "Passkey response did not contain a valid credential id")
    return value


async def _verify_credential_management_totp(user: dict, actor_code: str) -> None:
    """Require a fresh TOTP before passkey registration/removal.

    This deliberately makes TOTP the credential-management authority even when
    passkeys are the preferred login method. Existing MFA lockout protections are
    reused so brute-force attempts cannot bypass the established controls.
    """
    if not _mfa_enabled(user):
        raise HTTPException(403, "Activate Authenticator security before managing passkeys")
    _assert_not_locked(user)
    secret = _decrypt_secret(_mfa_doc(user).get("totp_secret", ""))
    if not _verify_totp(secret, actor_code):
        await _record_failure(user)
        raise HTTPException(400, "Authenticator code did not match")
    await _reset_failures(user)


async def _create_request(
    *,
    user_id: str,
    purpose: Literal["authenticate", "register"],
    return_mode: Literal["app", "web"],
    sid: str | None = None,
) -> dict:
    request_id = _new_token()
    now = utcnow()
    document = {
        "_id": request_id,
        "user_id": user_id,
        "purpose": purpose,
        "return_mode": return_mode,
        "created_at": now,
        "expires_at": now + timedelta(seconds=REQUEST_TTL_SECONDS),
    }
    if sid:
        document["sid"] = sid
    await webauthn_requests.insert_one(document)
    return {
        "request_id": request_id,
        "authorization_url": _ceremony_url(purpose, request_id),
        "expires_in": REQUEST_TTL_SECONDS,
    }


async def _load_request(request_id: str, purpose: str) -> dict:
    doc = await webauthn_requests.find_one(
        {"_id": request_id, "purpose": purpose, "expires_at": {"$gt": utcnow()}}
    )
    if not doc:
        raise HTTPException(400, "Passkey request expired or is no longer valid")
    return doc


async def _store_challenge(request_doc: dict, challenge: str, purpose: str) -> str:
    ceremony_id = _new_token()
    now = utcnow()
    await webauthn_challenges.insert_one(
        {
            "_id": ceremony_id,
            "request_id": request_doc["_id"],
            "user_id": request_doc["user_id"],
            "purpose": purpose,
            "challenge": challenge,
            "created_at": now,
            "expires_at": now + timedelta(seconds=CHALLENGE_TTL_SECONDS),
        }
    )
    return ceremony_id


async def _consume_challenge(*, ceremony_id: str, request_doc: dict, purpose: str) -> dict:
    challenge = await webauthn_challenges.find_one_and_delete(
        {
            "_id": ceremony_id,
            "request_id": request_doc["_id"],
            "user_id": request_doc["user_id"],
            "purpose": purpose,
            "expires_at": {"$gt": utcnow()},
        }
    )
    if not challenge:
        raise HTTPException(400, "Passkey challenge expired, mismatched, or already used")
    return challenge


async def _issue_handoff(user_id: str, return_mode: str) -> str:
    code = _new_token(36)
    now = utcnow()
    await passkey_handoffs.insert_one(
        {
            "_id": _handoff_digest(code),
            "user_id": user_id,
            "return_mode": return_mode,
            "created_at": now,
            "expires_at": now + timedelta(seconds=HANDOFF_TTL_SECONDS),
        }
    )
    return code


@router.get("/status")
async def passkey_status(ctx: dict = Depends(current_user)):
    user = ctx["user"]
    if not _staff_role_allowed(ctx.get("role")):
        raise HTTPException(403, "Passkeys are available only to Plant Staff accounts")
    passkeys = _active_passkeys(user)
    return {
        "enabled": bool(passkeys),
        "count": len(passkeys),
        "rp_id": settings.PASSKEY_RP_ID,
        "web_origin": settings.PASSKEY_WEB_ORIGIN,
        "android_origin_configured": bool(_android_apk_origin()),
        "user_verification": "required",
    }


@router.post("/authenticate/start")
async def start_authentication(body: AuthenticationStartBody):
    value, user = await _resolve_staff(body.identifier)
    passkeys = _active_passkeys(user)
    if not _mfa_enabled(user) or not passkeys:
        raise HTTPException(409, "No passkey is registered for this Plant Staff account")
    request = await _create_request(
        user_id=str(user["_id"]), purpose="authenticate", return_mode=body.return_mode
    )
    await write_audit(
        str(user["_id"]),
        "auth.passkey_authentication_started",
        "user",
        str(user["_id"]),
        {"return_mode": body.return_mode},
    )
    return {**request, "email": value}


@router.post("/authenticate/options")
async def authentication_options(body: RequestBody):
    request_doc = await _load_request(body.request_id, "authenticate")
    try:
        user = await users.find_one({"_id": ObjectId(request_doc["user_id"])})
    except Exception:
        user = None
    if not user or not _staff_role_allowed(user.get("primary_role")):
        raise HTTPException(403, "Passkey authentication is unavailable")
    _assert_account_available(user)
    passkeys = _active_passkeys(user)
    if not passkeys:
        raise HTTPException(409, "No active passkey is registered")

    options = generate_authentication_options(
        rp_id=settings.PASSKEY_RP_ID,
        allow_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(item["credential_id"]))
            for item in passkeys
            if item.get("credential_id")
        ],
        user_verification=UserVerificationRequirement.REQUIRED,
        timeout=CHALLENGE_TTL_SECONDS * 1000,
    )
    payload = json.loads(options_to_json(options))
    payload["ceremony_id"] = await _store_challenge(
        request_doc, payload["challenge"], "authenticate"
    )
    return payload


@router.post("/authenticate/verify")
async def verify_authentication(body: CeremonyVerifyBody):
    request_doc = await _load_request(body.request_id, "authenticate")
    challenge_doc = await _consume_challenge(
        ceremony_id=body.ceremony_id, request_doc=request_doc, purpose="authenticate"
    )
    try:
        user = await users.find_one({"_id": ObjectId(request_doc["user_id"])})
    except Exception:
        user = None
    if not user or not _staff_role_allowed(user.get("primary_role")):
        raise HTTPException(403, "Passkey authentication is unavailable")
    _assert_account_available(user)

    credential_id = _credential_id_from_response(body.credential)
    stored = next(
        (item for item in _active_passkeys(user) if item.get("credential_id") == credential_id),
        None,
    )
    if not stored:
        raise HTTPException(400, "Passkey is not registered for this account")

    try:
        verified = verify_authentication_response(
            credential=body.credential,
            expected_challenge=base64url_to_bytes(challenge_doc["challenge"]),
            expected_rp_id=settings.PASSKEY_RP_ID,
            expected_origin=_allowed_origins(),
            credential_public_key=base64url_to_bytes(stored["public_key"]),
            credential_current_sign_count=int(stored.get("sign_count") or 0),
            require_user_verification=True,
        )
    except (InvalidAuthenticationResponse, ValueError, TypeError):
        await write_audit(
            str(user["_id"]),
            "auth.passkey_authentication_rejected",
            "user",
            str(user["_id"]),
            {"reason": "cryptographic_verification_failed"},
        )
        raise HTTPException(400, "Passkey verification failed")

    now = utcnow()
    updated = await users.find_one_and_update(
        {
            "_id": user["_id"],
            "mfa.passkeys": {"$elemMatch": {"credential_id": credential_id, "active": {"$ne": False}}},
        },
        {
            "$set": {
                "mfa.passkeys.$.sign_count": int(verified.new_sign_count),
                "mfa.passkeys.$.last_used_at": now,
                "mfa.passkeys.$.credential_device_type": str(
                    getattr(verified.credential_device_type, "value", verified.credential_device_type)
                ),
                "mfa.passkeys.$.backed_up": bool(verified.credential_backed_up),
                "mfa.passkeys.$.user_verified": bool(verified.user_verified),
            }
        },
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "Passkey changed while authentication was completing")

    deleted = await webauthn_requests.find_one_and_delete(
        {"_id": request_doc["_id"], "user_id": request_doc["user_id"]}
    )
    if not deleted:
        raise HTTPException(400, "Passkey request was already completed")

    handoff_code = await _issue_handoff(str(user["_id"]), request_doc["return_mode"])
    await write_audit(
        str(user["_id"]),
        "auth.passkey_verified",
        "user",
        str(user["_id"]),
        {"return_mode": request_doc["return_mode"]},
    )
    return {
        "status": "PASSKEY_VERIFIED",
        "handoff_code": handoff_code,
        "return_mode": request_doc["return_mode"],
        "expires_in": HANDOFF_TTL_SECONDS,
    }


@router.post("/exchange")
async def exchange_handoff(body: HandoffBody):
    handoff = await passkey_handoffs.find_one_and_delete(
        {"_id": _handoff_digest(body.code), "expires_at": {"$gt": utcnow()}}
    )
    if not handoff:
        raise HTTPException(400, "Passkey handoff expired or was already used")
    try:
        user = await users.find_one({"_id": ObjectId(handoff["user_id"])})
    except Exception:
        user = None
    if not user or not _staff_role_allowed(user.get("primary_role")):
        raise HTTPException(403, "Passkey login is unavailable")
    _assert_account_available(user)
    if not _active_passkeys(user):
        raise HTTPException(403, "Passkey access was revoked")
    return await _issue_session(user, "staff_passkey")


@router.post("/register/start")
async def start_registration(body: RegistrationStartBody, ctx: dict = Depends(current_user)):
    user = ctx["user"]
    if not _staff_role_allowed(ctx.get("role")):
        raise HTTPException(403, "Passkey enrollment is available only to Plant Staff accounts")
    if not _mfa_enabled(user):
        raise HTTPException(403, "Activate Authenticator security before creating a passkey")
    await _verify_credential_management_totp(user, body.actor_code)
    if len(_active_passkeys(user)) >= MAX_PASSKEYS_PER_USER:
        raise HTTPException(409, f"Maximum of {MAX_PASSKEYS_PER_USER} passkeys already registered")

    request = await _create_request(
        user_id=str(user["_id"]), purpose="register", return_mode=body.return_mode, sid=ctx["sid"]
    )
    await write_audit(
        str(user["_id"]),
        "auth.passkey_registration_started",
        "user",
        str(user["_id"]),
        {"return_mode": body.return_mode},
    )
    return request


@router.post("/register/options")
async def registration_options(body: RequestBody):
    request_doc = await _load_request(body.request_id, "register")
    try:
        user = await users.find_one({"_id": ObjectId(request_doc["user_id"])})
    except Exception:
        user = None
    if not user or not _staff_role_allowed(user.get("primary_role")) or not _mfa_enabled(user):
        raise HTTPException(403, "Passkey enrollment is unavailable")
    _assert_account_available(user)
    if len(_active_passkeys(user)) >= MAX_PASSKEYS_PER_USER:
        raise HTTPException(409, f"Maximum of {MAX_PASSKEYS_PER_USER} passkeys already registered")

    handle = _passkey_user_handle(user)
    if not handle:
        handle = bytes_to_base64url(secrets.token_bytes(32))
        claimed = await users.find_one_and_update(
            {
                "_id": user["_id"],
                "$or": [
                    {"mfa.passkey_user_handle": {"$exists": False}},
                    {"mfa.passkey_user_handle": None},
                ],
            },
            {"$set": {"mfa.passkey_user_handle": handle}},
            return_document=ReturnDocument.AFTER,
        )
        if claimed:
            user = claimed
        else:
            user = await users.find_one({"_id": user["_id"]})
            handle = _passkey_user_handle(user or {})
        if not handle:
            raise HTTPException(500, "Could not establish a stable passkey user handle")

    email = (user.get("email") or str(user["_id"])).strip().lower()
    display_name = (user.get("name") or email).strip()
    options = generate_registration_options(
        rp_id=settings.PASSKEY_RP_ID,
        rp_name=settings.PASSKEY_RP_NAME,
        user_id=base64url_to_bytes(handle),
        user_name=email,
        user_display_name=display_name,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        attestation=AttestationConveyancePreference.NONE,
        exclude_credentials=[
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(item["credential_id"]))
            for item in _active_passkeys(user)
            if item.get("credential_id")
        ],
        timeout=CHALLENGE_TTL_SECONDS * 1000,
    )
    payload = json.loads(options_to_json(options))
    payload["ceremony_id"] = await _store_challenge(request_doc, payload["challenge"], "register")
    return payload


@router.post("/register/verify")
async def verify_registration(body: CeremonyVerifyBody):
    request_doc = await _load_request(body.request_id, "register")
    challenge_doc = await _consume_challenge(
        ceremony_id=body.ceremony_id, request_doc=request_doc, purpose="register"
    )
    try:
        user = await users.find_one({"_id": ObjectId(request_doc["user_id"])})
    except Exception:
        user = None
    if not user or not _staff_role_allowed(user.get("primary_role")) or not _mfa_enabled(user):
        raise HTTPException(403, "Passkey enrollment is unavailable")
    _assert_account_available(user)

    deleted = await webauthn_requests.find_one_and_delete(
        {"_id": request_doc["_id"], "user_id": request_doc["user_id"], "purpose": "register"}
    )
    if not deleted:
        raise HTTPException(400, "Passkey registration request was already completed")

    try:
        verified = verify_registration_response(
            credential=body.credential,
            expected_challenge=base64url_to_bytes(challenge_doc["challenge"]),
            expected_rp_id=settings.PASSKEY_RP_ID,
            expected_origin=_allowed_origins(),
            require_user_verification=True,
        )
    except (InvalidRegistrationResponse, ValueError, TypeError):
        await write_audit(
            str(user["_id"]),
            "auth.passkey_registration_rejected",
            "user",
            str(user["_id"]),
            {"reason": "cryptographic_verification_failed"},
        )
        raise HTTPException(400, "Passkey registration verification failed")

    credential_id = bytes_to_base64url(verified.credential_id)
    conflict = await users.find_one(
        {"_id": {"$ne": user["_id"]}, "mfa.passkeys.credential_id": credential_id}, {"_id": 1}
    )
    if conflict:
        raise HTTPException(409, "This passkey is already registered to another account")
    if any(item.get("credential_id") == credential_id for item in _active_passkeys(user)):
        raise HTTPException(409, "This passkey is already registered")

    response = body.credential.get("response") if isinstance(body.credential.get("response"), dict) else {}
    transports = response.get("transports") if isinstance(response.get("transports"), list) else []
    now = utcnow()
    passkey = {
        "credential_id": credential_id,
        "public_key": bytes_to_base64url(verified.credential_public_key),
        "sign_count": int(verified.sign_count),
        "transports": [str(item)[:32] for item in transports[:8]],
        "credential_device_type": str(
            getattr(verified.credential_device_type, "value", verified.credential_device_type)
        ),
        "backed_up": bool(verified.credential_backed_up),
        "user_verified": bool(verified.user_verified),
        "active": True,
        "created_at": now,
        "last_used_at": None,
    }
    updated = await users.find_one_and_update(
        {"_id": user["_id"], "mfa.enabled": True, "mfa.passkeys.credential_id": {"$ne": credential_id}},
        {"$push": {"mfa.passkeys": passkey}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(409, "Passkey could not be added because account security changed")

    await write_audit(
        str(user["_id"]),
        "auth.passkey_registered",
        "user",
        str(user["_id"]),
        {"credential_device_type": passkey["credential_device_type"], "backed_up": passkey["backed_up"]},
    )
    return {
        "status": "PASSKEY_REGISTERED",
        "return_mode": request_doc["return_mode"],
        "passkey_count": len(_active_passkeys(updated)),
    }


@router.post("/remove")
async def remove_passkey(body: RemovePasskeyBody, ctx: dict = Depends(current_user)):
    user = ctx["user"]
    if not _staff_role_allowed(ctx.get("role")) or not _mfa_enabled(user):
        raise HTTPException(403, "Passkey settings are unavailable")
    await _verify_credential_management_totp(user, body.actor_code)
    result = await users.update_one(
        {"_id": user["_id"], "mfa.passkeys.credential_id": body.credential_id},
        {"$pull": {"mfa.passkeys": {"credential_id": body.credential_id}}},
    )
    if not result.modified_count:
        raise HTTPException(404, "Passkey not found")
    await write_audit(str(user["_id"]), "auth.passkey_removed", "user", str(user["_id"]))
    return {"status": "PASSKEY_REMOVED"}
