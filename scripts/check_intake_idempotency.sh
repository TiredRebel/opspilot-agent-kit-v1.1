#!/usr/bin/env bash
# P2-4 scripted proof: re-delivering the same webhook payload creates no duplicate ticket.
# Exercises the real running WF-1 workflow (not just the DB constraint already covered by
# services/rag/tests/test_idempotency.py).
set -euo pipefail

N8N_URL="${N8N_API_URL:-http://localhost:5678}"
EXTERNAL_REF="idempotency-check-$$"
PAYLOAD=$(cat <<JSON
{"external_ref":"${EXTERNAL_REF}","subject":"Idempotency check","body":"Does the Starter plan support annual billing?"}
JSON
)

echo "Posting webhook payload twice with external_ref=${EXTERNAL_REF}..."
curl -s -o /dev/null -w "first delivery:  HTTP %{http_code}\n" -X POST "${N8N_URL}/webhook/opspilot-intake" \
  -H "Content-Type: application/json" -d "${PAYLOAD}"
curl -s -o /dev/null -w "second delivery: HTTP %{http_code}\n" -X POST "${N8N_URL}/webhook/opspilot-intake" \
  -H "Content-Type: application/json" -d "${PAYLOAD}"

sleep 2

COUNT=$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-opspilot}" -d "${POSTGRES_DB:-opspilot}" -tA \
  -c "SELECT COUNT(*) FROM tickets WHERE external_ref = '${EXTERNAL_REF}';")

echo "tickets with external_ref=${EXTERNAL_REF}: ${COUNT}"
if [ "${COUNT}" -eq 1 ]; then
  echo "PASS: exactly one ticket row, duplicate delivery did not create a second ticket."
  exit 0
else
  echo "FAIL: expected exactly 1 ticket, found ${COUNT}."
  exit 1
fi
