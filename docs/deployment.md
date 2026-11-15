# Deployment

Three ways to run Strava Automation Service. Each mode uses a different Compose file (see the one-line audience comment at the top of each file).

## Local development

1. Copy `.env.example` to `.env` and fill required values. Use `POSTGRES_HOST=postgres`, `APP_ENV=development`, and leave `PUBLIC_BASE_URL` empty so webhook registration is skipped. Set `COOKIE_SECURE=false` when the frontend is served over plain HTTP.
2. Start the stack:

```sh
docker compose -f docker-compose.dev.yml up --build
```

3. Run migrations:

```sh
docker compose -f docker-compose.dev.yml run --rm --no-deps api bash /app/run_migrations.sh
```

4. Open the dashboard at `http://localhost:${FRONTEND_PORT:-3000}` (Vite dev server).

## Standalone

Self-contained Postgres and production-style images—no VPS control panel, shared `postgres-net`, or Cloudflare.

```sh
docker compose -f docker-compose.standalone.yml up --build -d
docker compose -f docker-compose.standalone.yml run --rm --no-deps api bash /app/run_migrations.sh
```

Open `http://localhost:${FRONTEND_PORT:-3000}`. The API listens on `127.0.0.1:${BACKEND_PORT:-8000}`; interactive docs are at `/docs` on that port.

Webhook registration at API startup still needs a reachable `PUBLIC_BASE_URL` (and real Strava/Telegram credentials). When `PUBLIC_BASE_URL` is unset or `APP_ENV=development`, registration is skipped—recommended for local standalone runs.

**Updates:** `docker compose -f docker-compose.standalone.yml up --build -d`

**Logs:** `docker compose -f docker-compose.standalone.yml logs -f`

**Database dump:** `docker compose -f docker-compose.standalone.yml exec postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup.sql`

**Restore:** `docker compose -f docker-compose.standalone.yml exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB" < backup.sql`

Before exposing the frontend port on a public host, place your own reverse proxy and firewall in front of `${FRONTEND_PORT:-3000}:80`.

## This VPS

The VPS control panel deploys this repository in **image mode**:

- Runs `docker-compose.yml` (prebuilt Docker Hub images, not local builds).
- Joins the external Docker network `postgres-net`; Postgres runs on the host stack, not inside this Compose file.
- Binds `api`, `frontend`, and `mcp` to loopback ports on the VPS (`BACKEND_PORT`, `FRONTEND_PORT`, `MCP_PORT` from the panel-managed `.env`).
- Pulls image tags (`DOCKER_IMAGE_API`, `DOCKER_IMAGE_FRONTEND`, `DOCKER_IMAGE_MCP`) built by GitHub Actions on `main`.
- Migrates with `docker compose run --rm --no-deps api bash /app/run_migrations.sh`.
- Health-checks `GET /api/health`.

The panel supplies production `POSTGRES_*` values and image tags; TLS and public URLs are configured on the host, not in this repository.