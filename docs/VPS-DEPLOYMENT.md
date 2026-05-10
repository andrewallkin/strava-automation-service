# VPS Production Deployment Guide

This guide covers deploying the Strava Automation Service to a Linux VPS with a real domain and HTTPS.

---

## 1. Overview

| Aspect | VPS production |
|--------|----------------|
| Public URL | Your own domain |
| TLS | Managed by host nginx + certbot |
| Docker compose file | `docker-compose.yml` |
| Database | Postgres container with persistent volume |
| Webhooks | Registered automatically by deploy workflow on each deploy |

The production stack is: **Host Nginx → FastAPI (uvicorn, port 8000) + React (Vite preview, port 3001) + PostgreSQL**, all Docker containers except nginx.

Nginx runs on the host and proxies to the Docker containers via their exposed ports.

---

## 2. Prerequisites

**VPS:**
- Ubuntu 22.04 or later
- Minimum 1 GB RAM (2 GB recommended)
- Public IP address

**Installed on VPS:**
- Docker Engine + Docker Compose plugin ([official install guide](https://docs.docker.com/engine/install/ubuntu/))
- `git`, `curl`
- `nginx` (host-installed, manages routing and TLS)
- `certbot` with the nginx plugin (`sudo apt install certbot python3-certbot-nginx`)

**DNS:**
- A domain name with an A record pointing to the VPS public IP
- DNS propagation must complete before running certbot (allow up to 30 min)

**Strava:**
- Strava API application already created at [strava.com/settings/api](https://www.strava.com/settings/api)
- `client_id` and `client_secret` available

**Telegram:**
- Bot created via [@BotFather](https://t.me/BotFather)
- Bot token and your numeric user ID available

---

## 3. Provision the Server

```bash
# SSH into the VPS
ssh user@your-vps-ip

# Install Docker (if not already installed)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in so the group takes effect

# Clone the repo
git clone https://github.com/your-username/strava-automation-service.git
cd strava-automation-service
```

---

## 4. Configure `.env` for Production

```bash
cp .env.example .env
nano .env   # or use your preferred editor
```

### Required values (all must be set)

```dotenv
# App
APP_ENV=production
PUBLIC_BASE_URL=https://yourdomain.com

# Database — use a strong password
POSTGRES_DB=strava
POSTGRES_USER=strava
POSTGRES_PASSWORD=<generate_a_strong_random_password>
POSTGRES_HOST=postgres

# Strava
STRAVA_CLIENT_ID=<your_client_id>
STRAVA_CLIENT_SECRET=<your_client_secret>
STRAVA_WEBHOOK_VERIFY_TOKEN=<random_string_you_invent>
STRAVA_SCOPES=activity:read,activity:write,profile:read_all
STRAVA_ALLOWED_ATHLETE_ID=<your_strava_athlete_id>

# Telegram
TELEGRAM_BOT_TOKEN=<your_bot_token>
TELEGRAM_WEBHOOK_SECRET=<long_random_string>
TELEGRAM_ALLOWED_USER_ID=<your_numeric_telegram_id>
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/api/telegram/webhook/<same_value_as_TELEGRAM_WEBHOOK_SECRET>
COACH_TELEGRAM_BOT_TOKEN=<your_second_bot_token>
COACH_TELEGRAM_WEBHOOK_SECRET=<long_random_string_for_coach_bot>
COACH_TELEGRAM_ALLOWED_USER_ID=<your_numeric_telegram_id>
COACH_TELEGRAM_WEBHOOK_URL=https://yourdomain.com/api/telegram/coach/webhook/<same_value_as_COACH_TELEGRAM_WEBHOOK_SECRET>
REDIS_URL=redis://redis:6379/0

# Security
APP_SECRET_KEY=<32_plus_random_characters>
JWT_SECRET=<32_plus_random_characters>
JWT_EXP_MINUTES=30
JWT_COOKIE_SECURE=true
```

### Optional values

- **`FRONTEND_BASE_URL`** — Where the browser is redirected after Strava OAuth. Defaults to `PUBLIC_BASE_URL` if unset. Set this if your frontend is served on a different subdomain than the API.
- **JWT expiry** — Set `JWT_EXP_MINUTES=30` for production.

> **Note:** The webhook URL is derived from `PUBLIC_BASE_URL`. Webhooks are registered automatically by the deploy workflow on each deploy.

---

## 5. Update Strava API App Settings

Go to [strava.com/settings/api](https://www.strava.com/settings/api) → **Edit Application**:

- **Authorization Callback Domain**: `yourdomain.com`
  - Enter the bare domain only — no `https://`, no path, no trailing slash.

Save. The OAuth redirect URI is derived from `PUBLIC_BASE_URL` automatically.

---

## 6. Configure Host Nginx

Create an nginx site config on the VPS host (replace `yourdomain.com` with your domain):

```nginx
# /etc/nginx/sites-available/strava
server {
    listen 80;
    server_name yourdomain.com;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/strava /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 7. Deploy the Stack

Push to `main` to deploy via GitHub Actions. The workflow builds, starts containers, runs migrations, and registers webhooks.

For manual deployment:

```bash
docker compose up -d --build
docker compose exec api bash -c "cd /app && ./run_migrations.sh"
```

At this point the service is accessible over **HTTP only** (port 80). HTTPS comes next.

---

## 8. Enable HTTPS (Let's Encrypt)

Ensure DNS has propagated (verify with `dig yourdomain.com +short` — should return your VPS IP), then run:

```bash
sudo certbot --nginx -d yourdomain.com
```

Certbot will automatically update the nginx config to add TLS and redirect HTTP → HTTPS.

After success, the service is live at `https://yourdomain.com`.

---

## 9. Register Webhooks

Webhooks are registered automatically by the deploy workflow on each deploy. No manual step required.

If you deploy manually and need to re-register webhooks, trigger the deploy workflow from the Actions tab, or redeploy to run the webhook registration step.

---

## 10. Connect Strava (OAuth Login)

Open `https://yourdomain.com/` in your browser and click **Continue with Strava**. Login always starts the OAuth redirect flow. If your Strava browser session is still active and your app is already authorized, Strava usually redirects back immediately without showing consent again.

Your Strava tokens are stored in the postgres container's persistent volume and survive restarts. App logout only clears the app JWT cookie; it does not revoke Strava authorization.

---

## 11. Verify

```bash
# Health check — should return 200
curl -s https://yourdomain.com/api/health

# Confirm all containers are running
docker compose ps
```

Then:
- Open `https://yourdomain.com/` — UI should load and show your Strava athlete ID
- Record a short run in Strava — after a minute or two, a Telegram message should arrive asking for shoe selection (if `run_shoe_enabled` is on)

---

## 12. Certificate Renewal

Certbot (installed via `python3-certbot-nginx`) sets up automatic renewal via a systemd timer. Verify it's active:

```bash
sudo systemctl status certbot.timer
```

To test renewal without actually renewing:

```bash
sudo certbot renew --dry-run
```

---

## 13. Maintenance

### View logs

```bash
# All services
docker compose logs -f

# API only
docker compose logs -f api
```

### Deploy updates

Push to `main` to deploy via GitHub Actions. For manual updates:

```bash
git pull
docker compose up -d --build
docker compose exec api bash -c "cd /app && ./run_migrations.sh"
```

### Restart a single service

```bash
docker compose restart api
```

### Database access

```bash
docker compose exec postgres psql -U strava -d strava
```

---

## 14. Troubleshooting

### Nginx shows 502 Bad Gateway
- The `api` or `frontend` container may not be healthy yet. Check with `docker compose ps` and `docker compose logs api`.
- Confirm the containers are exposing ports: `docker compose ps` should show the api and frontend ports.

### certbot fails with "connection refused" or "timeout"
- Confirm that port 80 is open in your VPS firewall/security group.
- Confirm DNS has propagated: `dig yourdomain.com +short` must return the VPS IP.
- Make sure nginx is running: `sudo systemctl status nginx`.

### Strava webhook registration fails
- Check that `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, and `STRAVA_WEBHOOK_VERIFY_TOKEN` are correct in `.env`.
- The callback URL must be HTTPS and publicly reachable. Verify with `curl https://yourdomain.com/api/strava/webhook?hub.mode=subscribe&hub.verify_token=<your_token>&hub.challenge=test`.

### Telegram messages not arriving
- Confirm the webhook is registered: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
- Check that `TELEGRAM_ALLOWED_USER_ID` matches your actual Telegram numeric ID.
- Check `docker compose logs api` for webhook processing errors.

### OAuth redirect fails after clicking "Connect with Strava"
- Confirm the **Authorization Callback Domain** on strava.com/settings/api is set to `yourdomain.com` (not the full URL).
- The redirect URI is derived from `PUBLIC_BASE_URL` automatically — confirm `PUBLIC_BASE_URL=https://yourdomain.com` in `.env`.

### Strava webhook events not processing after reconnect
- If you disconnected Strava and reconnected, webhooks remain registered and will resume delivery automatically.
- If webhooks were deleted or timed out, trigger a deploy (push to main or run workflow manually) to re-register webhooks.
