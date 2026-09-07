"""Safe, typed Control Center APIs and constrained AI command policy."""
from __future__ import annotations

import re
from enum import Enum
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import Field

from audit import write_audit
from control_center_security import (
    APPROVED_CONTROL_CENTER_EMAILS,
    Permission,
    control_center_admin,
    is_control_center_approved_user,
    is_root_control_center_user,
    permissions_for,
    require_permission,
)
from database import plant_listing_requests, plants, sessions, users
from reviewer_access import reviewer_access_state, set_reviewer_access
from roles import Role
from routers import assistant as support_routes
from routers import plant_discovery
from routers.admin_auth import _has_recent_admin_step_up
from security import as_aware, utcnow
from validation import StrictModel

router = APIRouter(prefix="/api/control-center", tags=["control-center"])


class Risk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    DENIED = "DENIED"


class CommandBody(StrictModel):
    prompt: str = Field(min_length=3, max_length=1000)
    confirmed: bool = False
    reason: str | None = Field(default=None, min_length=8, max_length=500)


class CommandDecision(StrictModel):
    command_id: str
    intent: str
    risk: Risk
    status: str
    message: str


class ReviewerAccessUpdateBody(StrictModel):
    enabled: bool
    reason: str = Field(min_length=8, max_length=500)


class AdminAccessUpdateBody(StrictModel):
    email: str = Field(min_length=5, max_length=254)
    enabled: bool = True
    permissions: list[str] | None = Field(default=None, max_length=64)
    reason: str = Field(min_length=8, max_length=500)


class SessionRevokeBody(StrictModel):
    reason: str = Field(min_length=8, max_length=500)


DENIED_PATTERNS = re.compile(
    r"(?:\b(?:secret|api[ _-]?key|environment variables?|otp(?: code)?|password|"
    r"arbitrary sql|drop table|production shell|sudo|chmod|edit permissions?|bypass)\b|"
    r"(?:^|[\s/])\.env(?:\b|$))",
    re.IGNORECASE,
)
HIGH_PATTERNS = re.compile(r"\b(suspend|unlock|revoke|activate|send|publish|deploy|merge|fix branch)\b", re.I)
MEDIUM_PATTERNS = re.compile(r"\b(create|generate|retry|campaign|proposal|incident)\b", re.I)


MODULE_PERMISSION_MAP: dict[str, Permission | None] = {
    "Dashboard": None,
    "AI Command Center": Permission.AI_DIAGNOSE,
    "Users": Permission.USER_VIEW,
    "KYC": Permission.KYC_VIEW,
    "Payments": Permission.PAYMENT_VIEW,
    "All Plants": Permission.PLANT_VIEW,
    "Orders": Permission.ORDER_VIEW,
    "Support": Permission.SUPPORT_VIEW,
    "System": Permission.SYSTEM_VIEW,
    "Onboarding": Permission.OWNER_VIEW,
    "Owners / Staff": Permission.OWNER_VIEW,
    "Reviewer Access": Permission.REVIEWER_ACCESS_MANAGE,
    "Admins": Permission.ADMIN_ACCESS_MANAGE,
    "Permissions": Permission.PERMISSIONS_MANAGE,
    "Roles": Permission.PERMISSIONS_MANAGE,
    "Sessions": Permission.SESSION_VIEW,
    "Security Overview": Permission.SESSION_VIEW,
    "Audit Logs": Permission.AUDIT_VIEW,
}


def classify_command(prompt: str) -> tuple[str, Risk]:
    normalized = " ".join(prompt.split())
    if DENIED_PATTERNS.search(normalized):
        return "prohibited_capability", Risk.DENIED
    if HIGH_PATTERNS.search(normalized):
        return "privileged_action", Risk.HIGH
    if MEDIUM_PATTERNS.search(normalized):
        return "draft_or_workflow", Risk.MEDIUM
    return "diagnostic_query", Risk.LOW


