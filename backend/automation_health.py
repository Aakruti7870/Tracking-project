"""Operator/monitoring health check for the automation worker heartbeat.

This is a production-safe, read-only monitor. It reads the worker heartbeat from
the existing MongoDB store and reports HEALTHY / WARNING / FAILED / UNKNOWN based
on how recently the worker last succeeded. It never mutates order state, calls
Cloud Scheduler, or prints secrets.

Exit codes (so it can drive an alert):
    0  HEALTHY or WARNING
    1  FAILED or UNKNOWN (stale / never-run worker)

Usage:
    python automation_health.py [worker_name]

Run it from an operator/monitoring environment that has the production MongoDB
connection configured (same environment contract as the API service).
"""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Optional

from automation_heartbeat import Health, HealthReport, WORKER_NAME, worker_health

# A stale or never-run worker must fail loudly. A WARNING is surfaced but does
# not hard-fail, so a single delayed minute does not page an operator.
FAIL_STATUSES = frozenset({Health.FAILED, Health.UNKNOWN})


def monitor_exit_code(status: Health) -> int:
    """Testable mapping from health status to process exit code."""
    return 1 if status in FAIL_STATUSES else 0


async def _collect(worker_name: str) -> HealthReport:
    return await worker_health(worker_name)


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    worker_name = argv[0] if argv else WORKER_NAME
    report = asyncio.run(_collect(worker_name))
    print(json.dumps(report.to_dict(), default=str))
    print(f"AUTOMATION_WORKER_HEALTH={report.status.value}")
    return monitor_exit_code(report.status)


if __name__ == "__main__":
    raise SystemExit(main())
