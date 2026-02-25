# Strava Automation Service

Docker-only Strava + Telegram automation with:
- FastAPI API (webhook processing in-process)
- PostgreSQL
- React/TypeScript dashboard
- Nginx reverse proxy

No local dependency installs are required beyond Docker/Compose.

## 1) Required Values

Copy and fill `.env` from `.env.example`:

```sh
cp .env.example .env
```

Minimum required values:
- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `STRAVA_WEBHOOK_VERIFY_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `TELEGRAM_ALLOWED_USER_ID`
- `APP_SECRET_KEY`

For local ngrok tests, `NGROK_AUTHTOKEN` is required.

## 2) Local Bring-Up (Docker)

```sh
./ops/scripts/local-start.sh
```

This starts:
- API, frontend, postgres, nginx
- and runs database migrations in Docker.

URLs:
- Dashboard: `http://localhost/`
- Health: `http://localhost/api/health`

## 3) Local ngrok + Webhook Registration

Start ngrok container, detect public URL, and register Strava + Telegram webhooks:

```sh
./ops/scripts/local-ngrok-test-setup.sh
```

This script:
- starts ngrok (`docker compose --profile ngrok up -d ngrok`)
- reads ngrok public URL from local ngrok API
- registers Strava push subscription
- sets Telegram webhook
- prints a Strava OAuth connect URL

Then:
1. Open the printed Strava OAuth URL once.
2. In Telegram, send any message to your bot (required so bot can message you later).
3. Complete a test run/workout in Strava.
4. Watch dashboard updates in `http://localhost/`.

## 4) Containerized Tests

```sh
./ops/scripts/test.sh
```

This executes:
- backend tests: `pytest`
- frontend tests: `vitest`

Both run in containers.

## 5) VPS Deployment

On your VPS, clone repo, create `.env`, then:

```sh
./ops/scripts/vps-deploy.sh
```

This does:
- compose up/build (prod file)
- migration run in container
- process status output

Then register webhooks against your VPS domain:

```sh
PUBLIC_BASE_URL=https://your-domain.example ./ops/scripts/register-webhooks.sh
```

Re-run Strava OAuth connect URL (printed by script) if needed after changing callback domains.

## 6) Operational Commands

Start local stack:

```sh
docker compose up -d --build
```

Tail local logs:

```sh
docker compose logs -f api frontend nginx
```

Stop local:

```sh
docker compose down
```

Stop local and wipe data:

```sh
docker compose down -v
```

## Notes

- This is single-user by design.
- Run flow sends Telegram shoe picker for every run (allows changing gear even when default is pre-assigned).
- Gym/workout flow updates Strava `hide_from_home=true`.
- Dashboard polls operational APIs for pending items and recent events.