def _require_step_up(ctx: dict) -> None:
    if not _has_recent_admin_step_up(ctx.get("session") or {}):
        raise HTTPException(403, "Recent administrator verification required")


def _normalize_admin_email(value: str) -> str:
    email = value.strip().casefold()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(422, "Enter a valid administrator email")
    return email


def _validated_permissions(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    unique = list(dict.fromkeys(values))
    invalid = [value for value in unique if value not in Permission._value2member_map_]
    if invalid:
        raise HTTPException(422, f"Unknown Control Center permission: {invalid[0]}")
    return unique


async def _admin_governance_context(ctx: dict = Depends(control_center_admin)) -> dict:
    granted = permissions_for(ctx)
    if not ({Permission.ADMIN_ACCESS_MANAGE, Permission.PERMISSIONS_MANAGE} & granted):
        raise HTTPException(403, "Permission denied")
    return ctx


async def _usable_root_admin_count(*, excluding_user_id: str | None = None) -> int:
    query: dict = {
        "email": {"$in": sorted(APPROVED_CONTROL_CENTER_EMAILS)},
        "primary_role": Role.CENTRAL_ADMIN.value,
        "control_center_access_disabled": {"$ne": True},
        "status": {"$nin": ["suspended", "disabled", "deleted"]},
        "mfa.enabled": True,
        "mfa.totp_secret": {"$exists": True},
    }
    if excluding_user_id:
        try:
            from bson import ObjectId
            query["_id"] = {"$ne": ObjectId(excluding_user_id)}
        except Exception:
            query["_id"] = {"$ne": excluding_user_id}
    return await users.count_documents(query)


@router.post("/ai/commands", response_model=CommandDecision)
async def run_command(
    body: CommandBody,
    ctx: dict = Depends(require_permission(Permission.AI_DIAGNOSE)),
) -> CommandDecision:
    command_id = str(uuid4())
    intent, risk = classify_command(body.prompt)
    granted = permissions_for(ctx)
    status_value = "completed"
    message = "Diagnostic accepted. Results are limited to approved, redacted operational data sources."

    if risk is Risk.DENIED:
        status_value, message = "denied", "This capability is prohibited by the Control Center AI policy."
    elif risk in {Risk.MEDIUM, Risk.HIGH} and Permission.AI_CREATE_DRAFT not in granted:
        status_value, message = "denied", "Your Control Center permissions do not allow AI workflow or draft creation."
    elif risk is Risk.MEDIUM and not body.confirmed:
        status_value, message = "confirmation_required", "Review and confirm this draft workflow before it can continue."
    elif risk is Risk.HIGH and not (
        body.confirmed
        and _has_recent_admin_step_up(ctx.get("session") or {})
        and body.reason
    ):
        status_value, message = "mfa_confirmation_required", "A reason, fresh MFA, and explicit confirmation are required."

    await write_audit(
        ctx["user_id"],
        "control_center.ai.command",
        "ai_command",
        command_id,
        {"intent": intent, "risk": risk.value, "result": status_value},
    )
    if status_value == "denied":
        raise HTTPException(403, message)
    return CommandDecision(
        command_id=command_id,
        intent=intent,
        risk=risk,
        status=status_value,
        message=message,
    )


@router.get("/owners/requests")
async def list_owner_onboarding_requests(
    ctx: dict = Depends(require_permission(Permission.OWNER_VIEW)),
):
    del ctx
    docs = await plant_listing_requests.find({"status": "PENDING"}).sort("updated_at", -1).to_list(500)
    return {"requests": [plant_discovery._serialize(doc) for doc in docs]}


@router.get("/owners/unowned-plants")
async def list_control_center_unowned_plants(
    ctx: dict = Depends(require_permission(Permission.OWNER_VIEW)),
):
    del ctx
    docs = await plants.find({
        "$or": [{"owner_id": None}, {"owner_id": {"$exists": False}}],
        "status": {"$ne": "deleted"},
    }).sort("name", 1).to_list(500)
    return {"plants": [{
        "id": str(doc["_id"]),
        "name": doc.get("name"),
        "city": doc.get("city"),
        "address": doc.get("address"),
        "status": doc.get("status"),
    } for doc in docs]}


@router.post("/owners/requests/{request_id}/approve")
async def approve_owner_onboarding(
    request_id: str,
    ctx: dict = Depends(require_permission(Permission.OWNER_APPROVE)),
):
    _require_step_up(ctx)
    result = await plant_discovery.approve_listing(request_id, None, ctx)
    await write_audit(
        ctx["user_id"],
        "control_center.owner_onboarding.approved",
        "plant_listing_request",
        request_id,
        {"plant_id": result.get("plant_id"), "owner_id": result.get("owner_id")},
    )
    return result


@router.post("/owners/plants/{plant_id}/assign")
async def assign_owner_from_control_center(
    plant_id: str,
    body: plant_discovery.OwnerAssignmentBody,
    ctx: dict = Depends(require_permission(Permission.OWNER_ASSIGN)),
):
    _require_step_up(ctx)
    result = await plant_discovery.assign_first_owner(plant_id, body, ctx)
    await write_audit(
        ctx["user_id"],
        "control_center.owner_access.assigned",
        "plant",
        plant_id,
        {"owner_id": result.get("owner_id")},
    )
    return result


@router.get("/reviewer-access")
async def get_reviewer_access(
    ctx: dict = Depends(require_permission(Permission.REVIEWER_ACCESS_MANAGE)),
):
    state = await reviewer_access_state()
    reviewer_docs = await users.find({"play_review_account": True}, {"_id": 1}).to_list(20)
    reviewer_ids = [str(doc["_id"]) for doc in reviewer_docs]
    active_sessions = await sessions.count_documents({
        "$or": [
            {"play_review_session": True},
            {"user_id": {"$in": reviewer_ids}},
        ],
        "revoked": False,
        "expires_at": {"$gt": utcnow()},
    }) if reviewer_ids else await sessions.count_documents({
        "play_review_session": True,
        "revoked": False,
        "expires_at": {"$gt": utcnow()},
    })
    return {
        **state,
        "reviewer_accounts": len(reviewer_ids),
        "active_sessions": active_sessions,
        "roles": [Role.CUSTOMER.value, Role.PLANT_OWNER.value, Role.DRIVER.value],
        "credential_exposed": False,
        "admin": ctx["user_id"],
    }


@router.post("/reviewer-access")
async def update_reviewer_access(
    body: ReviewerAccessUpdateBody,
    ctx: dict = Depends(require_permission(Permission.REVIEWER_ACCESS_MANAGE)),
):
    _require_step_up(ctx)
    try:
        state = await set_reviewer_access(
            enabled=body.enabled,
            actor_id=ctx["user_id"],
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc))

    revoked = 0
    if not body.enabled:
        reviewer_docs = await users.find({"play_review_account": True}, {"_id": 1}).to_list(20)
        reviewer_ids = [str(doc["_id"]) for doc in reviewer_docs]
        result = await sessions.update_many(
            {
                "$or": [
                    {"play_review_session": True},
                    {"user_id": {"$in": reviewer_ids}},
                ],
                "revoked": False,
            },
            {"$set": {
                "revoked": True,
                "revoked_at": utcnow(),
                "revoke_reason": "reviewer_access_disabled",
            }},
        )
        revoked = result.modified_count

    await write_audit(
        ctx["user_id"],
        "control_center.reviewer_access.updated",
        "platform_setting",
        "google_play_reviewer_access",
        {"enabled": body.enabled, "revoked_sessions": revoked, "reason": body.reason},
    )
    return {**state, "revoked_sessions": revoked}


