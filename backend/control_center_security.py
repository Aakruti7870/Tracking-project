"""Fail-closed authorization and policy primitives for the web Control Center.

This module deliberately has no knowledge of the mobile authentication flows. A
Control Center request must carry a server-side session minted by the dedicated
admin MFA endpoint; JWT role claims and an email address are never sufficient.
"""
from __future__ import annotations

from enum import Enum
from typing import Callable

from fastapi import Depends, HTTPException, status

from roles import Role
from security import current_user


APPROVED_CONTROL_CENTER_EMAILS = frozenset({
    "support@trackmyrmc.com",
    "yashpatel4643231@gmail.com",
    "trackmyrmcsupport@gmail.com",
})
CONTROL_CENTER_SESSION_FLAG = "control_center_mfa_authenticated"


class Permission(str, Enum):
    PLANT_VIEW = "plant.view"
    PLANT_EDIT = "plant.edit"
    PLANT_SUSPEND = "plant.suspend"
    OWNER_APPROVE = "owner.approve"
    OWNER_ASSIGN = "owner.assign"
    KYC_VIEW = "kyc.view"
    KYC_REVIEW = "kyc.review"
    KYC_RETRY = "kyc.retry"
    LOGIN_UNLOCK = "login.unlock"
    SESSION_REVOKE = "session.revoke"
    PROMOTION_CREATE = "promotion.create"
    PROMOTION_ACTIVATE = "promotion.activate"
    PAYMENT_VIEW = "payment.view"
    MARKETING_SEND = "marketing.send"
    INCIDENT_RESOLVE = "incident.resolve"
    PERMISSIONS_MANAGE = "permissions.manage"
    REVIEWER_ACCESS_MANAGE = "reviewer_access.manage"
    ADMIN_ACCESS_MANAGE = "admin_access.manage"
    AI_DIAGNOSE = "ai.diagnose"
    AI_CREATE_DRAFT = "ai.create_draft"


FULL_ADMIN_PERMISSIONS = frozenset(Permission)


def normalized_email(ctx: dict) -> str:
    return str((ctx.get("user") or {}).get("email") or "").strip().casefold()


def is_control_center_approved_user(user: dict | None) -> bool:
    """Return whether a Central Admin identity is currently approved.

    The three root identities remain code-pinned so an accidental database edit
    cannot remove every recovery path. Any approved identity can still be
    suspended from the Control Center through the explicit disabled flag.
    """
    user = user or {}
    if user.get("control_center_access_disabled"):
        return False
    email = str(user.get("email") or "").strip().casefold()
    return email in APPROVED_CONTROL_CENTER_EMAILS or bool(user.get("control_center_approved"))


def authorize_control_center_context(ctx: dict) -> dict:
    """Validate all independent privileged-access requirements."""
    session = ctx.get("session") or {}
    if ctx.get("role") != Role.CENTRAL_ADMIN.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Control Center access denied")
    if not is_control_center_approved_user(ctx.get("user") or {}):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Control Center access denied")
    if not session.get(CONTROL_CENTER_SESSION_FLAG):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Web administrator MFA session required")
    if session.get("auth_surface") != "control_center_web":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Web administrator session required")
    return ctx


async def control_center_admin(ctx: dict = Depends(current_user)) -> dict:
    return authorize_control_center_context(ctx)


def permissions_for(ctx: dict) -> frozenset[Permission]:
    authorize_control_center_context(ctx)
    configured = (ctx.get("user") or {}).get("control_center_permissions")
    if configured is None:
        return FULL_ADMIN_PERMISSIONS
    return frozenset(Permission(value) for value in configured if value in Permission._value2member_map_)


def require_permission(permission: Permission) -> Callable:
    async def dependency(ctx: dict = Depends(control_center_admin)) -> dict:
        if permission not in permissions_for(ctx):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permission denied")
        return ctx

    return dependency
