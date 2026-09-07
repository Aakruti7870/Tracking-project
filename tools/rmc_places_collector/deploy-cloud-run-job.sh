#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-tracking-project-preview}"
REGION="${REGION:-asia-south1}"
JOB_NAME="${JOB_NAME:-rmc-places-four-state-collector}"
COLLECTOR_SA="${COLLECTOR_SA:-rmc-places-collector@${PROJECT_ID}.iam.gserviceaccount.com}"

if [[ -z "${OUTPUT_BUCKET:-}" ]]; then
  echo "OUTPUT_BUCKET is required" >&2
  exit 2
fi

gcloud iam service-accounts describe "${COLLECTOR_SA}" \
  --project="${PROJECT_ID}" >/dev/null
gcloud secrets versions list GOOGLE_PLACES_API_KEY \
  --project="${PROJECT_ID}" \
  --filter='state=ENABLED' \
  --limit=1 \
  --format='value(name)' | grep -q .
gcloud storage buckets describe "gs://${OUTPUT_BUCKET}" \
  --project="${PROJECT_ID}" >/dev/null

gcloud run jobs deploy "${JOB_NAME}" \
  --source=. \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --service-account="${COLLECTOR_SA}" \
  --set-secrets='GOOGLE_PLACES_API_KEY=GOOGLE_PLACES_API_KEY:latest' \
  --set-env-vars="OUTPUT_BUCKET=${OUTPUT_BUCKET},OUTPUT_PREFIX=rmc-places,STATES=Maharashtra|Goa|Karnataka|Gujarat,MAX_TEXT_REQUESTS=34000,MAX_DETAIL_REQUESTS=6500,RESUME=true" \
  --tasks=1 \
  --max-retries=1 \
  --task-timeout=24h \
  --cpu=2 \
  --memory=4Gi \
  --quiet

echo "COLLECTOR_DEPLOY=PASS"
echo "JOB=${JOB_NAME}"
echo "REGION=${REGION}"