@router.get("/admin-access")
async def list_admin_access(ctx: dict = Depends(_admin_governance_context)):
    root_emails = sorted(APPROVED_CONTROL_CENTER_EMAILS)
    docs = await users.find({
        "$or": [
            {"email": {"$in": root_emails}},
            {"control_center_approved": True},
        ],
        "primary_role": Role.CENTRAL_ADMIN.value,
    }).sort("email", 1).to_list(100)

    by_email = {str(doc.get("email") or "").strip().casefold(): doc for doc in docs}
    all_emails = sorted(set(root_emails) | set(by_email))
    admins = []
    for email in all_emails:
        doc = by_email.get(email)
        active_sessions = 0
        if doc:
            active_sessions = await sessions.count_documents({
                "user_id": str(doc["_id"]),
                "revoked": False,
                "auth_surface": "control_center_web",
                "expires_at": {"$gt": utcnow()},
            })
        mfa = doc.get("mfa") if doc and isinstance(doc.get("mfa"), dict) else {}
        admins.append({
            "id": str(doc["_id"]) if doc else None,
            "email": email,
            "name": doc.get("name") if doc else None,
            "provisioned": bool(doc),
            "enabled": bool(doc and is_control_center_approved_user(doc)),
            "root_identity": email in APPROVED_CONTROL_CENTER_EMAILS,
            "mfa_enabled": bool(mfa.get("enabled") and mfa.get("totp_secret")),
            "mfa_enrolled_at": mfa.get("enrolled_at"),
            "status": doc.get("status", "missing") if doc else "missing",
            "permissions": doc.get("control_center_permissions") if doc else None,
            "effective_permissions": sorted(
                permission.value
                for permission in (
                    permissions_for({**ctx, "user": doc}) if doc and is_control_center_approved_user(doc) else frozenset()
                )
            ) if doc else [],
            "active_sessions": active_sessions,
            "last_privileged_login": doc.get("control_center_last_privileged_login_at") if doc else None,
            "is_current": bool(doc and str(doc["_id"]) == ctx["user_id"]),
        })

    return {
        "admins": admins,
        "available_permissions": sorted(permission.value for permission in Permission),
        "policy": {
            "requires_central_admin_role": True,
            "requires_mfa": True,
            "requires_web_session": True,
            "self_disable_blocked": True,
            "permission_changes_require_permissions_manage": True,
        },
    }


