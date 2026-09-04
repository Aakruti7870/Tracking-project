# Automation worker: production safety and separation of responsibilities

The scheduled automation worker delivers already-materialized order-status
automation events. It never mutates authoritative order state. This document
describes who owns what so the system is verifiable in production without
granting the GitHub deploy service account broad Cloud permissions.

## Separation of responsibilities

| Concern | Owner | Mechanism |
| --- | --- | --- |
| Build + deploy the worker Cloud Run Job, smoke-test it | **GitHub CI** (`.github/workflows/deploy-automation-worker.yml`) | `gcloud run jobs deploy/replace/execute`, `gcloud run jobs describe`. **Zero** Cloud Scheduler permissions. |
| Trigger the worker every minute | **Cloud Scheduler** (operator-managed) | HTTP job → Cloud Run Jobs `:run` endpoint with OAuth as the runtime service account |
| Confirm the automation is actually executing | **Heartbeat** (`backend/automation_heartbeat.py`) | Worker writes `last_started_at` / `last_success_at` to MongoDB every cycle |
| Confirm scheduler configuration is correct | **Operator** (`scripts/verify_automation_scheduler.sh`) | Read-only `gcloud scheduler jobs describe` + `automation_scheduler_check.py` |

### Why the GitHub deploy service account holds no Cloud Scheduler permissions

The deploy identity must NOT have any of:
`roles/cloudscheduler.admin`, `roles/cloudscheduler.viewer`,
`roles/cloudscheduler.jobRunner`, or the granular
`cloudscheduler.jobs.get/run/create/update` permissions.

CI therefore performs **no** `gcloud scheduler jobs create/update/run/describe`
calls. A regression guard
(`backend/tests/test_deploy_workflow_scheduler_guard.py`) fails the build if any
such call is reintroduced into the deploy workflow.

## Cloud Scheduler (operator-managed)

Required configuration:

- schedule: `* * * * *`
- time zone: `UTC`
- target: the Cloud Run automation worker job `:run` endpoint
- auth: OAuth using the approved **runtime** service account (the same identity
  the production API runs as). No secrets are stored in the repo or workflow.

Create/update it once from an authorized operator environment:

```bash
# dry run (prints the plan, mutates nothing)
scripts/setup_automation_scheduler.sh

# apply (create or update; idempotent, never destroys/recreates)
scripts/setup_automation_scheduler.sh --apply
```

Verify it any time (read-only):

```bash
scripts/verify_automation_scheduler.sh
```

## Heartbeat + health

Every worker cycle records a heartbeat in the `automation_worker_heartbeats`
collection:

- `worker_name`
- `last_started_at`
- `last_success_at`
- `last_status` (`SUCCESS`, `SUCCESS_IDLE`, `FAILED`)
- `last_execution_id` (Cloud Run execution id when available)
- `last_failure_reason` (bounded, non-sensitive class name only)

A heartbeat write failure is intentionally **not** swallowed: it fails the
worker execution so the problem is visible rather than masked.

Health thresholds (configurable in `backend/config.py`):

- `HEALTHY`: last success ≤ `AUTOMATION_HEARTBEAT_HEALTHY_SECONDS` (default 180s)
- `WARNING`: between healthy and `AUTOMATION_HEARTBEAT_WARNING_SECONDS` (default 300s)
- `FAILED`: older than the warning threshold
- `UNKNOWN`: no successful execution has ever been recorded

Check health two ways:

```bash
# CLI monitor: exit 0 for HEALTHY/WARNING, exit 1 for FAILED/UNKNOWN
python backend/automation_health.py
```

```
# Authenticated, read-only API (uses the existing AUTOMATION_WORKER_TOKEN):
GET /api/automation/worker-health
Authorization: Bearer <AUTOMATION_WORKER_TOKEN>
```

## Recovery: heartbeat is stale (WARNING/FAILED) or UNKNOWN

Work through these in order; each isolates one failure mode without hiding it:

1. **Scheduler not triggering** — run `scripts/verify_automation_scheduler.sh`.
   If the job is missing, disabled, on the wrong schedule, points at the wrong
   worker job, or uses the wrong OAuth service account, fix it with
   `scripts/setup_automation_scheduler.sh --apply`.
2. **Scheduler triggers but invocation fails** — check the Cloud Scheduler job's
   last run result and Cloud Run job executions. A `PERMISSION_DENIED` here means
   the scheduler's OAuth service account lacks `run.jobs.run` on the worker job
   (grant it to the runtime SA, not to the GitHub deploy SA).
3. **Worker executes but fails** — inspect the most recent Cloud Run execution
   logs and the heartbeat `last_failure_reason` / `last_status=FAILED`.
4. **Heartbeat write failing** — a worker that runs but cannot persist its
   heartbeat exits non-zero; check MongoDB connectivity/credentials in the worker
   runtime environment. The API `/api/automation/worker-health` and the CLI
   monitor will report `UNKNOWN` until a successful cycle is recorded.

Never "fix" a stale heartbeat by bypassing failures (`|| true`), by marking a
failed verification as successful, or by making the scheduler public.
