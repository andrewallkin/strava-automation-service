#!/usr/bin/env sh
set -eu

if [ ! -f .env ]; then
  echo ".env not found on VPS."
  exit 1
fi

docker compose -f docker-compose.prod.yml pull || true
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head

if [ -n "${VPS_DOMAIN:-}" ] && [ -n "${LETSENCRYPT_EMAIL:-}" ]; then
  VPS_DOMAIN="${VPS_DOMAIN}" LETSENCRYPT_EMAIL="${LETSENCRYPT_EMAIL}" ./ops/scripts/vps-enable-tls.sh
fi

echo "Deployment complete."
echo "Check services:"
docker compose -f docker-compose.prod.yml ps