@router.post("/admin-access")
async def update_admin_access(
    body: AdminAccessUpdateBody,
    ctx: dict = Depends(_admin_governance_context),
):
    _require_step_up(ctx)
    caller_permissions = permissions_for(ctx)
    email = _normalize_admin_email(body.email)
    permissions = _validated_permissions(body.permissions)

    if permissions is not None and Permission.PERMISSIONS_MANAGE not in caller_permissions:
        raise HTTPException(403, "permissions.manage is required to change permission grants")
    if Permission.ADMIN_ACCESS_MANAGE not in caller_permissions and permissions is None:
        raise HTTPException(403, "admin_access.manage is required to change administrator access")

    user = await users.find_one({"email": email})
    if not user:
        raise HTTPException(404, "Central Admin account must be provisioned before this email can be approved")
    if user.get("primary_role") != Role.CENTRAL_ADMIN.value:
        raise HTTPException(409, "This email belongs to a non-Central-Admin account and cannot be promoted here")

    user_id = str(user["_id"])
    current_approved = is_control_center_approved_user(user)
    target_is_root = email in APPROVED_CONTROL_CENTER_EMAILS
    if body.enabled != current_approved and Permission.ADMIN_ACCESS_MANAGE not in caller_permissions:
        raise HTTPException(403, "admin_access.manage is required to enable or disable administrator access")
    if user_id == ctx["user_id"] and not body.enabled:
        raise HTTPException(409, "You cannot disable your current Control Center identity")
    if permissions is not None and user_id == ctx["user_id"] and not is_root_control_center_user(ctx.get("user")):
        raise HTTPException(409, "Restricted administrators cannot change their own permission grants")
    if body.enabled and not target_is_root and not current_approved and permissions is None:
        raise HTTPException(422, "An explicit permission set is required when approving an additional Central Admin")
    if not body.enabled and target_is_root:
        if await _usable_root_admin_count(excluding_user_id=user_id) < 1:
            raise HTTPException(409, "Cannot disable the final usable root/recovery administrator")

    before_permissions = user.get("control_center_permissions")
    update: dict = {
        "control_center_access_disabled": not body.enabled,
        "control_center_access_updated_at": utcnow(),
        "control_center_access_updated_by": ctx["user_id"],
    }
    if not target_is_root:
        update["control_center_approved"] = bool(body.enabled)
    if permissions is not None:
        update["control_center_permissions"] = permissions

    await users.update_one({"_id": user["_id"]}, {"$set": update})
    revoked = 0
    if not body.enabled or permissions is not None:
        result = await sessions.update_many(
            {"user_id": user_id, "revoked": False},
            {"$set": {
                "revoked": True,
                "revoked_at": utcnow(),
                "revoke_reason": (
                    "control_center_access_disabled" if not body.enabled else "control_center_permissions_changed"
                ),
            }},
        )
        revoked = result.modified_count

    updated = await users.find_one({"_id": user["_id"]})
    after_permissions = updated.get("control_center_permissions") if updated else None
    await write_audit(
        ctx["user_id"],
        "control_center.admin_access.updated",
        "user",
        user_id,
        {
            "email": email,
            "enabled_before": current_approved,
            "enabled_after": bool(updated and is_control_center_approved_user(updated)),
            "permissions_before": before_permissions,
            "permissions_after": after_permissions,
            "permissions_updated": permissions is not None,
            "revoked_sessions": revoked,
            "reason": body.reason,
        },
    )
    return {
        "id": user_id,
        "email": email,
        "enabled": bool(updated and is_control_center_approved_user(updated)),
        "permissions": after_permissions,
        "revoked_sessions": revoked,
    }


