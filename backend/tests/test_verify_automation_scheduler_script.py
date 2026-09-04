"""Regression tests for the operator-only scheduler verification script."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import datetime as dt

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "verify_automation_scheduler.sh"
NOW_EPOCH = 2_000_000_000


def _run_verifier(
    tmp_path: Path,
    execution: str,
    *,
    runtime_sa: str = "runtime@example.test",
    scheduler_sa: str = "runtime@example.test",
    resolved_runtime_sa: str = "runtime@example.test",
    runtime_lookup_fails: bool = False,
) -> subprocess.CompletedProcess[str]:
    gcloud = tmp_path / "gcloud"
    scheduler = {
        "state": "ENABLED",
        "schedule": "* * * * *",
        "timeZone": "UTC",
        "httpTarget": {
            "uri": (
                "https://run.googleapis.com/v2/projects/test-project/locations/"
                "test-region/jobs/test-worker:run"
            ),
            "httpMethod": "POST",
            "oauthToken": {"serviceAccountEmail": scheduler_sa},
        },
    }
    gcloud.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$*" == *"run services describe"* ]]; then\n'
        "  if [ \"$FAKE_RUNTIME_LOOKUP_FAILS\" = 1 ]; then exit 1; fi\n"
        "  printf '%s' \"$FAKE_RUNTIME_SA\"\n"
        'elif [[ "$*" == *"scheduler jobs describe"* ]]; then\n'
        f"  printf '%s\\n' '{json.dumps(scheduler)}'\n"
        'elif [[ "$*" == *"run jobs executions list"* ]]; then\n'
        "  printf '%s' \"$FAKE_EXECUTION\"\n"
        "else\n"
        "  exit 64\n"
        "fi\n"
    )
    gcloud.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "PROJECT_ID": "test-project",
        "REGION": "test-region",
        "WORKER_JOB": "test-worker",
        "RUNTIME_SA": runtime_sa,
        "FAKE_RUNTIME_SA": resolved_runtime_sa,
        "FAKE_RUNTIME_LOOKUP_FAILS": "1" if runtime_lookup_fails else "0",
        "AUTOMATION_SCHEDULER_NOW_EPOCH": str(NOW_EPOCH),
        "FAKE_EXECUTION": execution,
    }
    return subprocess.run(
        [str(SCRIPT)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize("age", [0, 299, 300])
def test_fresh_and_boundary_executions_pass(tmp_path: Path, age: int):
    timestamp = dt.datetime.fromtimestamp(
        NOW_EPOCH - age, tz=dt.timezone.utc
    ).isoformat()
    result = _run_verifier(tmp_path, f"execution-1\t{timestamp}")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "AUTOMATION_WORKER_RECENT_EXECUTION=YES" in result.stdout
    assert "AUTOMATION_SCHEDULER_VERIFIED=YES" in result.stdout


@pytest.mark.parametrize(
    "execution",
    [
        pytest.param("", id="no-execution"),
        pytest.param("execution-1\tnot-a-timestamp", id="malformed-timestamp"),
    ],
)
def test_missing_or_malformed_execution_fails(tmp_path: Path, execution: str):
    result = _run_verifier(tmp_path, execution)

    assert result.returncode != 0
    assert "AUTOMATION_WORKER_RECENT_EXECUTION=NO" in result.stdout
    assert result.stdout.rstrip().endswith("AUTOMATION_SCHEDULER_VERIFIED=NO")


def test_execution_older_than_300_seconds_fails(tmp_path: Path):
    timestamp = dt.datetime.fromtimestamp(
        NOW_EPOCH - 301, tz=dt.timezone.utc
    ).isoformat()
    result = _run_verifier(tmp_path, f"execution-1\t{timestamp}")

    assert result.returncode != 0
    assert "more than 300 seconds old" in result.stdout
    assert result.stdout.rstrip().endswith("AUTOMATION_SCHEDULER_VERIFIED=NO")


def test_missing_resolved_runtime_service_account_fails(tmp_path: Path):
    result = _run_verifier(tmp_path, "", runtime_sa="", resolved_runtime_sa="")

    assert result.returncode != 0
    assert "runtime service account is empty" in result.stderr
    assert "AUTOMATION_SCHEDULER_VERIFIED=NO" in result.stdout


def test_failed_runtime_service_account_lookup_fails(tmp_path: Path):
    result = _run_verifier(tmp_path, "", runtime_sa="", runtime_lookup_fails=True)

    assert result.returncode != 0
    assert "unable to resolve the Cloud Run runtime service account" in result.stderr
    assert "AUTOMATION_SCHEDULER_VERIFIED=NO" in result.stdout


def test_wrong_scheduler_oauth_service_account_fails(tmp_path: Path):
    timestamp = dt.datetime.fromtimestamp(NOW_EPOCH, tz=dt.timezone.utc).isoformat()
    result = _run_verifier(
        tmp_path,
        f"execution-1\t{timestamp}",
        scheduler_sa="wrong@example.test",
    )

    assert result.returncode != 0
    assert "OAuth service account must be 'runtime@example.test'" in result.stdout
    assert result.stdout.rstrip().endswith("AUTOMATION_SCHEDULER_VERIFIED=NO")
