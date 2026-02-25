#!/usr/bin/env sh
set -eu

if [ -z "${VPS_DOMAIN:-}" ] || [ -z "${LETSENCRYPT_EMAIL:-}" ]; then
  echo "Set VPS_DOMAIN and LETSENCRYPT_EMAIL."
  exit 1
fi

mkdir -p ops/nginx/certs ops/nginx/acme

sed "s/__DOMAIN__/${VPS_DOMAIN}/g" ops/nginx/default.prod.bootstrap.conf > ops/nginx/default.prod.conf
docker compose -f docker-compose.prod.yml up -d api frontend nginx

docker run --rm \
  -v "$(pwd)/ops/nginx/certs:/etc/letsencrypt" \
  -v "$(pwd)/ops/nginx/acme:/var/www/certbot" \
  certbot/certbot certonly \
  --webroot \
  -w /var/www/certbot \
  --email "${LETSENCRYPT_EMAIL}" \
  --agree-tos \
  --no-eff-email \
  -d "${VPS_DOMAIN}"

sed "s/__DOMAIN__/${VPS_DOMAIN}/g" ops/nginx/default.prod.ssl.conf > ops/nginx/default.prod.conf
docker compose -f docker-compose.prod.yml up -d nginx

echo "TLS is enabled for ${VPS_DOMAIN}."
