"""Google Play reviewer-only authentication.

This bypass exists solely to satisfy Play review requirements for apps whose
normal authentication uses OTP or third-party sign-in. It is disabled by
default, guarded by a server-side fixed review OTP, limited to three review
roles and issues an ordinary revocable TrackMyRMC session.
"""
from secrets import compare_digest
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field
from validation import StrictModel

from audit import write_audit
from config import settings
from database import sessions
from play_review import play_review_user
from reviewer_access import reviewer_access_enabled
from roles import Role
from security import issue_jwt, new_session_id, utcnow

router = APIRouter(prefix="/api/auth", tags=["auth", "play-review"])

ReviewRole = Literal["customer", "plant_owner", "driver"]


class PlayReviewAccessBody(StrictModel):
    role: ReviewRole
    # The configured Play Console reviewer credential remains server-side in
    # PLAY_REVIEW_ACCESS_CODE and is never returned by the Control Center.
    access_code: str = Field(min_length=6, max_length=128)


@router.get("/play-review/status")
async def play_review_status():
    # PLAY_REVIEW_ACCESS_ENABLED remains the deployment-default gate; the
    # Control Center can override it through the audited runtime setting.
    return {"enabled": await reviewer_access_enabled()}


@router.post("/play-review")
async def play_review_access(body: PlayReviewAccessBody):
    if not await reviewer_access_enabled():
        # Do not expose whether a code is configured when review access is off.
        raise HTTPException(404, "Reviewer access is not enabled")
    if not compare_digest(body.access_code, settings.PLAY_REVIEW_ACCESS_CODE):
        raise HTTPException(401, "Invalid reviewer OTP")

    allowed = {
        Role.CUSTOMER.value,
        Role.PLANT_OWNER.value,
        Role.DRIVER.value,
    }
    if body.role not in allowed:
        raise HTTPException(403, "This role is not available for app review")

    user = await play_review_user(body.role)
    user_id = str(user["_id"])
    sid = new_session_id()
    token, expires = issue_jwt(user_id, sid, body.role)
    await sessions.insert_one({
        "_id": sid,
        "user_id": user_id,
        "role": body.role,
        "revoked": False,
        "created_at": utcnow(),
        "expires_at": expires,
        "play_review_session": True,
    })
    await write_audit(
        user_id,
        "auth.play_review_login",
        "session",
        sid,
        {"role": body.role},
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": expires.isoformat(),
        "role": body.role,
        "name": user.get("name"),
    }
