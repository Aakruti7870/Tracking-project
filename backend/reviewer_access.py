"""Runtime control and session issuance for isolated Google Play reviewer access.

The reviewer credential is never stored in Mongo, returned by an API, logged, or
printed. Runtime enable/disable state is server-side and every reviewer session
is marked consistently so disabling access can revoke it deterministically.
"""
from __future__ import annotations

from fastapi import HTTPException

from audit import write_audit
from config import settings
from database import db, sessions
from security import issue_jwt, new_session_id, utcnow

_REVIEWER_SETTING_ID = "google_play_reviewer_access"
_platform_settings = db.platform_settings


def reviewer_credential_supported() -> bool:
    value = settings.PLAY_REVIEW_ACCESS_CODE
    return bool(len(value) == 6 and value.isdigit())


async def reviewer_access_state() -> dict:
    doc = await _platform_settings.find_one({"_id": _REVIEWER_SETTING_ID})
    requested = bool(doc.get("enabled")) if doc else bool(settings.PLAY_REVIEW_ACCESS_ENABLED)
    configured = bool(settings.PLAY_REVIEW_ACCESS_CODE)
    supported = reviewer_credential_supported()
    migration_required = bool(configured and not supported)
    return {
        "enabled": bool(requested and supported),
        "requested_enabled": requested,
        "credential_configured": configured,
        "credential_supported": supported,
        "credential_migration_required": migration_required,
        "source": "control_center" if doc else "deployment_default",
        "updated_at": doc.get("updated_at").isoformat() if doc and doc.get("updated_at") else None,
        "updated_by": doc.get("updated_by") if doc else None,
        "reason": doc.get("reason") if doc else None,
    }


async def reviewer_access_enabled() -> bool:
    state = await reviewer_access_state()
    return bool(state["enabled"])


async def set_reviewer_access(*, enabled: bool, actor_id: str, reason: str) -> dict:
    if enabled and not reviewer_credential_supported():
        raise ValueError(
            "Google Play reviewer credential migration is required before access can be enabled"
        )
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


async def issue_reviewer_session(user: dict, role: str, login_method: str) -> dict:
    """Issue a marked reviewer session with a final runtime-switch recheck.

    The second check closes the disable/login race: if disable wins before this
    insert, login is rejected; if it wins between the first check and insert,
    this helper revokes the new session; if it wins after insert, the disable
    operation sees and revokes the marked/reviewer-user session.
    """
    if not await reviewer_access_enabled():
        raise HTTPException(404, "Reviewer access is not enabled")

    user_id = str(user["_id"])
    sid = new_session_id()
    token, expires = issue_jwt(user_id, sid, role)
    await sessions.insert_one({
        "_id": sid,
        "user_id": user_id,
        "reviewer_user_id": user_id,
        "role": role,
        "revoked": False,
        "created_at": utcnow(),
        "expires_at": expires,
        "play_review_session": True,
        "auth_method": login_method,
    })

    if not await reviewer_access_enabled():
        now = utcnow()
        await sessions.update_one(
            {"_id": sid, "user_id": user_id, "revoked": False},
            {"$set": {
                "revoked": True,
                "revoked_at": now,
                "revoke_reason": "reviewer_access_disabled_during_login",
            }},
        )
        await write_audit(
            user_id,
            "auth.play_review_login_rejected",
            "session",
            sid,
            {"role": role, "reason": "runtime_disabled"},
        )
        raise HTTPException(404, "Reviewer access is not enabled")

    await write_audit(
        user_id,
        "auth.play_review_login",
        "session",
        sid,
        {"role": role, "login_method": login_method},
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires.isoformat(),
        "role": role,
        "name": user.get("name"),
    }
