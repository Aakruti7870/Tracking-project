"""Scheduled worker for durable order-status automation delivery.

The worker never mutates authoritative order state. It only claims already-
materialized automation events, delivers them through the existing provider
adapters, and ACKs or schedules retry/dead-letter through the durable queue.

It is intended to run as a short-lived Cloud Run Job on a recurring schedule.
Mongo lease fencing makes overlapping executions safe.
"""
from __future__ import annotations

import asyncio
import logging
import os
import socket
from collections import Counter
from dataclasses import dataclass
from uuid import uuid4

from config import settings
from automation_heartbeat import (
    STATUS_SUCCESS,
    STATUS_SUCCESS_IDLE,
    WORKER_NAME,
    record_failure,
    record_started,
    record_success,
)
from order_automation import (
    claim_order_status_events,
    complete_order_status_event,
    deliver_claimed_event,
    fail_order_status_event,
)

logger = logging.getLogger("trackmyrmc.automation_worker")


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True)
class WorkerConfig:
    batch_size: int
    max_events: int
    lease_seconds: int
    retry_after_seconds: int

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        return cls(
            batch_size=_bounded_int("AUTOMATION_WORKER_BATCH_SIZE", 10, 1, 50),
            max_events=_bounded_int("AUTOMATION_WORKER_MAX_EVENTS", 200, 1, 2000),
            lease_seconds=_bounded_int("AUTOMATION_WORKER_LEASE_SECONDS", 300, 30, 900),
            retry_after_seconds=_bounded_int("AUTOMATION_WORKER_RETRY_SECONDS", 60, 15, 3600),
        )


def _worker_id() -> str:
    host = (socket.gethostname() or "cloud-run").replace(" ", "-")[:48]
    return f"automation-worker:{host}:{uuid4().hex[:12]}"


async def _process_event(event: dict, worker_id: str, config: WorkerConfig) -> str:
    event_id = event.get("_id")
    lease_token = str(event.get("lease_token") or "")
    if event_id is None or not lease_token:
        raise RuntimeError("Claimed automation event is missing lease metadata")

    try:
        result = await deliver_claimed_event(event_id, worker_id, lease_token)
    except Exception as exc:
        # Provider payloads, credentials and response bodies are deliberately not
        # written to logs or queue errors. The exception class is enough for
        # retry/dead-letter audit and keeps sensitive provider details internal.
        released = await fail_order_status_event(
            event_id,
            worker_id,
            type(exc).__name__,
            config.retry_after_seconds,
            lease_token,
        )
        if not released:
            logger.warning("automation event lease lost before retry scheduling")
            return "lease_lost"
        logger.warning("automation event delivery deferred: %s", type(exc).__name__)
        return "retry"

    acknowledged = await complete_order_status_event(
        event_id,
        worker_id,
        result,
        lease_token,
    )
    if not acknowledged:
        logger.warning("automation event lease lost before ACK")
        return "lease_lost"
    return "completed"


async def run_worker(
    config: WorkerConfig | None = None,
    *,
    record_heartbeat: bool = True,
) -> dict[str, int]:
    """Drain currently claimable automation work up to the configured limit.

    Every invocation records a durable heartbeat: ``last_started_at`` before the
    cycle and ``last_success_at`` after a clean cycle (including an idle cycle
    when automation is disabled or there is no work). If the cycle raises, a
    failure heartbeat is recorded and the exception is re-raised so the Cloud Run
    execution fails visibly. A heartbeat write error is intentionally NOT
    swallowed, so a broken heartbeat surfaces as a failed execution instead of a
    silently healthy-looking one.
    """
    config = config or WorkerConfig.from_env()
    worker_id = _worker_id()
    execution_id = os.environ.get("CLOUD_RUN_EXECUTION") or None

    if record_heartbeat:
        await record_started(WORKER_NAME, execution_id)

    try:
        if not settings.AUTOMATION_ENABLED:
            logger.info("automation worker disabled by AUTOMATION_ENABLED")
            summary: dict[str, int] = {"disabled": 1, "processed": 0}
            cycle_status = STATUS_SUCCESS_IDLE
        else:
            outcomes: Counter[str] = Counter()
            processed = 0

            while processed < config.max_events:
                limit = min(config.batch_size, config.max_events - processed)
                claimed = await claim_order_status_events(
                    worker_id,
                    limit=limit,
                    lease_seconds=config.lease_seconds,
                )
                if not claimed:
                    break

                batch_outcomes = await asyncio.gather(
                    *(_process_event(event, worker_id, config) for event in claimed)
                )
                outcomes.update(batch_outcomes)
                processed += len(claimed)

            summary = {"processed": processed, **dict(outcomes)}
            cycle_status = STATUS_SUCCESS if processed else STATUS_SUCCESS_IDLE
            logger.info(
                "automation worker completed processed=%s completed=%s retry=%s lease_lost=%s",
                processed,
                outcomes.get("completed", 0),
                outcomes.get("retry", 0),
                outcomes.get("lease_lost", 0),
            )
    except Exception as exc:
        if record_heartbeat:
            await record_failure(WORKER_NAME, type(exc).__name__, execution_id)
        raise

    if record_heartbeat:
        await record_success(WORKER_NAME, execution_id, summary, status=cycle_status)
    return summary


async def _main() -> int:
    await run_worker()
    return 0


def main() -> int:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
    return asyncio.run(_main())


if __name__ == "__main__":
    raise SystemExit(main())
