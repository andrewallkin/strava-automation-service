#!/usr/bin/env sh
set -eu

if [ ! -f .env ]; then
  echo ".env not found. Copying from .env.example"
  cp .env.example .env
  echo "Fill in required values in .env, then run this script again."
  exit 1
fi

docker compose up -d --build postgres api frontend nginx
docker compose run --rm api alembic upgrade head

echo "Local stack is up."
echo "API health: http://localhost/api/health"
echo "UI: http://localhost/"
