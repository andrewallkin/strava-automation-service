#!/usr/bin/env sh
set -eu

if [ ! -f .env ]; then
  echo ".env not found."
  exit 1
fi

set -a
. ./.env
set +a

if [ -z "${PUBLIC_BASE_URL:-}" ]; then
  echo "PUBLIC_BASE_URL is required (for example: https://abc.ngrok-free.app)"
  exit 1
fi

if [ -z "${STRAVA_CLIENT_ID:-}" ] || [ -z "${STRAVA_CLIENT_SECRET:-}" ] || [ -z "${STRAVA_WEBHOOK_VERIFY_TOKEN:-}" ]; then
  echo "Missing STRAVA_CLIENT_ID / STRAVA_CLIENT_SECRET / STRAVA_WEBHOOK_VERIFY_TOKEN in .env"
  exit 1
fi

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_WEBHOOK_SECRET:-}" ]; then
  echo "Missing TELEGRAM_BOT_TOKEN / TELEGRAM_WEBHOOK_SECRET in .env"
  exit 1
fi

strava_callback="${PUBLIC_BASE_URL}/api/strava/webhook"
strava_redirect="${PUBLIC_BASE_URL}/api/auth/strava/callback"
telegram_webhook="${PUBLIC_BASE_URL}/api/telegram/webhook/${TELEGRAM_WEBHOOK_SECRET}"

echo "Updating Strava webhook subscription..."
# Remove previous subscriptions to avoid duplicate callbacks.
curl -sS -X GET "https://www.strava.com/api/v3/push_subscriptions?client_id=${STRAVA_CLIENT_ID}&client_secret=${STRAVA_CLIENT_SECRET}" \
  | docker run --rm -i python:3.12-alpine python -c 'import json,sys; data=json.load(sys.stdin); print("\n".join(str(x.get("id")) for x in data if isinstance(x, dict) and x.get("id")))' \
  | while IFS= read -r sub_id; do
      if [ -n "$sub_id" ]; then
        curl -sS -X DELETE "https://www.strava.com/api/v3/push_subscriptions/${sub_id}?client_id=${STRAVA_CLIENT_ID}&client_secret=${STRAVA_CLIENT_SECRET}" >/dev/null
      fi
    done

curl -sS -X POST "https://www.strava.com/api/v3/push_subscriptions" \
  -d "client_id=${STRAVA_CLIENT_ID}" \
  -d "client_secret=${STRAVA_CLIENT_SECRET}" \
  -d "callback_url=${strava_callback}" \
  -d "verify_token=${STRAVA_WEBHOOK_VERIFY_TOKEN}" >/dev/null

echo "Setting Telegram webhook..."
curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d "{\"url\":\"${telegram_webhook}\"}" >/dev/null

echo "Done."
echo "Use this Strava OAuth URL once to connect your account:"
echo "https://www.strava.com/oauth/authorize?client_id=${STRAVA_CLIENT_ID}&response_type=code&redirect_uri=${strava_redirect}&approval_prompt=force&scope=${STRAVA_SCOPES}"
