# Deployment Guide: strava-automation-service

## Port Assignments

| Service  | Port |
|----------|------|
| API      | 8002 |
| Frontend | 3002 |

These are chosen to avoid conflicts with other VPS services:
- `budget-dashboard`: backend=8000, frontend=3000
- `locked-in`: backend=8001, frontend=3001

## VPS Setup

### Directory structure

```
/srv/apps/strava-automation-service/
```

The CI/CD pipeline will create and manage this directory automatically on first deploy.

### Nginx / Reverse Proxy

Configure your VPS reverse proxy (Nginx, Caddy, etc.) to forward:

```
strava.yourdomain.com → localhost:3002
```

The frontend nginx container handles `/api/` proxying internally to the `api` service, so you only need to expose port 3002 externally.

Example Nginx reverse proxy config:

```nginx
server {
    listen 443 ssl;
    server_name strava.yourdomain.com;

    location / {
        proxy_pass http://localhost:3002;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## GitHub Actions Secrets

### Shared VPS secrets (may already exist at org/user level):

| Secret        | Description                        |
|---------------|------------------------------------|
| `VPS_HOST`    | VPS IP address or hostname         |
| `VPS_PORT`    | SSH port (usually `22`)            |
| `VPS_USER`    | SSH username                       |
| `VPS_SSH_KEY` | SSH private key (full contents)    |
| `GH_USERNAME` | GitHub username for repo cloning   |
| `GH_PAT`      | GitHub Personal Access Token       |

### Strava-specific secrets:

| Secret                        | Value / Description                                          |
|-------------------------------|--------------------------------------------------------------|
| `POSTGRES_USER`               | Database username (e.g. `strava_user`)                       |
| `POSTGRES_PASSWORD`           | Database password                                            |
| `POSTGRES_DB`                 | Database name (e.g. `strava_db`)                             |
| `POSTGRES_PORT`               | `5432`                                                       |
| `BACKEND_PORT`                | `8002`                                                       |
| `FRONTEND_PORT`               | `3002`                                                       |
| `APP_ENV`                     | `production`                                                 |
| `APP_SECRET_KEY`              | Random 32+ character secret string                           |
| `JWT_SECRET`                  | Random 32+ character secret string (can reuse `APP_SECRET_KEY`) |
| `JWT_EXP_MINUTES`             | `30`                                                          |
| `JWT_COOKIE_SECURE`           | `true` (required over HTTPS)                                 |
| `PUBLIC_BASE_URL`             | `https://strava.yourdomain.com`                              |
| `STRAVA_CLIENT_ID`            | Strava app Client ID (from strava.com/settings/api)          |
| `STRAVA_CLIENT_SECRET`        | Strava app Client Secret                                     |
| `STRAVA_WEBHOOK_VERIFY_TOKEN` | Random token for Strava webhook verification                 |
| `STRAVA_ALLOWED_ATHLETE_ID`   | Your Strava athlete ID (e.g. `14460791`) — restricts OAuth and webhook to this athlete only |
| `TELEGRAM_BOT_TOKEN`          | Bot token from BotFather                                     |
| `TELEGRAM_WEBHOOK_SECRET`     | Long random string for Telegram webhook path                 |
| `TELEGRAM_ALLOWED_USER_ID`    | Your Telegram numeric user ID                                |
| `TELEGRAM_WEBHOOK_URL`        | `https://strava.yourdomain.com/api/telegram/webhook/{secret}`|

## First Deployment

1. Add all secrets listed above to the GitHub repository (Settings → Secrets → Actions).
2. Push to `main` or trigger manually via Actions → Deploy to VPS → Run workflow.
3. Monitor the Actions tab for successful completion.
4. SSH to VPS and verify: `cd /srv/apps/strava-automation-service && docker compose ps`

### JWT setting

- Set `JWT_EXP_MINUTES=30`.
- Keep `STRAVA_ALLOWED_ATHLETE_ID` set in all environments to block non-owner access.

## Post-Deployment: Webhook Registration

After the first successful deploy, register the Strava and Telegram webhooks:

```bash
# On VPS or locally with VPS-accessible PUBLIC_BASE_URL
cd /srv/apps/strava-automation-service
PUBLIC_BASE_URL=https://strava.yourdomain.com bash ops/scripts/register-webhooks.sh
```

This registers:
- **Strava webhook**: Strava pushes activity events to `/api/strava/webhook`
- **Telegram webhook**: Telegram delivers bot messages to `/api/telegram/webhook/{secret}`

## Verification Checklist

- [ ] `docker compose ps` — all containers show `Up`
- [ ] `https://strava.yourdomain.com` — frontend loads
- [ ] `https://strava.yourdomain.com/api/health` — returns `{"status":"ok"}`
- [ ] `docker compose exec api alembic current` — shows latest migration revision

## Compose File Reference

| File                    | Purpose                                      |
|-------------------------|----------------------------------------------|
| `docker-compose.yml`    | Production (used by CI/CD)                   |
| `docker-compose.dev.yml`| Local development (hot reload, ngrok, tunnel)|

## Development

```bash
make dev-up       # Start local dev environment
make dev-logs     # Tail all logs
make dev-shell    # Shell into api container
make migrate      # Apply pending migrations
```
