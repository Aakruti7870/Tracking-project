"""Safe, typed Control Center APIs and constrained AI command policy."""
from __future__ import annotations

import re
from enum import Enum
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from audit import write_audit
from control_center_security import (
    APPROVED_CONTROL_CENTER_EMAILS,
    Permission,
    is_control_center_approved_user,
    require_permission,
)
from database import sessions, users
from reviewer_access import reviewer_access_state, set_reviewer_access
from roles import Role
from routers.admin_auth import _has_recent_admin_step_up
from security import utcnow
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


DENIED_PATTERNS = re.compile(
    r"\b(secret|api[ _-]?key|environment variables?|\.env|otp(?: code)?|password|"
    r"arbitrary sql|drop table|production shell|sudo|chmod|edit permissions?|bypass)\b",
    re.IGNORECASE,
)
HIGH_PATTERNS = re.compile(r"\b(suspend|unlock|revoke|activate|send|publish|deploy|merge|fix branch)\b", re.I)
MEDIUM_PATTERNS = re.compile(r"\b(create|generate|retry|campaign|proposal|incident)\b", re.I)


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


@router.post("/ai/commands", response_model=CommandDecision)
async def run_command(
    body: CommandBody,
    ctx: dict = Depends(require_permission(Permission.AI_DIAGNOSE)),
) -> CommandDecision:
    command_id = str(uuid4())
    intent, risk = classify_command(body.prompt)
    status_value = "completed"
    message = "Diagnostic accepted. Results are limited to approved, redacted operational data sources."

    if risk is Risk.DENIED:
        status_value, message = "denied", "This capability is prohibited by the Control Center AI policy."
    elif risk is Risk.MEDIUM and not body.confirmed:
        status_value, message = "confirmation_required", "Review and confirm this draft workflow before it can continue."
    elif risk is Risk.HIGH and not (body.confirmed and _has_recent_admin_step_up(ctx.get("session") or {}) and body.reason):
        status_value, message = "mfa_confirmation_required", "A reason, fresh MFA, and explicit confirmation are required."

    await write_audit(
        ctx["user_id"],
        "control_center.ai.command",
        "ai_command",
        command_id,
        {"intent": intent, "risk": risk.value, "result": status_value},
    )
    if risk is Risk.DENIED:
        raise HTTPException(403, message)
    return CommandDecision(command_id=command_id, intent=intent, risk=risk, status=status_value, message=message)


@router.get("/reviewer-access")
async def get_reviewer_access(
    ctx: dict = Depends(require_permission(Permission.REVIEWER_ACCESS_MANAGE)),
):
    state = await reviewer_access_state()
    reviewer_accounts = await users.count_documents({"play_review_account": True})
    active_sessions = await sessions.count_documents({"play_review_session": True, "revoked": False})
    return {
        **state,
        "reviewer_accounts": reviewer_accounts,
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
        if reviewer_ids:
            result = await sessions.update_many(
                {"user_id": {"$in": reviewer_ids}, "revoked": False},
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
async def list_admin_access(
    ctx: dict = Depends(require_permission(Permission.ADMIN_ACCESS_MANAGE)),
):
    root_emails = sorted(APPROVED_CONTROL_CENTER_EMAILS)
    docs = await users.find(
        {
            "$or": [
                {"email": {"$in": root_emails}},
                {"control_center_approved": True},
            ],
            "primary_role": Role.CENTRAL_ADMIN.value,
        }
    ).sort("email", 1).to_list(100)

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
            "status": doc.get("status", "missing") if doc else "missing",
            "permissions": doc.get("control_center_permissions") if doc else None,
            "active_sessions": active_sessions,
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
        },
    }


@router.post("/admin-access")
async def update_admin_access(
    body: AdminAccessUpdateBody,
    ctx: dict = Depends(require_permission(Permission.ADMIN_ACCESS_MANAGE)),
):
    _require_step_up(ctx)
    email = _normalize_admin_email(body.email)
    permissions = _validated_permissions(body.permissions)
    user = await users.find_one({"email": email})
    if not user:
        raise HTTPException(404, "Central Admin account must be provisioned before this email can be approved")
    if user.get("primary_role") != Role.CENTRAL_ADMIN.value:
        raise HTTPException(409, "This email belongs to a non-Central-Admin account and cannot be promoted here")
    user_id = str(user["_id"])
    if user_id == ctx["user_id"] and not body.enabled:
        raise HTTPException(409, "You cannot disable your current Control Center identity")

    update: dict = {
        "control_center_access_disabled": not body.enabled,
        "control_center_access_updated_at": utcnow(),
        "control_center_access_updated_by": ctx["user_id"],
    }
    if email not in APPROVED_CONTROL_CENTER_EMAILS:
        update["control_center_approved"] = bool(body.enabled)
    if permissions is not None:
        update["control_center_permissions"] = permissions

    await users.update_one({"_id": user["_id"]}, {"$set": update})
    revoked = 0
    if not body.enabled:
        result = await sessions.update_many(
            {"user_id": user_id, "revoked": False},
            {"$set": {
                "revoked": True,
                "revoked_at": utcnow(),
                "revoke_reason": "control_center_access_disabled",
            }},
        )
        revoked = result.modified_count

    await write_audit(
        ctx["user_id"],
        "control_center.admin_access.updated",
        "user",
        user_id,
        {
            "email": email,
            "enabled": body.enabled,
            "permissions_updated": permissions is not None,
            "revoked_sessions": revoked,
            "reason": body.reason,
        },
    )
    updated = await users.find_one({"_id": user["_id"]})
    return {
        "id": user_id,
        "email": email,
        "enabled": is_control_center_approved_user(updated),
        "permissions": updated.get("control_center_permissions") if updated else None,
        "revoked_sessions": revoked,
    }


@router.get("/capabilities")
async def capabilities(ctx: dict = Depends(require_permission(Permission.PLANT_VIEW))):
    return {
        "permissions": sorted(permission.value for permission in Permission),
        "constraints": [
            "no_arbitrary_sql", "no_production_shell", "no_secret_access",
            "no_otp_visibility", "no_permission_bypass", "no_direct_production_edits",
        ],
        "admin": ctx["user_id"],
    }
