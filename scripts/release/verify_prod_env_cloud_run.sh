#!/usr/bin/env bash

set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-inkscroller-backend}"
REGION="${REGION:-us-central1}"
PROJECT_ID="${PROJECT_ID:-inkscroller-8fa87}"
PROD_URL="${PROD_URL:-https://inkscroller-backend-806863502436.us-central1.run.app}"

print_header() {
  printf "\n== %s ==\n" "$1"
}

print_expected_output() {
  cat <<'EOF'

[EXPECTED OUTPUT REFERENCE]
- FIREBASE_PROJECT_ID=inkscroller-8fa87
- DEBUG=false
- CORS_ORIGINS must NOT be "*"
- DB_PATH should be /app/data/inkscroller.db (or approved persistent volume path)
- /ping returns HTTP 200

If these values cannot be validated with real gcloud output,
P0-B1 remains MANUAL PENDING.
EOF
}

print_copy_paste_commands() {
  cat <<EOF

[COPY-PASTE COMMANDS]
gcloud run services describe ${SERVICE_NAME} \\
  --region ${REGION} \\
  --project ${PROJECT_ID} \\
  --format="value(spec.template.spec.containers[0].env)"

gcloud run services describe ${SERVICE_NAME} \\
  --region ${REGION} \\
  --project ${PROJECT_ID} \\
  --format="value(spec.template.spec.containers[0].env)" | grep FIREBASE_PROJECT_ID

gcloud run services describe ${SERVICE_NAME} \\
  --region ${REGION} \\
  --project ${PROJECT_ID} \\
  --format="value(spec.template.spec.containers[0].env)" | grep DEBUG

gcloud run services describe ${SERVICE_NAME} \\
  --region ${REGION} \\
  --project ${PROJECT_ID} \\
  --format="value(spec.template.spec.containers[0].env)" | grep CORS_ORIGINS

gcloud run services describe ${SERVICE_NAME} \\
  --region ${REGION} \\
  --project ${PROJECT_ID} \\
  --format="value(spec.template.spec.containers[0].env)" | grep DB_PATH

curl -i "${PROD_URL}/ping"
EOF
}

print_header "P0-B1 prod env verification"
printf "service=%s region=%s project=%s\n" "$SERVICE_NAME" "$REGION" "$PROJECT_ID"

if ! command -v gcloud >/dev/null 2>&1; then
  print_header "gcloud unavailable in this environment"
  print_copy_paste_commands
  print_expected_output
  exit 2
fi

if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" >/dev/null 2>&1; then
  print_header "gcloud installed but no active auth/session"
  print_copy_paste_commands
  print_expected_output
  exit 2
fi

print_header "Cloud Run env dump"
ENV_DUMP="$(gcloud run services describe "$SERVICE_NAME" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --format="value(spec.template.spec.containers[0].env)")"

printf "%s\n" "$ENV_DUMP"

print_header "Automated checks"
PASS=true

if [[ "$ENV_DUMP" == *"FIREBASE_PROJECT_ID"*"inkscroller-8fa87"* ]]; then
  printf "[OK] FIREBASE_PROJECT_ID present and expected\n"
else
  printf "[FAIL] FIREBASE_PROJECT_ID missing or unexpected\n"
  PASS=false
fi

if [[ "$ENV_DUMP" == *"DEBUG"*"false"* ]]; then
  printf "[OK] DEBUG=false\n"
else
  printf "[FAIL] DEBUG=false not explicitly configured\n"
  PASS=false
fi

if [[ "$ENV_DUMP" == *"CORS_ORIGINS"* ]]; then
  if [[ "$ENV_DUMP" == *"CORS_ORIGINS"*"\*"* ]]; then
    printf "[FAIL] CORS_ORIGINS appears open ('*')\n"
    PASS=false
  else
    printf "[OK] CORS_ORIGINS configured and not wildcard\n"
  fi
else
  printf "[FAIL] CORS_ORIGINS not explicitly configured (runtime default may be '*')\n"
  PASS=false
fi

if [[ "$ENV_DUMP" == *"DB_PATH"*"/app/data/inkscroller.db"* ]]; then
  printf "[OK] DB_PATH points to expected path\n"
else
  printf "[FAIL] DB_PATH missing or not expected\n"
  PASS=false
fi

print_header "Ping check"
PING_RESPONSE="$(curl -is "${PROD_URL}/ping")"
printf "%s\n" "$PING_RESPONSE"

if [[ "$PING_RESPONSE" == *"HTTP/2 200"* ]] || [[ "$PING_RESPONSE" == *"HTTP/1.1 200"* ]]; then
  printf "[OK] /ping returned HTTP 200\n"
else
  printf "[FAIL] /ping did not return HTTP 200\n"
  PASS=false
fi

print_expected_output

print_header "Next step"
printf "Paste real output in docs/release/templates/p0-b1-evidence-template.md and update checklist state.\n"

if [[ "$PASS" == "true" ]]; then
  print_header "Decision"
  printf "PASS — All checks conform for P0-B1.\n"
else
  print_header "Decision"
  printf "FAIL — P0-B1 remains pending until gaps are fixed and re-verified.\n"
  exit 1
fi
