"""Pure validation of an operator's Cloud Scheduler `describe` output.

This module is consumed ONLY by scripts/verify_automation_scheduler.sh, which an
authorized operator runs from an environment that has read-only Cloud Scheduler
access. GitHub CI never imports or runs this against Cloud Scheduler and never
prints AUTOMATION_SCHEDULER_VERIFIED=YES.

Keeping the parsing/validation here (instead of inline bash) makes it unit
testable without any cloud access.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Optional

EXPECTED_SCHEDULE = "* * * * *"
EXPECTED_TIME_ZONE = "UTC"
EXPECTED_HTTP_METHOD = "POST"


def expected_worker_uri(project_id: str, region: str, worker_job: str) -> str:
    return (
        f"https://run.googleapis.com/v2/projects/{project_id}/locations/{region}/"
        f"jobs/{worker_job}:run"
    )


@dataclass
class SchedulerCheck:
    ok: bool
    problems: list[str] = field(default_factory=list)
    parsed: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "problems": self.problems, "parsed": self.parsed}


def evaluate_scheduler(
    describe: Optional[dict],
    *,
    project_id: str,
    region: str,
    worker_job: str,
    runtime_sa: Optional[str] = None,
) -> SchedulerCheck:
    """Validate a Cloud Scheduler HTTP job describe payload against the contract."""
    describe = describe or {}
    problems: list[str] = []

    state = describe.get("state")
    if state != "ENABLED":
        problems.append(f"state must be ENABLED, found {state!r}")

    schedule = describe.get("schedule")
    if schedule != EXPECTED_SCHEDULE:
        problems.append(f"schedule must be {EXPECTED_SCHEDULE!r}, found {schedule!r}")

    time_zone = describe.get("timeZone")
    if time_zone != EXPECTED_TIME_ZONE:
        problems.append(f"timeZone must be {EXPECTED_TIME_ZONE!r}, found {time_zone!r}")

    http_target = describe.get("httpTarget") or {}
    uri = http_target.get("uri")
    expected_uri = expected_worker_uri(project_id, region, worker_job)
    if uri != expected_uri:
        problems.append(
            f"httpTarget.uri must be {expected_uri!r} (the worker job run endpoint), "
            f"found {uri!r}"
        )

    http_method = http_target.get("httpMethod")
    if http_method != EXPECTED_HTTP_METHOD:
        problems.append(
            f"httpTarget.httpMethod must be {EXPECTED_HTTP_METHOD!r}, found {http_method!r}"
        )

    oauth = http_target.get("oauthToken") or {}
    service_account = oauth.get("serviceAccountEmail")
    if not service_account:
        problems.append("httpTarget.oauthToken.serviceAccountEmail must be set")
    elif runtime_sa and service_account != runtime_sa:
        problems.append(
            f"OAuth service account must be {runtime_sa!r}, found {service_account!r}"
        )

    parsed = {
        "state": state,
        "schedule": schedule,
        "timeZone": time_zone,
        "uri": uri,
        "httpMethod": http_method,
        "serviceAccountEmail": service_account,
    }
    return SchedulerCheck(ok=not problems, problems=problems, parsed=parsed)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Cloud Scheduler describe output")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--worker-job", required=True)
    parser.add_argument("--runtime-sa", default="")
    parser.add_argument(
        "--describe-file",
        default="-",
        help="Path to gcloud scheduler describe JSON, or '-' for stdin",
    )
    args = parser.parse_args(argv)

    raw = sys.stdin.read() if args.describe_file == "-" else open(args.describe_file).read()
    describe = json.loads(raw) if raw.strip() else {}

    result = evaluate_scheduler(
        describe,
        project_id=args.project_id,
        region=args.region,
        worker_job=args.worker_job,
        runtime_sa=args.runtime_sa or None,
    )
    print(json.dumps(result.to_dict(), indent=2))
    if result.ok:
        print("AUTOMATION_SCHEDULER_VERIFIED=YES")
        return 0
    print("AUTOMATION_SCHEDULER_VERIFIED=NO")
    for problem in result.problems:
        print(f"  - {problem}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
