"""Dedicated authentication surface for the privileged web Control Center.

The public mobile client never calls these routes. Central Administrators must
be explicitly approved, use Authenticator TOTP, and receive server-side web
provenance. Recovery can create only a short-lived MFA re-enrollment bootstrap;
it can never directly create a privileged Control Center session.
"""
from datetime import timedelta

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from pymongo import ReturnDocument
from validation import StrictModel

from audit import write_audit
from config import settings
from database import sessions, users
from roles import Role
from control_center_security import (
    CONTROL_CENTER_SESSION_FLAG,
    authorize_control_center_context,
    is_control_center_approved_user,
)
from routers import staff_auth, staff_mfa
from security import as_aware, current_user, utcnow

router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])
PLATFORM_ROLES = {Role.CENTRAL_ADMIN.value}
ADMIN_STEP_UP_SECONDS = 300
PORTAL_SESSION_FLAG = CONTROL_CENTER_SESSION_FLAG


class AdminLoginBody(StrictModel):
    identifier: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=6, max_length=8)


class AdminRecoveryBody(StrictModel):
    identifier: str = Field(min_length=3, max_length=254)
    recovery_code: str = Field(min_length=8, max_length=32)


class StepUpBody(StrictModel):
    code: str = Field(min_length=6, max_length=8)


def _failed() -> HTTPException:
    return HTTPException(401, "Authentication failed.")


def _has_recent_admin_step_up(session: dict, *, now=None) -> bool:
    """Return True only while the server-issued five-minute step-up window is active."""
    current = now or utcnow()
    verified_at = as_aware(session.get("admin_step_up_at")) if session else None
    expires_at = as_aware(session.get("admin_step_up_expires_at")) if session else None
    return bool(verified_at and expires_at and verified_at <= current and current < expires_at)


