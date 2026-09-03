"""Least-privilege pull surface for external automation workers."""
import hmac
import os
from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from fastapi import APIRouter, Header, HTTPException
from pydantic import Field

from order_automation import (
    claim_order_status_events,
    complete_order_status_event,
    fail_order_status_event,
    deliver_claimed_event,
    order_automation_attempts,
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


def _json_safe(value: Any) -> Any:
    """Convert Mongo-specific values to JSON-safe equivalents for worker responses."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
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


class DeliverBody(StrictModel):
    worker_id: str = Field(min_length=3, max_length=128)
    lease_token: str = Field(min_length=16, max_length=256)
    channels: list[str] = Field(default_factory=list, max_length=5)


class ProviderCallbackBody(StrictModel):
    provider: str = Field(min_length=2, max_length=32)
    provider_id: str = Field(min_length=1, max_length=256)
    status: str = Field(min_length=1, max_length=64)
    failure_reason: Optional[str] = Field(default=None, max_length=1000)


@router.post("/events/claim")
async def claim(body: ClaimBody, authorization: Optional[str] = Header(default=None)):
    _authorize(authorization)
    events = await claim_order_status_events(body.worker_id, body.limit, body.lease_seconds)
    return {"events": _json_safe(events)}


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


@router.post("/events/{event_id}/deliver")
async def deliver(event_id: str, body: DeliverBody, authorization: Optional[str] = Header(default=None)):
    """Run provider adapters and atomically ACK or schedule retry on the same lease."""
    _authorize(authorization)
    oid = _event_id(event_id)
    try:
        result = await deliver_claimed_event(
            oid, body.worker_id, body.lease_token, body.channels or None,
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:  # provider details and credentials never reach the caller
        failed = await fail_order_status_event(
            oid, body.worker_id, type(exc).__name__, 60, body.lease_token,
        )
        if not failed:
            raise HTTPException(409, "Event lease expired during provider delivery") from exc
        raise HTTPException(502, "Provider delivery failed and was scheduled for retry") from exc
    if not await complete_order_status_event(oid, body.worker_id, result, body.lease_token):
        raise HTTPException(409, "Event lease expired during provider delivery")
    return {"status": "completed", "result": result}


@router.post("/provider-callback")
async def provider_callback(body: ProviderCallbackBody,
                            x_automation_callback_token: Optional[str] = Header(default=None)):
    """Record normalized provider callbacks authenticated by a separate secret."""
    secret = os.getenv("AUTOMATION_CALLBACK_TOKEN", "").strip()
    if len(secret) < 32 or not hmac.compare_digest(secret, x_automation_callback_token or ""):
        raise HTTPException(401, "Invalid provider callback credentials")
    await order_automation_attempts.insert_one({
        "action": "PROVIDER_CALLBACK", "provider": body.provider,
        "provider_id": body.provider_id, "status": body.status,
        "failure_reason": body.failure_reason, "created_at": datetime.now(timezone.utc),
    })
    return {"status": "recorded"}
