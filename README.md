# Strava Automation Service

Docker-only Strava + Telegram automation with:
- FastAPI API (webhook processing in-process)
- PostgreSQL
- React/TypeScript dashboard

No local dependency installs are required beyond Docker/Compose.

## Required Values

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
- `COACH_TELEGRAM_BOT_TOKEN`
- `COACH_TELEGRAM_WEBHOOK_SECRET`
- `COACH_TELEGRAM_ALLOWED_USER_ID`
- `MCP_SERVER_URL`
- `STRAVA_MCP_BEARER`
- `APP_SECRET_KEY`

## VPS Deployment

Push to `main` to deploy. The GitHub Actions workflow builds, deploys to your VPS, runs migrations, and registers Strava + Telegram webhooks automatically.

See [docs/VPS-DEPLOYMENT.md](docs/VPS-DEPLOYMENT.md) for full setup (domain, TLS, Strava API settings, etc.).

## Notes

- This is single-user by design.
- Run flow sends Telegram shoe picker for every run (allows changing gear even when default is pre-assigned).
- Gym/workout flow updates Strava `hide_from_home=true`.
- Dashboard polls operational APIs for pending items and recent events.
