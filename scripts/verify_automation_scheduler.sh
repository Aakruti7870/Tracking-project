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
#   - a recent Cloud Run worker execution exists
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
  RUNTIME_SA="$(gcloud run services describe "$API_SERVICE" \
    --project "$PROJECT_ID" --region "$REGION" \
    --format='value(spec.template.spec.serviceAccountName)' 2>/dev/null || true)"
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
  --format='value(metadata.name,metadata.creationTimestamp)')"
if [ -n "$RECENT" ]; then
  echo "Most recent execution: $RECENT"
  echo "AUTOMATION_WORKER_RECENT_EXECUTION=YES"
else
  echo "::error:: no Cloud Run worker executions found for ${WORKER_JOB}"
  echo "AUTOMATION_WORKER_RECENT_EXECUTION=NO"
  STATUS=1
fi

if [ "$STATUS" -eq 0 ]; then
  echo "AUTOMATION_SCHEDULER_VERIFIED=YES"
else
  echo "AUTOMATION_SCHEDULER_VERIFIED=NO"
fi
exit "$STATUS"