@router.get("/support/cases")
async def list_control_center_support_cases(
    status_filter: str | None = Query(default=None, alias="status"),
    ctx: dict = Depends(require_permission(Permission.SUPPORT_VIEW)),
):
    del ctx
    query = {}
    if status_filter:
        if status_filter not in {"OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"}:
            raise HTTPException(422, "Unknown support status")
        query["status"] = status_filter
    rows = await support_routes.support_cases.find(query).sort("created_at", -1).to_list(500)
    return {"cases": [support_routes._public_case(row, staff=True) for row in rows]}


@router.get("/support/cases/{case_id}")
async def get_control_center_support_case(
    case_id: str,
    ctx: dict = Depends(require_permission(Permission.SUPPORT_VIEW)),
):
    return await support_routes.get_support_case(case_id, ctx)


@router.post("/support/cases/{case_id}/replies")
async def reply_control_center_support_case(
    case_id: str,
    body: support_routes.CaseReplyBody,
    ctx: dict = Depends(require_permission(Permission.SUPPORT_MANAGE)),
):
    _require_step_up(ctx)
    body = support_routes.CaseReplyBody(message=body.message, internal=False)
    return await support_routes.reply_to_support_case(case_id, body, ctx)


@router.post("/support/cases/{case_id}/notes")
async def note_control_center_support_case(
    case_id: str,
    body: support_routes.CaseReplyBody,
    ctx: dict = Depends(require_permission(Permission.SUPPORT_MANAGE)),
):
    _require_step_up(ctx)
    body = support_routes.CaseReplyBody(message=body.message, internal=True)
    return await support_routes.reply_to_support_case(case_id, body, ctx)


@router.patch("/support/cases/{case_id}/status")
async def set_control_center_support_status(
    case_id: str,
    body: support_routes.CaseStatusBody,
    ctx: dict = Depends(require_permission(Permission.SUPPORT_MANAGE)),
):
    _require_step_up(ctx)
    return await support_routes.set_support_case_status(case_id, body, ctx)


