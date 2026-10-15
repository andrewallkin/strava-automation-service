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

The API registers its webhooks automatically at startup. On boot it spawns a background task that idempotently registers the Strava push subscription and the Telegram `setWebhook` (replacing a stale Strava subscription whose callback URL no longer matches `PUBLIC_BASE_URL`), and retries with backoff (30s → 1m → 5m capped) until both succeed — Strava validates the callback URL with a hub.challenge request at creation time, so registration keeps retrying until the public URL is live. Failures never block startup, and registration is skipped when `PUBLIC_BASE_URL` is unset, `APP_ENV=development`, or the relevant credentials are missing.

`scripts/register_webhooks.sh` remains as a manual fallback (e.g. after rotating `STRAVA_WEBHOOK_VERIFY_TOKEN`):

```sh
cd /srv/apps/strava-automation-service
set -a; . ./.env; set +a
./scripts/register_webhooks.sh
```

## Notes

- This is single-user by design.
- Run flow sends Telegram shoe picker for every run (allows changing gear even when default is pre-assigned).
- Gym/workout flow updates Strava `hide_from_home=true`.
- Dashboard polls operational APIs for pending items and recent events.
