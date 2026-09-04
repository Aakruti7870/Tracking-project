"""Regression guard: the automation deploy workflow must never call Cloud
Scheduler APIs directly.

The production architecture keeps the GitHub deploy service account free of any
Cloud Scheduler permission. The scheduler is operator-managed out of band. If a
future edit reintroduces a direct `gcloud scheduler jobs create/update/run/
describe` command into the deploy workflow, this test fails so the change is a
deliberate, reviewed decision rather than an accident.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-automation-worker.yml"

FORBIDDEN = (
    "gcloud scheduler jobs create",
    "gcloud scheduler jobs update",
    "gcloud scheduler jobs run",
    "gcloud scheduler jobs describe",
)


def test_deploy_workflow_exists():
    assert WORKFLOW.is_file(), f"expected workflow at {WORKFLOW}"


def test_deploy_workflow_has_no_direct_scheduler_calls():
    text = WORKFLOW.read_text()
    hits = [pattern for pattern in FORBIDDEN if pattern in text]
    assert not hits, (
        "deploy-automation-worker.yml must not call Cloud Scheduler APIs "
        f"directly (found: {hits}). The deploy service account intentionally "
        "holds zero Cloud Scheduler permissions; use scripts/setup_automation_"
        "scheduler.sh / scripts/verify_automation_scheduler.sh instead."
    )


def test_deploy_workflow_does_not_claim_scheduler_verified():
    # CI must never assert the scheduler is verified; only an operator can.
    text = WORKFLOW.read_text()
    assert "AUTOMATION_SCHEDULER_VERIFIED=YES" not in text


def test_deploy_workflow_prints_required_markers():
    text = WORKFLOW.read_text()
    for marker in (
        "AUTOMATION_WORKER_DEPLOYED=YES",
        "AUTOMATION_WORKER_SMOKE_RUN=PASS",
        "AUTOMATION_WORKER_HEARTBEAT=PASS",
    ):
        assert marker in text, f"deploy workflow must print {marker}"
