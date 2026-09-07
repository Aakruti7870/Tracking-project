"""Runtime control for isolated Google Play reviewer access.

The deployment flag remains the default only. Once a Super Admin explicitly
changes reviewer access from the Control Center, the server-side runtime setting
becomes authoritative. The reviewer credential itself is never stored in Mongo
or returned by an API.
"""
from __future__ import annotations

from config import settings
from database import db
from security import utcnow

_REVIEWER_SETTING_ID = "google_play_reviewer_access"
_platform_settings = db.platform_settings


async def reviewer_access_state() -> dict:
    doc = await _platform_settings.find_one({"_id": _REVIEWER_SETTING_ID})
    enabled = bool(doc.get("enabled")) if doc else bool(settings.PLAY_REVIEW_ACCESS_ENABLED)
    configured = bool(settings.PLAY_REVIEW_ACCESS_CODE)
    return {
        "enabled": enabled and configured,
        "requested_enabled": enabled,
        "credential_configured": configured,
        "source": "control_center" if doc else "deployment_default",
        "updated_at": doc.get("updated_at").isoformat() if doc and doc.get("updated_at") else None,
        "updated_by": doc.get("updated_by") if doc else None,
        "reason": doc.get("reason") if doc else None,
    }


async def reviewer_access_enabled() -> bool:
    state = await reviewer_access_state()
    return bool(state["enabled"])


async def set_reviewer_access(*, enabled: bool, actor_id: str, reason: str) -> dict:
    if enabled and not settings.PLAY_REVIEW_ACCESS_CODE:
        raise ValueError("Google Play reviewer credential is not configured")
    now = utcnow()
    await _platform_settings.update_one(
        {"_id": _REVIEWER_SETTING_ID},
        {"$set": {
            "enabled": bool(enabled),
            "updated_at": now,
            "updated_by": actor_id,
            "reason": reason.strip(),
        }},
        upsert=True,
    )
    return await reviewer_access_state()
