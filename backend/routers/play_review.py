"""Google Play reviewer-only authentication.

This bypass exists solely to satisfy Play review requirements for apps whose
normal authentication uses OTP or third-party sign-in. It is disabled by
default, guarded by a server-side fixed review OTP, limited to four review
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
from roles import Role
from security import issue_jwt, new_session_id, utcnow

router = APIRouter(prefix="/api/auth", tags=["auth", "play-review"])

ReviewRole = Literal["customer", "plant_owner", "authority", "driver"]


class PlayReviewAccessBody(StrictModel):
    role: ReviewRole
    # The configured Play Console reviewer credential is a reusable six-digit
    # OTP. The value remains server-side in PLAY_REVIEW_ACCESS_CODE; 123456 is
    # not hard-coded as a universal application bypass.
    access_code: str = Field(min_length=6, max_length=128)


@router.post("/play-review")
async def play_review_access(body: PlayReviewAccessBody):
    if not settings.PLAY_REVIEW_ACCESS_ENABLED:
        # Do not expose whether a code is configured when review access is off.
        raise HTTPException(404, "Reviewer access is not enabled")
    if not compare_digest(body.access_code, settings.PLAY_REVIEW_ACCESS_CODE):
        raise HTTPException(401, "Invalid reviewer OTP")

    allowed = {
        Role.CUSTOMER.value,
        Role.PLANT_OWNER.value,
        Role.AUTHORITY.value,
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
