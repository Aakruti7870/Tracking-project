"""Dedicated authentication surface for the privileged web portal.

The public mobile client never calls these routes. Platform administrators must
already exist, have TOTP enabled, and pass the same throttled verifier used by
staff MFA. Failed and unauthorized attempts intentionally share one response.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from validation import StrictModel

from audit import write_audit
from config import settings
from database import sessions
from roles import Role
from routers import staff_mfa
from security import as_aware, current_user, utcnow

router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])
PLATFORM_ROLES = {Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value}
ADMIN_STEP_UP_SECONDS = 300
PORTAL_SESSION_FLAG = "admin_portal_totp_authenticated"


class AdminLoginBody(StrictModel):
    identifier: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=6, max_length=8)


class StepUpBody(StrictModel):
    code: str = Field(min_length=6, max_length=8)


def _failed() -> HTTPException:
    return HTTPException(401, "Authentication failed.")


def _has_recent_admin_step_up(session: dict, *, now=None) -> bool:
    """Return True only while the server-issued five-minute step-up window is active."""
    current = now or utcnow()
    verified_at = as_aware(session.get("admin_step_up_at")) if session else None
    expires_at = as_aware(session.get("admin_step_up_expires_at")) if session else None
    return bool(
        verified_at
        and expires_at
        and verified_at <= current
        and current < expires_at
    )


def _token_payload(access_token: str) -> dict:
    from jwt import decode

    return decode(access_token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


@router.post("/method")
async def admin_auth_method():
    # Deliberately static: callers cannot use this endpoint to enumerate admins.
    return {"status": "AUTHENTICATOR_REQUIRED", "method": "totp"}


@router.post("/verify-totp")
async def verify_admin_totp(body: AdminLoginBody):
    try:
        result = await staff_mfa.verify_staff_totp(
            staff_mfa.TotpLoginBody(identifier=body.identifier, code=body.code)
        )
    except HTTPException:
        await write_audit(None, "admin.auth.failed", "admin_session", meta={"result": "denied"})
        raise _failed()

    payload = _token_payload(result["access_token"])
    if result.get("role") not in PLATFORM_ROLES:
        # The shared verifier issued a session; revoke it before returning the
        # same generic response used for unknown accounts and bad MFA.
        await sessions.update_one(
            {"_id": payload["sid"]},
            {"$set": {"revoked": True, "revoked_at": utcnow(), "revoke_reason": "admin_portal_role_denied"}},
        )
        await write_audit(payload["sub"], "admin.auth.role_denied", "admin_session", payload["sid"])
        raise _failed()

    # Mark authentication provenance on the server-side session. Role alone is
    # never enough to access the privileged portal: sessions minted by mobile,
    # Google exchange, staff OTP, or any other auth surface do not receive this
    # flag and therefore fail closed at platform_admin().
    updated = await sessions.update_one(
        {"_id": payload["sid"], "user_id": payload["sub"], "revoked": False},
        {"$set": {PORTAL_SESSION_FLAG: True, "admin_portal_authenticated_at": utcnow()}},
    )
    if updated.modified_count != 1:
        await write_audit(payload["sub"], "admin.auth.failed", "admin_session", payload["sid"], {"result": "session_mark_failed"})
        raise _failed()

    await write_audit(payload["sub"], "admin.auth.succeeded", "admin_session", payload["sid"], {"role": result["role"]})
    return result


def platform_admin_role(ctx: dict = Depends(current_user)) -> dict:
    """Require a platform-administrator role without changing existing step-up flows."""
    if ctx["role"] not in PLATFORM_ROLES:
        raise HTTPException(403, "Insufficient permissions")
    return ctx


def platform_admin(ctx: dict = Depends(platform_admin_role)) -> dict:
    """Require platform role plus dedicated admin-portal TOTP provenance."""
    if not (ctx.get("session") or {}).get(PORTAL_SESSION_FLAG):
        raise HTTPException(403, "Privileged portal authentication required")
    return ctx


async def require_recent_admin_step_up(ctx: dict = Depends(platform_admin_role)) -> dict:
    """Require the existing server-issued recent admin step-up marker.

    This dependency is shared by sensitive operations outside the read-only
    admin portal. Portal routes still use platform_admin(), so portal access
    continues to require dedicated TOTP provenance.
    """
    if not _has_recent_admin_step_up(ctx.get("session") or {}):
        raise HTTPException(403, "Recent administrator verification required")
    return ctx


@router.post("/step-up")
async def step_up(body: StepUpBody, ctx: dict = Depends(platform_admin_role)):
    """Establish recent admin verification for any authenticated platform admin.

    Step-up is also used by sensitive operations outside the dedicated portal,
    so establishing it must not require portal-session provenance. Portal reads
    remain protected by platform_admin().
    """
    user = ctx["user"]
    try:
        secret = staff_mfa._decrypt_secret(staff_mfa._mfa_doc(user)["totp_secret"])
        valid = staff_mfa._verify_totp(secret, body.code)
    except (KeyError, ValueError):
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
        await write_audit(ctx["user_id"], "admin.step_up.failed", "session", ctx["sid"], {"result": "session_mark_failed"})
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
    await write_audit(ctx["user_id"], "admin.sessions.revoked_all", "user", ctx["user_id"], {"count": result.modified_count})
    return {"status": "ok", "revoked": result.modified_count}