@router.get("/sessions")
async def list_control_center_sessions(
    limit: int = Query(default=100, ge=1, le=200),
    ctx: dict = Depends(require_permission(Permission.SESSION_VIEW)),
):
    admin_docs = await users.find(
        {"primary_role": Role.CENTRAL_ADMIN.value},
        {"email": 1, "name": 1},
    ).to_list(200)
    by_id = {str(doc["_id"]): doc for doc in admin_docs}
    ids = list(by_id)
    rows = await sessions.find(
        {"user_id": {"$in": ids}},
        {
            "user_id": 1,
            "created_at": 1,
            "last_activity_at": 1,
            "auth_surface": 1,
            "control_center_mfa_authenticated": 1,
            "admin_portal_authenticated_at": 1,
            "expires_at": 1,
            "revoked": 1,
            "revoked_at": 1,
            "revoke_reason": 1,
            "user_agent_summary": 1,
            "device_summary": 1,
        },
    ).sort("created_at", -1).to_list(limit)
    return {"sessions": [{
        "id": str(row["_id"]),
        "administrator": (by_id.get(str(row.get("user_id"))) or {}).get("email")
            or (by_id.get(str(row.get("user_id"))) or {}).get("name")
            or str(row.get("user_id")),
        "user_id": str(row.get("user_id")),
        "created_at": row.get("created_at"),
        "last_activity_at": row.get("last_activity_at"),
        "auth_surface": row.get("auth_surface") or "unknown",
        "mfa_provenance": bool(row.get("control_center_mfa_authenticated")),
        "mfa_authenticated_at": row.get("admin_portal_authenticated_at"),
        "expires_at": row.get("expires_at"),
        "device_summary": row.get("device_summary") or row.get("user_agent_summary"),
        "revoked": bool(row.get("revoked")),
        "revoked_at": row.get("revoked_at"),
        "revoke_reason": row.get("revoke_reason"),
        "is_current": str(row["_id"]) == ctx["sid"],
    } for row in rows]}


@router.post("/sessions/{session_id}/revoke")
async def revoke_control_center_session(
    session_id: str,
    body: SessionRevokeBody,
    ctx: dict = Depends(require_permission(Permission.SESSION_REVOKE)),
):
    _require_step_up(ctx)
    now = utcnow()
    result = await sessions.update_one(
        {"_id": session_id, "revoked": False},
        {"$set": {
            "revoked": True,
            "revoked_at": now,
            "revoke_reason": "control_center_session_revoked",
        }},
    )
    if result.matched_count != 1:
        raise HTTPException(404, "Active administrator session not found")
    await write_audit(
        ctx["user_id"],
        "control_center.session.revoked",
        "session",
        session_id,
        {"reason": body.reason},
    )
    return {"status": "REVOKED", "session_id": session_id}


@router.get("/capabilities")
async def capabilities(ctx: dict = Depends(control_center_admin)):
    granted = permissions_for(ctx)
    session = ctx.get("session") or {}
    allowed_modules = sorted(
        key for key, permission in MODULE_PERMISSION_MAP.items()
        if permission is None or permission in granted
    )
    return {
        "permissions": sorted(permission.value for permission in granted),
        "session_security": {
            "auth_surface": session.get("auth_surface"),
            "control_center_mfa": bool(session.get("control_center_mfa_authenticated")),
            "recent_mfa_step_up": _has_recent_admin_step_up(session),
            "step_up_expires_at": (
                as_aware(session.get("admin_step_up_expires_at")).isoformat()
                if session.get("admin_step_up_expires_at") else None
            ),
        },
        "allowed_module_keys": allowed_modules,
        "constraints": [
            "no_arbitrary_sql",
            "no_production_shell",
            "no_secret_access",
            "no_otp_visibility",
            "no_permission_bypass",
            "no_direct_production_edits",
        ],
        "admin": ctx["user_id"],
    }
