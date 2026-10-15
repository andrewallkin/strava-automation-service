#!/bin/bash
# Register Strava push subscription and Telegram webhook after a deploy.
# Run manually with the required values in the environment, e.g.:
#   PUBLIC_BASE_URL=... STRAVA_CLIENT_ID=... ... ./scripts/register_webhooks.sh
set -uo pipefail

fail=0

require_env() {
    local name="$1"
    if [ -z "${!name:-}" ]; then
        echo "Missing required env var: ${name}"
        fail=1
    fi
}

: "${ACTIVITYADMIN_TELEGRAM_BOT_TOKEN:=${TELEGRAM_BOT_TOKEN:-}}"
: "${ACTIVITYADMIN_TELEGRAM_WEBHOOK_SECRET:=${TELEGRAM_WEBHOOK_SECRET:-}}"

require_env PUBLIC_BASE_URL
require_env STRAVA_CLIENT_ID
require_env STRAVA_CLIENT_SECRET
require_env STRAVA_WEBHOOK_VERIFY_TOKEN
require_env ACTIVITYADMIN_TELEGRAM_BOT_TOKEN
require_env ACTIVITYADMIN_TELEGRAM_WEBHOOK_SECRET

if [ "${fail}" -ne 0 ]; then
    echo "Aborting: required environment variables are missing."
    exit 1
fi

echo "Registering Strava webhook"
STRAVA_CALLBACK_URL="${PUBLIC_BASE_URL}/api/strava/webhook"
echo "Callback URL: ${STRAVA_CALLBACK_URL}"
EXISTING_JSON=$(curl -sf "https://www.strava.com/api/v3/push_subscriptions?client_id=${STRAVA_CLIENT_ID}&client_secret=${STRAVA_CLIENT_SECRET}" || echo "[]")
EXISTING_ID=$(echo "${EXISTING_JSON}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'] if isinstance(d,list) and d else '')" 2>/dev/null || echo "")
EXISTING_CB=$(echo "${EXISTING_JSON}" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['callback_url'] if isinstance(d,list) and d else '')" 2>/dev/null || echo "")
if [ -n "${EXISTING_ID}" ] && [ "${EXISTING_CB}" = "${STRAVA_CALLBACK_URL}" ]; then
    echo "✓ Webhook already registered (id=${EXISTING_ID})"
else
    if [ -n "${EXISTING_ID}" ]; then
        echo "Removing stale subscription (id=${EXISTING_ID}, url=${EXISTING_CB})..."
        curl -sf -X DELETE "https://www.strava.com/api/v3/push_subscriptions/${EXISTING_ID}?client_id=${STRAVA_CLIENT_ID}&client_secret=${STRAVA_CLIENT_SECRET}" || true
    fi
    echo "Creating webhook subscription..."
    RESULT=$(curl -sf -X POST https://www.strava.com/api/v3/push_subscriptions \
        -F "client_id=${STRAVA_CLIENT_ID}" \
        -F "client_secret=${STRAVA_CLIENT_SECRET}" \
        -F "callback_url=${STRAVA_CALLBACK_URL}" \
        -F "verify_token=${STRAVA_WEBHOOK_VERIFY_TOKEN}" || echo "curl_failed")
    if echo "${RESULT}" | grep -q '"id"'; then
        echo "✓ Webhook registered: ${RESULT}"
    else
        echo "⚠️  Webhook registration may have failed: ${RESULT}"
    fi
fi

echo "Registering Telegram webhook"
TRESULT=$(curl -sf -X POST "https://api.telegram.org/bot${ACTIVITYADMIN_TELEGRAM_BOT_TOKEN}/setWebhook" \
    -H "Content-Type: application/json" \
    -d "{\"url\":\"${PUBLIC_BASE_URL}/api/telegram/activityadmin/webhook/${ACTIVITYADMIN_TELEGRAM_WEBHOOK_SECRET}\"}" || echo "curl_failed")
if echo "${TRESULT}" | grep -q '"ok":true'; then
    echo "✓ Telegram webhook registered"
else
    echo "⚠️  Telegram webhook registration may have failed: ${TRESULT}"
fi
