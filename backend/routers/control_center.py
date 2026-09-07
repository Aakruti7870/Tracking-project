"""Safe, typed Control Center APIs and constrained AI command policy."""
from __future__ import annotations

import re
from enum import Enum
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from audit import write_audit
from control_center_security import Permission, require_permission
from routers.admin_auth import _has_recent_admin_step_up
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
