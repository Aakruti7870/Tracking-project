"""Fail-closed authorization and policy primitives for the web Control Center.

This module deliberately has no knowledge of the mobile authentication flows. A
Control Center request must carry a server-side session minted by the dedicated
admin MFA endpoint; JWT role claims and an email address are never sufficient.
"""
from __future__ import annotations

from enum import Enum
from typing import Callable

from bson import ObjectId
from fastapi import Depends, HTTPException, Request, status

from database import sessions, users
from roles import Role
from security import current_user


APPROVED_CONTROL_CENTER_EMAILS = frozenset({
    "support@trackmyrmc.com",
    "yashpatel4643231@gmail.com",
    "trackmyrmcsupport@gmail.com",
})
CONTROL_CENTER_SESSION_FLAG = "control_center_mfa_authenticated"


class Permission(str, Enum):
    # Read permissions are explicit so restricted administrators cannot inherit
    # portal data merely because their role is central_admin.
    PLANT_VIEW = "plant.view"
    USER_VIEW = "user.view"
    ORDER_VIEW = "order.view"
    KYC_VIEW = "kyc.view"
    PAYMENT_VIEW = "payment.view"
    SUPPORT_VIEW = "support.view"
    AUDIT_VIEW = "audit.view"
    SYSTEM_VIEW = "system.view"
    SESSION_VIEW = "session.view"
    OWNER_VIEW = "owner.view"

    PLANT_EDIT = "plant.edit"
    PLANT_SUSPEND = "plant.suspend"
    OWNER_APPROVE = "owner.approve"
    OWNER_ASSIGN = "owner.assign"
    KYC_REVIEW = "kyc.review"
    KYC_RETRY = "kyc.retry"
    LOGIN_UNLOCK = "login.unlock"
    SESSION_REVOKE = "session.revoke"
    SUPPORT_MANAGE = "support.manage"
    PROMOTION_CREATE = "promotion.create"
    PROMOTION_ACTIVATE = "promotion.activate"
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


def is_root_control_center_user(user: dict | None) -> bool:
    user = user or {}
    return str(user.get("email") or "").strip().casefold() in APPROVED_CONTROL_CENTER_EMAILS


def is_control_center_approved_user(user: dict | None) -> bool:
    """Return whether a Central Admin identity is currently approved.

    Root identities remain code-pinned so a database mistake cannot remove every
    recovery administrator. Any approved identity can still be suspended with
    the explicit Control Center disabled flag.
    """
    user = user or {}
    if user.get("control_center_access_disabled"):
        return False
    return is_root_control_center_user(user) or bool(user.get("control_center_approved"))


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
    """Return only the caller's effective permissions.

    Code-pinned root administrators retain the legacy full-admin default when no
    explicit grants have been stored. Additional approved Central Admins fail
    closed until an explicit permission set is assigned.
    """
    authorize_control_center_context(ctx)
    user = ctx.get("user") or {}
    configured = user.get("control_center_permissions")
    if configured is None:
        return FULL_ADMIN_PERMISSIONS if is_root_control_center_user(user) else frozenset()
    return frozenset(
        Permission(value)
        for value in configured
        if value in Permission._value2member_map_
    )


async def _assert_central_admin_session_target(request: Request) -> None:
    """Fail closed if a session-revocation request targets a non-admin session.

    The Sessions workspace must never become a cross-role session revocation
    primitive. The target is independently resolved server-side from the path
    parameter and must belong to a user whose current primary role is Central
    Admin. Customer, Driver, Owner, Authority and Plant Staff sessions therefore
    remain outside this permission even if a caller somehow learns a session id.
    """
    session_id = str(request.path_params.get("session_id") or "").strip()
    if not session_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Active administrator session not found")
    target_session = await sessions.find_one(
        {"_id": session_id, "revoked": False},
        {"user_id": 1},
    )
    if not target_session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Active administrator session not found")
    target_user_id = target_session.get("user_id")
    try:
        target_oid = ObjectId(str(target_user_id))
    except Exception:
        target_oid = target_user_id
    target_user = await users.find_one(
        {"_id": target_oid, "primary_role": Role.CENTRAL_ADMIN.value},
        {"_id": 1},
    )
    if not target_user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Active administrator session not found")


def require_permission(permission: Permission) -> Callable:
    async def dependency(
        request: Request,
        ctx: dict = Depends(control_center_admin),
    ) -> dict:
        if permission not in permissions_for(ctx):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permission denied")
        if permission is Permission.SESSION_REVOKE:
            await _assert_central_admin_session_target(request)
        return ctx

    return dependency
