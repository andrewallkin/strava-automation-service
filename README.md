# Strava Automation Service

Docker-only Strava + Telegram automation with:
- FastAPI API (webhook processing in-process)
- PostgreSQL (external `postgres-net` network)
- React/TypeScript dashboard
- MCP server (same backend image)

No local dependency installs are required.

## Required Values

Copy and fill `.env` from `.env.example`:

```sh
cp .env.example .env
```

Minimum required values:
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `STRAVA_WEBHOOK_VERIFY_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `TELEGRAM_ALLOWED_USER_ID`
- `PUBLIC_BASE_URL`
- `APP_SECRET_KEY`

The Telegram webhook URL is derived from `PUBLIC_BASE_URL`:
- activity admin bot: `/api/telegram/activityadmin/webhook/{TELEGRAM_WEBHOOK_SECRET}`

## Deployment

CI (`.github/workflows/deploy.yml`) builds and pushes `api`, `frontend`, and `mcp` images to Docker Hub on every push to `main`. It does NOT touch the VPS.

The VPS control panel deploys this repo in `image` mode: it manages `.env` on the VPS, pulls the images by tag, runs migrations via `docker compose run --rm --no-deps api bash /app/run_migrations.sh`, starts `docker compose up -d`, and health-checks `/api/health`. Services: `api`, `frontend`, `mcp` on the external `postgres-net` network, with host ports `BACKEND_PORT`, `FRONTEND_PORT`, `MCP_PORT`.

## Webhook Registration

Strava push subscription and Telegram `setWebhook` are NOT registered by CI. After each deploy (or whenever `PUBLIC_BASE_URL` changes), run:

```sh
cd /srv/apps/strava-automation-service
set -a; . ./.env; set +a
./scripts/register_webhooks.sh
```

The script reads `PUBLIC_BASE_URL`, `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_WEBHOOK_VERIFY_TOKEN`, and `ACTIVITYADMIN_TELEGRAM_BOT_TOKEN`/`ACTIVITYADMIN_TELEGRAM_WEBHOOK_SECRET` (or `TELEGRAM_BOT_TOKEN`/`TELEGRAM_WEBHOOK_SECRET`) from the environment.

## Notes

- This is single-user by design.
- Run flow sends Telegram shoe picker for every run (allows changing gear even when default is pre-assigned).
- Gym/workout flow updates Strava `hide_from_home=true`.
- Dashboard polls operational APIs for pending items and recent events.