def _token_payload(access_token: str) -> dict:
    from jwt import decode

    return decode(access_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def _user_oid(value: str):
    try:
        return ObjectId(value)
    except Exception:
        return value


@router.post("/method")
async def admin_auth_method():
    # Static by design: callers cannot enumerate whether an admin email exists,
    # is approved, or has enrolled MFA.
    return {"status": "AUTHENTICATOR_REQUIRED", "method": "totp"}


@router.post("/verify-totp")
async def verify_admin_totp(body: AdminLoginBody):
    try:
        result = await staff_mfa.verify_totp_for_roles(
            staff_mfa.TotpLoginBody(identifier=body.identifier, code=body.code),
            PLATFORM_ROLES,
        )
    except HTTPException:
        await write_audit(None, "admin.auth.failed", "admin_session", meta={"result": "denied"})
        raise _failed()

    payload = _token_payload(result["access_token"])
    user = await users.find_one({"_id": _user_oid(payload["sub"])})
    if result.get("role") not in PLATFORM_ROLES or not is_control_center_approved_user(user):
        await sessions.update_one(
            {"_id": payload["sid"]},
            {"$set": {
                "revoked": True,
                "revoked_at": utcnow(),
                "revoke_reason": "admin_portal_role_denied",
            }},
        )
        await write_audit(payload["sub"], "admin.auth.role_denied", "admin_session", payload["sid"])
        raise _failed()

    now = utcnow()
    updated = await sessions.update_one(
        {"_id": payload["sid"], "user_id": payload["sub"], "revoked": False},
        {"$set": {
            PORTAL_SESSION_FLAG: True,
            "auth_surface": "control_center_web",
            "admin_portal_authenticated_at": now,
        }},
    )
    if updated.modified_count != 1:
        await write_audit(
            payload["sub"], "admin.auth.failed", "admin_session", payload["sid"],
            {"result": "session_mark_failed"},
        )
        raise _failed()
    await users.update_one(
        {"_id": user["_id"]},
        {"$set": {"control_center_last_privileged_login_at": now}},
    )
    await write_audit(
        payload["sub"], "admin.auth.succeeded", "admin_session", payload["sid"],
        {"role": result["role"], "auth_surface": "control_center_web"},
    )
    return result


@router.post("/recover")
async def recover_admin_mfa(body: AdminRecoveryBody):
    """Consume one Central Admin recovery code and start restricted re-enrollment.

    No Control Center provenance is minted here. A successful recovery revokes
    every existing administrator session, invalidates the previous TOTP and old
    recovery-code set, and returns only a short-lived MFA bootstrap token.
    """
    staff_mfa._ensure_mfa_configured()
    try:
        _value, user = await staff_mfa._resolve_staff(body.identifier, PLATFORM_ROLES)
        if not is_control_center_approved_user(user) or not staff_mfa._mfa_enabled(user):
            raise _failed()
        staff_mfa._assert_not_locked(user)
    except HTTPException as exc:
        await write_audit(None, "admin.mfa_recovery.failed", "user", meta={"result": "denied"})
        if exc.status_code == 429:
            raise
        raise _failed()

    recovery_hash = staff_mfa._recovery_hash(str(user["_id"]), body.recovery_code)
    now = utcnow()
    recovered = await users.find_one_and_update(
        {
            "_id": user["_id"],
            "mfa.enabled": True,
            "mfa.recovery_code_hashes": recovery_hash,
        },
        {
            "$set": {
                "mfa.enabled": False,
                "mfa.last_recovery_at": now,
                "mfa.failed_attempts": 0,
            },
            "$unset": {
                "mfa.totp_secret": "",
                "mfa.recovery_code_hashes": "",
                "mfa.locked_until": "",
                "mfa.pending_totp_secret": "",
                "mfa.pending_expires_at": "",
                "mfa.pending_started_at": "",
            },
        },
        return_document=ReturnDocument.AFTER,
    )
    if not recovered:
        try:
            await staff_mfa._record_failure(user)
        finally:
            await write_audit(
                str(user["_id"]), "admin.mfa_recovery.failed", "user", str(user["_id"]),
                {"result": "invalid_or_used"},
            )
        raise _failed()

    revoked = await sessions.update_many(
        {"user_id": str(user["_id"]), "revoked": False},
        {"$set": {
            "revoked": True,
            "revoked_at": now,
            "revoke_reason": "control_center_mfa_recovery",
        }},
    )
    await write_audit(
        str(user["_id"]),
        "admin.mfa_recovery.used",
        "user",
        str(user["_id"]),
        {"revoked_sessions": revoked.modified_count},
    )
    return await staff_auth._issue_mfa_bootstrap_session(recovered, recovery=True)


def platform_admin_role(ctx: dict = Depends(current_user)) -> dict:
    if ctx["role"] not in PLATFORM_ROLES:
        raise HTTPException(403, "Insufficient permissions")
    return ctx


def platform_admin(ctx: dict = Depends(platform_admin_role)) -> dict:
    """Require Central Admin plus dedicated web Control Center provenance."""
    return authorize_control_center_context(ctx)


async def require_recent_admin_step_up(ctx: dict = Depends(platform_admin)) -> dict:
    if not _has_recent_admin_step_up(ctx.get("session") or {}):
        raise HTTPException(403, "Recent administrator verification required")
    return ctx


@router.post("/step-up")
async def step_up(body: StepUpBody, ctx: dict = Depends(platform_admin)):
    """Establish fresh verification only on an existing Control Center session."""
    user = ctx["user"]
    try:
        secret = staff_mfa._decrypt_secret(staff_mfa._mfa_doc(user)["totp_secret"])
        valid = staff_mfa._verify_totp(secret, body.code)
    except (KeyError, ValueError, HTTPException):
        valid = False
    if not valid:
        await write_audit(ctx["user_id"], "admin.step_up.failed", "session", ctx["sid"])
        raise _failed()
    now = utcnow()
    updated = await sessions.update_one(
        {"_id": ctx["sid"], "user_id": ctx["user_id"], "revoked": False},
        {"$set": {
            "admin_step_up_at": now,
            "admin_step_up_expires_at": now + timedelta(seconds=ADMIN_STEP_UP_SECONDS),
        }},
    )
    if updated.modified_count != 1:
        await write_audit(
            ctx["user_id"], "admin.step_up.failed", "session", ctx["sid"],
            {"result": "session_mark_failed"},
        )
        raise _failed()
    await write_audit(ctx["user_id"], "admin.step_up.succeeded", "session", ctx["sid"])
    return {"status": "verified", "expires_in": ADMIN_STEP_UP_SECONDS}


@router.post("/logout-all")
async def logout_all(ctx: dict = Depends(platform_admin)):
    now = utcnow()
    result = await sessions.update_many(
        {"user_id": ctx["user_id"], "revoked": False},
        {"$set": {"revoked": True, "revoked_at": now, "revoke_reason": "admin_logout_all"}},
    )
    await write_audit(
        ctx["user_id"], "admin.sessions.revoked_all", "user", ctx["user_id"],
        {"count": result.modified_count},
    )
    return {"status": "ok", "revoked": result.modified_count}
