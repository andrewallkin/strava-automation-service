#!/usr/bin/env sh
set -eu

if [ ! -f .env ]; then
  echo ".env not found."
  exit 1
fi

docker compose --profile ngrok up -d ngrok

echo "Waiting for ngrok public URL..."
attempt=0
public_url=""
while [ "$attempt" -lt 20 ]; do
  public_url="$(curl -sf http://localhost:4040/api/tunnels 2>/dev/null \
    | grep -oE '"public_url":"https://[^"]+"' | head -1 \
    | grep -oE 'https://[^"]+' || true)"
  if [ -n "$public_url" ]; then
    break
  fi
  attempt=$((attempt + 1))
  sleep 1
done

if [ -z "$public_url" ]; then
  echo "Could not detect ngrok URL from http://localhost:4040/api/tunnels"
  exit 1
fi

echo "Detected ngrok URL: $public_url"

# Update PUBLIC_BASE_URL in .env so the running API container gets the correct redirect_uri
if grep -q "^PUBLIC_BASE_URL=" .env; then
  sed -i '' "s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=$public_url|" .env
else
  echo "PUBLIC_BASE_URL=$public_url" >> .env
fi
echo "Updated PUBLIC_BASE_URL in .env"

# Keep post-auth browser redirect pointing at localhost, not the ngrok tunnel
if grep -q "^FRONTEND_BASE_URL=" .env; then
  sed -i '' "s|^FRONTEND_BASE_URL=.*|FRONTEND_BASE_URL=http://localhost|" .env
else
  echo "FRONTEND_BASE_URL=http://localhost" >> .env
fi
echo "Set FRONTEND_BASE_URL=http://localhost"

# Restart the API container so it picks up the new PUBLIC_BASE_URL
echo "Restarting API container..."
docker compose up -d --force-recreate api
echo "Waiting for API to be healthy..."
attempt=0
while [ "$attempt" -lt 30 ]; do
  if docker compose ps api | grep -q "healthy"; then
    break
  fi
  attempt=$((attempt + 1))
  sleep 2
done

PUBLIC_BASE_URL="$public_url" ./ops/scripts/register-webhooks.sh

echo "Local webhook setup complete."
echo "Open: $public_url"
