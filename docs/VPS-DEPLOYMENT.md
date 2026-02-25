# VPS Production Deployment Guide

This guide covers deploying the Strava Automation Service to a Linux VPS with a real domain and HTTPS. It replaces the local ngrok/cloudflared tunnel workflow.

---

## 1. Overview

| Aspect | Local dev | VPS production |
|--------|-----------|----------------|
| Public URL | ngrok / cloudflare tunnel | Your own domain |
| TLS | Tunnel handles it | Managed by host nginx + certbot |
| Docker compose file | `docker-compose.yml` | `docker-compose.prod.yml` |
| Database | Local postgres container | Same (postgres container, persistent volume) |
| Webhooks | Re-registered each tunnel restart | Registered once, stable |

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

# Telegram
TELEGRAM_BOT_TOKEN=<your_bot_token>
TELEGRAM_WEBHOOK_SECRET=<long_random_string>
TELEGRAM_ALLOWED_USER_ID=<your_numeric_telegram_id>
TELEGRAM_WEBHOOK_URL=https://yourdomain.com/api/telegram/webhook/<same_value_as_TELEGRAM_WEBHOOK_SECRET>

# Security
APP_SECRET_KEY=<32_plus_random_characters>
```

### Optional values

- **`FRONTEND_BASE_URL`** — Where the browser is redirected after Strava OAuth. Defaults to `PUBLIC_BASE_URL` if unset. Set this if your frontend is served on a different subdomain than the API.
- **Tunnel vars** (`TUNNEL_PROVIDER`, `CLOUDFLARED_TUNNEL_TOKEN`, `NGROK_AUTHTOKEN`, `TUNNEL_DOMAIN`) — Not used in production. Remove or leave blank.

> **Note on `STRAVA_WEBHOOK_CALLBACK_URL`:** This variable no longer exists in config. The webhook URL is auto-derived from `PUBLIC_BASE_URL` by the `register-webhooks.sh` script.

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

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Then run migrations:

```bash
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
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

```bash
./ops/scripts/register-webhooks.sh
```

This script reads `.env` and:
1. Deletes any existing Strava webhook subscriptions for your app (to avoid duplicates)
2. Creates a new Strava push subscription pointing to `PUBLIC_BASE_URL/api/strava/webhook`
3. Sets the Telegram webhook to `PUBLIC_BASE_URL/api/telegram/webhook/<secret>`

You only need to run this once. Webhooks remain registered until you explicitly change them.

---

## 10. Connect Strava (One-Time OAuth)

Open `https://yourdomain.com/` in your browser and click **Connect with Strava**. Complete the OAuth flow. Your tokens are stored in the postgres container's persistent volume and will survive restarts.

---

## 11. Verify

```bash
# Health check — should return 200
curl -s https://yourdomain.com/api/health

# Confirm all containers are running
docker compose -f docker-compose.prod.yml ps
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
docker compose -f docker-compose.prod.yml logs -f

# API only
docker compose -f docker-compose.prod.yml logs -f api
```

### Deploy updates

Pull the latest code and rebuild:

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
```

### Restart a single service

```bash
docker compose -f docker-compose.prod.yml restart api
```

### Database access

```bash
docker compose -f docker-compose.prod.yml exec postgres psql -U strava -d strava
```

---

## 14. Troubleshooting

### Nginx shows 502 Bad Gateway
- The `api` or `frontend` container may not be healthy yet. Check with `docker compose -f docker-compose.prod.yml ps` and `logs api`.
- Confirm the containers are exposing ports: `docker compose -f docker-compose.prod.yml ps` should show `0.0.0.0:8000->8000/tcp` and `0.0.0.0:3001->3001/tcp`.

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
- Check `docker compose -f docker-compose.prod.yml logs api` for webhook processing errors.

### OAuth redirect fails after clicking "Connect with Strava"
- Confirm the **Authorization Callback Domain** on strava.com/settings/api is set to `yourdomain.com` (not the full URL).
- The redirect URI is derived from `PUBLIC_BASE_URL` automatically — confirm `PUBLIC_BASE_URL=https://yourdomain.com` in `.env`.

### Strava webhook events not processing after reconnect
- If you disconnected Strava and reconnected, webhooks remain registered and will resume delivery automatically.
- If webhooks were deleted or timed out, re-run `./ops/scripts/register-webhooks.sh`.
