"""Durable heartbeat and health evaluation for the automation worker.

The scheduled Cloud Run worker records one heartbeat document per logical
worker in MongoDB (the project's existing durable store) so operators, a health
monitor and CI can confirm the worker is actually executing on its one-minute
schedule. This module records liveness only: no secrets, credentials or
provider payloads are ever written here.

The heartbeat is intentionally the production signal that answers "is the
Cloud Scheduler trigger actually invoking the worker?" without granting the
GitHub deploy service account any Cloud Scheduler permissions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from config import settings
from database import automation_worker_heartbeats

# Stable logical identity for the scheduled worker. This is NOT the per-execution
# worker id; it is the heartbeat document key so every execution updates the same
# row.
WORKER_NAME = "automation-worker"

# Result of the most recent automation cycle.
STATUS_SUCCESS = "SUCCESS"          # ran and had work / completed a normal cycle
STATUS_SUCCESS_IDLE = "SUCCESS_IDLE"  # ran successfully but there was nothing to do
STATUS_FAILED = "FAILED"            # the cycle raised before completing

_FAILURE_REASON_MAX = 300


class Health(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: Any) -> Optional[datetime]:
    """Coerce a stored timestamp into a timezone-aware UTC datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


async def record_started(
    worker_name: str = WORKER_NAME,
    execution_id: Optional[str] = None,
    *,
    now: Optional[datetime] = None,
) -> None:
    """Mark the beginning of a worker cycle.

    A failure to write the heartbeat is deliberately allowed to propagate so a
    broken heartbeat surfaces as a failed worker execution instead of being
    silently hidden.
    """
    now = now or _utcnow()
    set_fields: dict[str, Any] = {
        "worker_name": worker_name,
        "last_started_at": now,
        "updated_at": now,
    }
    if execution_id:
        set_fields["last_execution_id"] = execution_id
    await automation_worker_heartbeats.update_one(
        {"_id": worker_name},
        {"$set": set_fields, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )


async def record_success(
    worker_name: str = WORKER_NAME,
    execution_id: Optional[str] = None,
    summary: Optional[dict] = None,
    *,
    status: str = STATUS_SUCCESS,
    now: Optional[datetime] = None,
) -> None:
    """Record a successful automation cycle timestamp."""
    now = now or _utcnow()
    set_fields: dict[str, Any] = {
        "worker_name": worker_name,
        "last_success_at": now,
        "last_status": status,
        "last_failure_reason": None,
        "updated_at": now,
    }
    if execution_id:
        set_fields["last_execution_id"] = execution_id
    if summary is not None:
        set_fields["last_summary"] = summary
    await automation_worker_heartbeats.update_one(
        {"_id": worker_name},
        {"$set": set_fields, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )


async def record_failure(
    worker_name: str = WORKER_NAME,
    failure_reason: str = "",
    execution_id: Optional[str] = None,
    *,
    now: Optional[datetime] = None,
) -> None:
    """Record a failed automation cycle. Reason is bounded and non-sensitive."""
    now = now or _utcnow()
    set_fields: dict[str, Any] = {
        "worker_name": worker_name,
        "last_status": STATUS_FAILED,
        "last_failure_reason": str(failure_reason)[:_FAILURE_REASON_MAX],
        "last_failure_at": now,
        "updated_at": now,
    }
    if execution_id:
        set_fields["last_execution_id"] = execution_id
    await automation_worker_heartbeats.update_one(
        {"_id": worker_name},
        {"$set": set_fields, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )


async def get_heartbeat(worker_name: str = WORKER_NAME) -> Optional[dict]:
    return await automation_worker_heartbeats.find_one({"_id": worker_name})


@dataclass(frozen=True)
class HealthReport:
    status: Health
    worker_name: str
    reason: str
    age_seconds: Optional[float]
    last_success_at: Optional[datetime]
    last_started_at: Optional[datetime]
    last_status: Optional[str]
    last_failure_reason: Optional[str]
    healthy_threshold_seconds: int
    warning_threshold_seconds: int

    def to_dict(self) -> dict:
        return {
            "worker_name": self.worker_name,
            "status": self.status.value,
            "reason": self.reason,
            "age_seconds": self.age_seconds,
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
            "last_started_at": self.last_started_at.isoformat() if self.last_started_at else None,
            "last_status": self.last_status,
            "last_failure_reason": self.last_failure_reason,
            "healthy_threshold_seconds": self.healthy_threshold_seconds,
            "warning_threshold_seconds": self.warning_threshold_seconds,
        }


def evaluate_health(
    heartbeat: Optional[dict],
    *,
    now: Optional[datetime] = None,
    healthy_seconds: Optional[int] = None,
    warning_seconds: Optional[int] = None,
) -> HealthReport:
    """Pure health decision based on the age of the last successful execution.

    HEALTHY : last success within the healthy threshold.
    WARNING : last success older than healthy but within the warning threshold.
    FAILED  : last success older than the warning threshold.
    UNKNOWN : no successful execution has ever been recorded.
    """
    now = now or _utcnow()
    healthy_seconds = (
        healthy_seconds if healthy_seconds is not None
        else settings.AUTOMATION_HEARTBEAT_HEALTHY_SECONDS
    )
    warning_seconds = (
        warning_seconds if warning_seconds is not None
        else settings.AUTOMATION_HEARTBEAT_WARNING_SECONDS
    )

    heartbeat = heartbeat or {}
    worker_name = heartbeat.get("worker_name") or WORKER_NAME
    last_status = heartbeat.get("last_status")
    last_failure_reason = heartbeat.get("last_failure_reason")
    last_success = _as_aware(heartbeat.get("last_success_at"))
    last_started = _as_aware(heartbeat.get("last_started_at"))

    if last_success is None:
        return HealthReport(
            status=Health.UNKNOWN,
            worker_name=worker_name,
            reason="No successful worker execution has been recorded yet.",
            age_seconds=None,
            last_success_at=None,
            last_started_at=last_started,
            last_status=last_status,
            last_failure_reason=last_failure_reason,
            healthy_threshold_seconds=healthy_seconds,
            warning_threshold_seconds=warning_seconds,
        )

    age = (now - last_success).total_seconds()
    if age < 0:
        age = 0.0

    if age <= healthy_seconds:
        status = Health.HEALTHY
        reason = f"Last successful execution was {age:.0f}s ago."
    elif age <= warning_seconds:
        status = Health.WARNING
        reason = (
            f"Last successful execution was {age:.0f}s ago, exceeding the healthy "
            f"threshold of {healthy_seconds}s."
        )
    else:
        status = Health.FAILED
        reason = (
            f"Last successful execution was {age:.0f}s ago, exceeding the warning "
            f"threshold of {warning_seconds}s. The scheduler may not be invoking the "
            f"worker or the worker is failing."
        )

    return HealthReport(
        status=status,
        worker_name=worker_name,
        reason=reason,
        age_seconds=age,
        last_success_at=last_success,
        last_started_at=last_started,
        last_status=last_status,
        last_failure_reason=last_failure_reason,
        healthy_threshold_seconds=healthy_seconds,
        warning_threshold_seconds=warning_seconds,
    )


async def worker_health(
    worker_name: str = WORKER_NAME,
    *,
    now: Optional[datetime] = None,
) -> HealthReport:
    heartbeat = await get_heartbeat(worker_name)
    return evaluate_health(heartbeat, now=now)
