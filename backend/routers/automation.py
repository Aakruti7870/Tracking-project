"""Least-privilege pull surface for external automation workers."""
import hmac
import os
from typing import Any, Optional

from bson import ObjectId
from fastapi import APIRouter, Header, HTTPException
from pydantic import Field

from order_automation import (
    claim_order_status_events,
    complete_order_status_event,
    fail_order_status_event,
)
from validation import StrictModel

router = APIRouter(prefix="/api/automation", tags=["automation"])


def _authorize(value: Optional[str]) -> None:
    secret = os.getenv("AUTOMATION_WORKER_TOKEN", "").strip()
    supplied = (value or "").removeprefix("Bearer ").strip()
    if len(secret) < 32 or not hmac.compare_digest(secret, supplied):
        raise HTTPException(401, "Invalid automation worker credentials")


def _event_id(value: str) -> Any:
    try:
        return ObjectId(value)
    except Exception:
        return value


class ClaimBody(StrictModel):
    worker_id: str = Field(min_length=3, max_length=128)
    limit: int = Field(default=25, ge=1, le=100)
    lease_seconds: int = Field(default=120, ge=30, le=900)


class AckBody(StrictModel):
    worker_id: str = Field(min_length=3, max_length=128)
    lease_token: str = Field(min_length=16, max_length=256)
    result: dict = Field(default_factory=dict)


class FailBody(StrictModel):
    worker_id: str = Field(min_length=3, max_length=128)
    lease_token: str = Field(min_length=16, max_length=256)
    error: str = Field(min_length=1, max_length=1000)
    retry_after_seconds: int = Field(default=60, ge=15, le=3600)


@router.post("/events/claim")
async def claim(body: ClaimBody, authorization: Optional[str] = Header(default=None)):
    _authorize(authorization)
    events = await claim_order_status_events(body.worker_id, body.limit, body.lease_seconds)
    return {"events": events}


@router.post("/events/{event_id}/ack")
async def ack(event_id: str, body: AckBody, authorization: Optional[str] = Header(default=None)):
    _authorize(authorization)
    ok = await complete_order_status_event(
        _event_id(event_id), body.worker_id, body.result, body.lease_token
    )
    if not ok:
        raise HTTPException(409, "Event lease is stale or not owned by this worker")
    return {"status": "completed"}


@router.post("/events/{event_id}/fail")
async def fail(event_id: str, body: FailBody, authorization: Optional[str] = Header(default=None)):
    _authorize(authorization)
    ok = await fail_order_status_event(
        _event_id(event_id), body.worker_id, body.error,
        body.retry_after_seconds, body.lease_token,
    )
    if not ok:
        raise HTTPException(409, "Event lease is stale or not owned by this worker")
    return {"status": "recorded"}
