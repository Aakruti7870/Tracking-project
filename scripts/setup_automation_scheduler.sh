#!/usr/bin/env bash
#
# setup_automation_scheduler.sh — one-time operator utility that creates or
# updates the Cloud Scheduler job which triggers the TrackMyRMC automation
# worker Cloud Run Job every minute.
#
# WHY THIS EXISTS
#   GitHub CI intentionally holds ZERO Cloud Scheduler permissions. The
#   scheduler is therefore managed out of band by an authorized operator using
#   this script from an environment whose gcloud identity has the required
#   Cloud Scheduler permissions (and iam.serviceAccounts.actAs on the runtime
#   service account). This script is never run by CI.
#
# SAFETY
#   - Idempotent: detects an existing job and updates it instead of recreating.
#   - Never destroys/recreates the job.
#   - Validates project, region, worker job and runtime service account first.
#   - Mutates ONLY when explicitly run with --apply (default is a dry-run plan).
#   - Contains no secrets. The OAuth identity is a service-account EMAIL, not a key.
#
# USAGE
#   scripts/setup_automation_scheduler.sh [--apply]
#
# Override any of these via environment before running:
#   PROJECT_ID     (default: tracking-project-preview)
#   REGION         (default: asia-south1)
#   WORKER_JOB     (default: tracking-automation-worker)
#   SCHEDULER_JOB  (default: tracking-automation-worker-every-minute)
#   API_SERVICE    (default: tracking-preview-api)  # used to auto-detect RUNTIME_SA
#   RUNTIME_SA     (default: auto-detected from API_SERVICE Cloud Run service)
#
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-tracking-project-preview}"
REGION="${REGION:-asia-south1}"
WORKER_JOB="${WORKER_JOB:-tracking-automation-worker}"
SCHEDULER_JOB="${SCHEDULER_JOB:-tracking-automation-worker-every-minute}"
API_SERVICE="${API_SERVICE:-tracking-preview-api}"
RUNTIME_SA="${RUNTIME_SA:-}"
SCHEDULE="* * * * *"
TIME_ZONE="UTC"

APPLY=0
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

command -v gcloud >/dev/null 2>&1 || { echo "::error:: gcloud CLI is required" >&2; exit 1; }

echo "== Validating target =="
gcloud run jobs describe "$WORKER_JOB" --project "$PROJECT_ID" --region "$REGION" \
  --format='value(metadata.name)' >/dev/null \
  || { echo "::error:: worker Cloud Run job '$WORKER_JOB' not found; deploy it first" >&2; exit 1; }

if [ -z "$RUNTIME_SA" ]; then
  echo "Auto-detecting runtime service account from Cloud Run service '$API_SERVICE'..."
  RUNTIME_SA="$(gcloud run services describe "$API_SERVICE" \
    --project "$PROJECT_ID" --region "$REGION" \
    --format='value(spec.template.spec.serviceAccountName)')"
fi
[ -n "$RUNTIME_SA" ] || { echo "::error:: could not resolve RUNTIME_SA" >&2; exit 1; }

URI="https://run.googleapis.com/v2/projects/${PROJECT_ID}/locations/${REGION}/jobs/${WORKER_JOB}:run"

echo ""
echo "Planned Cloud Scheduler configuration:"
echo "  project             = ${PROJECT_ID}"
echo "  location            = ${REGION}"
echo "  scheduler job       = ${SCHEDULER_JOB}"
echo "  schedule            = ${SCHEDULE}"
echo "  time zone           = ${TIME_ZONE}"
echo "  target worker job   = ${WORKER_JOB}"
echo "  target uri          = ${URI}"
echo "  http method         = POST"
echo "  oauth svc account   = ${RUNTIME_SA}"
echo ""

COMMON_ARGS=(
  --project "$PROJECT_ID"
  --location "$REGION"
  --schedule "$SCHEDULE"
  --time-zone "$TIME_ZONE"
  --uri "$URI"
  --http-method POST
  --oauth-service-account-email "$RUNTIME_SA"
  --oauth-token-scope "https://www.googleapis.com/auth/cloud-platform"
  --attempt-deadline 180s
)

if gcloud scheduler jobs describe "$SCHEDULER_JOB" \
    --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then
  ACTION="update"
else
  ACTION="create"
fi
echo "Detected action: ${ACTION} (job ${ACTION}s only)"

if [ "$APPLY" -ne 1 ]; then
  echo ""
  echo "Dry run only. Re-run with --apply to ${ACTION} the scheduler."
  exit 0
fi

if [ "$ACTION" = "update" ]; then
  gcloud scheduler jobs update http "$SCHEDULER_JOB" "${COMMON_ARGS[@]}" --quiet
else
  gcloud scheduler jobs create http "$SCHEDULER_JOB" "${COMMON_ARGS[@]}" --quiet
fi

echo ""
echo "== Final verified configuration =="
gcloud scheduler jobs describe "$SCHEDULER_JOB" \
  --project "$PROJECT_ID" --location "$REGION" \
  --format='yaml(name,state,schedule,timeZone,httpTarget.uri,httpTarget.httpMethod,httpTarget.oauthToken.serviceAccountEmail)'
echo "AUTOMATION_SCHEDULER_SETUP=DONE"
