"""Google Play reviewer-only authentication."""
from secrets import compare_digest
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field
from validation import StrictModel

from config import settings
from play_review import play_review_user
from reviewer_access import issue_reviewer_session, reviewer_access_enabled
from roles import Role

router = APIRouter(prefix="/api/auth", tags=["auth", "play-review"])

ReviewRole = Literal["customer", "plant_owner", "driver"]


class PlayReviewAccessBody(StrictModel):
    role: ReviewRole
    access_code: str = Field(min_length=6, max_length=128)


@router.get("/play-review/status")
async def play_review_status():
    return {"enabled": await reviewer_access_enabled()}


@router.post("/play-review")
async def play_review_access(body: PlayReviewAccessBody):
    if not await reviewer_access_enabled():
        raise HTTPException(404, "Reviewer access is not enabled")
    if not compare_digest(body.access_code, settings.PLAY_REVIEW_ACCESS_CODE):
        raise HTTPException(401, "Invalid reviewer OTP")

    allowed = {Role.CUSTOMER.value, Role.PLANT_OWNER.value, Role.DRIVER.value}
    if body.role not in allowed:
        raise HTTPException(403, "This role is not available for app review")

    user = await play_review_user(body.role)
    return await issue_reviewer_session(user, body.role, "play_review_endpoint")
