#!/usr/bin/env bash
#
# verify_automation_scheduler.sh — operator-only, read-only verification that
# the Cloud Scheduler trigger for the automation worker is configured and
# healthy. NOT run by GitHub CI (CI holds no Cloud Scheduler permissions).
#
# It confirms:
#   - the scheduler exists
#   - state == ENABLED
#   - schedule == * * * * *
#   - time zone == UTC
#   - target URI points at the correct Cloud Run worker job :run endpoint
#   - OAuth service account matches the runtime service account
#   - the newest Cloud Run worker execution is no more than 300 seconds old
#
# Run from an authorized operator/admin environment whose gcloud identity has
# read-only Cloud Scheduler + Cloud Run access.
#
# USAGE
#   scripts/verify_automation_scheduler.sh
#
# Environment overrides (same defaults as setup_automation_scheduler.sh):
#   PROJECT_ID, REGION, WORKER_JOB, SCHEDULER_JOB, API_SERVICE, RUNTIME_SA
#
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-tracking-project-preview}"
REGION="${REGION:-asia-south1}"
WORKER_JOB="${WORKER_JOB:-tracking-automation-worker}"
SCHEDULER_JOB="${SCHEDULER_JOB:-tracking-automation-worker-every-minute}"
API_SERVICE="${API_SERVICE:-tracking-preview-api}"
RUNTIME_SA="${RUNTIME_SA:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/../backend" && pwd)"

command -v gcloud >/dev/null 2>&1 || { echo "::error:: gcloud CLI is required" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "::error:: python3 is required" >&2; exit 1; }

if [ -z "$RUNTIME_SA" ]; then
  if ! RUNTIME_SA="$(gcloud run services describe "$API_SERVICE" \
    --project "$PROJECT_ID" --region "$REGION" \
    --format='value(spec.template.spec.serviceAccountName)')"; then
    echo "::error:: unable to resolve the Cloud Run runtime service account" >&2
    echo "AUTOMATION_SCHEDULER_VERIFIED=NO"
    exit 1
  fi
fi
if [ -z "${RUNTIME_SA//[[:space:]]/}" ]; then
  echo "::error:: Cloud Run runtime service account is empty" >&2
  echo "AUTOMATION_SCHEDULER_VERIFIED=NO"
  exit 1
fi

echo "== Describing scheduler '${SCHEDULER_JOB}' =="
DESCRIBE_JSON="$(gcloud scheduler jobs describe "$SCHEDULER_JOB" \
  --project "$PROJECT_ID" --location "$REGION" --format=json)"

STATUS=0
printf '%s' "$DESCRIBE_JSON" | python3 "${BACKEND_DIR}/automation_scheduler_check.py" \
  --project-id "$PROJECT_ID" \
  --region "$REGION" \
  --worker-job "$WORKER_JOB" \
  --runtime-sa "$RUNTIME_SA" \
  --describe-file - || STATUS=1

echo ""
echo "== Recent Cloud Run worker executions =="
RECENT="$(gcloud run jobs executions list \
  --project "$PROJECT_ID" --region "$REGION" --job "$WORKER_JOB" \
  --sort-by='~metadata.creationTimestamp' --limit=1 \
  --format='value(metadata.name,metadata.creationTimestamp)')" || RECENT=""
if [ -z "$RECENT" ]; then
  echo "::error:: no Cloud Run worker executions found for ${WORKER_JOB}"
  echo "AUTOMATION_WORKER_RECENT_EXECUTION=NO"
  STATUS=1
else
  echo "Most recent execution: $RECENT"
  CREATION_TIMESTAMP="${RECENT#*$'\t'}"
  if AUTOMATION_EXECUTION_TIMESTAMP="$CREATION_TIMESTAMP" python3 - <<'PY'
import datetime as dt
import os

raw = os.environ["AUTOMATION_EXECUTION_TIMESTAMP"].strip()
try:
    created = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if created.tzinfo is None:
        raise ValueError("timezone is missing")
    created = created.astimezone(dt.timezone.utc)
except (OverflowError, ValueError) as exc:
    print(f"::error:: malformed Cloud Run execution timestamp {raw!r}: {exc}")
    raise SystemExit(1)

now_override = os.environ.get("AUTOMATION_SCHEDULER_NOW_EPOCH")
now = (
    dt.datetime.fromtimestamp(float(now_override), tz=dt.timezone.utc)
    if now_override is not None
    else dt.datetime.now(dt.timezone.utc)
)
age_seconds = (now - created).total_seconds()
print(f"AUTOMATION_WORKER_EXECUTION_AGE_SECONDS={age_seconds:.3f}")
if age_seconds < 0:
    print("::error:: newest Cloud Run execution timestamp is in the future")
    raise SystemExit(1)
if age_seconds > 300:
    print("::error:: newest Cloud Run worker execution is more than 300 seconds old")
    raise SystemExit(1)
PY
  then
    echo "AUTOMATION_WORKER_RECENT_EXECUTION=YES"
  else
    echo "AUTOMATION_WORKER_RECENT_EXECUTION=NO"
    STATUS=1
  fi
fi

if [ "$STATUS" -eq 0 ]; then
  echo "AUTOMATION_SCHEDULER_VERIFIED=YES"
else
  echo "AUTOMATION_SCHEDULER_VERIFIED=NO"
fi
exit "$STATUS"
