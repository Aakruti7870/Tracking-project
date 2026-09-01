"""Dedicated authentication surface for the privileged web portal.

The public mobile client never calls these routes. Platform administrators must
already exist, have TOTP enabled, and pass the same throttled verifier used by
staff MFA. Failed and unauthorized attempts intentionally share one response.
"""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from audit import write_audit
from database import sessions
from roles import Role
from routers import staff_mfa
from security import current_user, utcnow

router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])
PLATFORM_ROLES = {Role.AUTHORITY.value, Role.CENTRAL_ADMIN.value}


class AdminLoginBody(BaseModel):
    identifier: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=6, max_length=8)


class StepUpBody(BaseModel):
    code: str = Field(min_length=6, max_length=8)


def _failed() -> HTTPException:
    return HTTPException(401, "Authentication failed.")


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

    if result.get("role") not in PLATFORM_ROLES:
        # The shared verifier issued a session; revoke it before returning the
        # same generic response used for unknown accounts and bad MFA.
        from jwt import decode
        from config import settings

        payload = decode(result["access_token"], settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        await sessions.update_one(
            {"_id": payload["sid"]},
            {"$set": {"revoked": True, "revoked_at": utcnow(), "revoke_reason": "admin_portal_role_denied"}},
        )
        await write_audit(payload["sub"], "admin.auth.role_denied", "admin_session", payload["sid"])
        raise _failed()
    await write_audit(None, "admin.auth.succeeded", "admin_session", meta={"role": result["role"]})
    return result


def platform_admin(ctx: dict = Depends(current_user)) -> dict:
    if ctx["role"] not in PLATFORM_ROLES:
        raise HTTPException(403, "Insufficient permissions")
    return ctx


@router.post("/step-up")
async def step_up(body: StepUpBody, ctx: dict = Depends(platform_admin)):
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
    await sessions.update_one(
        {"_id": ctx["sid"], "revoked": False},
        {"$set": {"admin_step_up_at": now, "admin_step_up_expires_at": now + timedelta(minutes=5)}},
    )
    await write_audit(ctx["user_id"], "admin.step_up.succeeded", "session", ctx["sid"])
    return {"status": "verified", "expires_in": 300}


@router.post("/logout-all")
async def logout_all(ctx: dict = Depends(platform_admin)):
    now = utcnow()
    result = await sessions.update_many(
        {"user_id": ctx["user_id"], "revoked": False},
        {"$set": {"revoked": True, "revoked_at": now, "revoke_reason": "admin_logout_all"}},
    )
    await write_audit(ctx["user_id"], "admin.sessions.revoked_all", "user", ctx["user_id"], {"count": result.modified_count})
    return {"status": "ok", "revoked": result.modified_count}
