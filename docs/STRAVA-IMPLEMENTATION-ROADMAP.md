# Strava Implementation Roadmap

This roadmap breaks full Strava ingestion and MCP access into reviewable phases.

The highest-priority requirement is compatibility: current Telegram shoe selection, gym hiding, Strava OAuth, webhook responses, event logging, and dashboard behavior must remain unchanged.

## Phase 0: Regression Safety

Before changing shared code, lock down current behavior with tests.

Recommended checks:

- `GET /api/strava/webhook` accepts the configured verify token and rejects invalid tokens.
- `POST /api/strava/webhook` ignores non-activity objects.
- `POST /api/strava/webhook` ignores non-create events for the current Telegram automation path.
- Create events still queue `process_activity()`.
- Run activity processing still sends the Telegram shoe picker when enabled.
- Gym activity processing still sets `hide_from_home=true` when enabled.
- Existing `/api/ui/*` auth and settings behavior remains compatible.

Testing must run inside Docker, consistent with `AGENTS.md`.

Example command shape:

```bash
docker compose run --rm api pytest tests/
```

## Phase 1: Data Model

Add new tables without changing current tables.

Tasks:

- Add SQLAlchemy models for `strava_activities`, `strava_activity_streams`, `strava_ingestion_jobs`, and `strava_backfill_runs`.
- Add an Alembic migration after `0003_athlete_profile`.
- Add JSONB and scalar indexes described in `docs/STRAVA-DATA-MODEL.md`.
- Add model-level tests or migration smoke tests.

Acceptance criteria:

- Existing tables `users`, `gear`, `pending_activities`, and `event_log` are unchanged.
- Migration upgrade creates only new ingestion tables/indexes.
- Migration downgrade removes only new ingestion tables/indexes.
- Existing tests still pass.

## Phase 2: Strava Client Expansion

Extend `StravaService` additively.

Tasks:

- Add `get_activity_detail(..., include_all_efforts=True)`.
- Add `get_activity_streams(..., keys, key_by_type=True)`.
- Add `get_athlete_activities_between(...)` for backfill discovery.
- Capture rate-limit headers in a structured helper or response wrapper if useful.

Do not break these current methods:

- `get_activity()`
- `update_activity()`
- `get_athlete_activities()`
- `get_activities_since()`
- `sync_gear_cache()`

Acceptance criteria:

- Existing callers continue to work without signature changes.
- New methods have tests using mocked Strava responses.
- Token refresh behavior remains centralized in `ensure_fresh_token()`.

## Phase 3: Ingestion Service

Build a new ingestion service independent from Telegram automation.

Suggested files:

```text
backend/app/services/strava_ingestion_service.py
backend/app/services/strava_stream_analysis.py
```

Tasks:

- Implement `ingest_activity(activity_id, owner_id, trigger_type, aspect_type)`.
- Upsert `strava_activities`.
- Upsert `strava_activity_streams`.
- Record `strava_ingestion_jobs`.
- Calculate initial metadata such as `has_streams`, `stream_keys`, and `sample_count`.
- Soft-delete activities for delete events.

Acceptance criteria:

- Re-ingesting the same activity updates the same rows.
- Ingestion failures are recorded without raising into the current Telegram processor.
- No Telegram messages are sent by ingestion code.
- No Strava writes are performed by ingestion code.

## Phase 4: Webhook Integration

Fan out webhook processing to both the existing Telegram automation and the new ingestion path.

Tasks:

- Keep the current `/api/strava/webhook` route and response behavior.
- Continue queueing `process_activity()` for create events exactly as today.
- Add a separate background task for ingestion.
- Let ingestion handle create, update, and delete events.
- Ensure ingestion errors are caught and logged independently.

Important behavior split:

- Current automation remains create-only.
- New ingestion handles create/update/delete for the local read model.

Acceptance criteria:

- Existing webhook tests remain unchanged or are extended without weakening assertions.
- A failed ingestion task does not prevent current Telegram automation from running.
- Non-activity events continue to return the same ignored response.
- Unauthorized owners continue to be ignored.

## Phase 5: Backfill API

Add authenticated APIs for historical ingestion.

Tasks:

- Add `POST /api/ui/backfill`.
- Add `GET /api/ui/backfill/{id}`.
- Add `GET /api/ui/backfill/{id}/jobs`.
- Add retry and cancel endpoints if needed for the first UI.
- Implement missing activity detection.
- Queue ingestion jobs from discovered activity headers.

Acceptance criteria:

- Backfill APIs require the same JWT auth as current UI APIs.
- Backfill queues only missing activities by default.
- `force_refresh` is explicit and tested.
- Job counters are accurate after success, failure, and skip cases.

## Phase 6: Rate Limiting And Worker Behavior

Keep the first worker conservative.

Tasks:

- Add a Strava request limiter or conservative delay.
- Reserve Strava API budget for normal webhook automation.
- Process one activity at a time initially.
- Prioritize webhook ingestion ahead of historical backfill jobs.
- Persist job errors and attempt counts.

Acceptance criteria:

- A large backfill cannot consume the entire short-window request budget.
- 429 responses pause or fail jobs with useful state.
- Failed jobs can be retried.
- Current automation still has enough budget to process new Strava webhooks.

## Phase 7: Backfill UI

Add an admin backfill page without changing current dashboard workflows.

Tasks:

- Add a new route such as `/backfill`.
- Add date range inputs and a `force_refresh` option.
- Show progress with polling.
- Show failed jobs and retry action if implemented.
- Add navigation entry without removing existing pages.

Acceptance criteria:

- Existing home, activities, events, and settings pages still work.
- Existing API client functions remain compatible.
- Backfill status is understandable without reading logs.

## Phase 8: MCP Server

Add a read-only FastMCP server for Claude.

Tasks:

- Add FastMCP dependency inside the Docker build, not through host installs.
- Add `backend/app/mcp/server.py`.
- Add Postgres query helpers.
- Add stream analysis/downsampling helpers.
- Add token auth for SSE access.
- Expose tools for search, activity summary, workout analysis, weekly summary, period comparison, and downsampled streams.

Acceptance criteria:

- MCP tools read from Postgres only.
- MCP tools do not call Strava.
- MCP tools do not mutate Strava or local activity data.
- Long streams are summarized or downsampled before being returned.
- Invalid or missing MCP tokens are rejected.

## Phase 9: Deployment

Deploy in small steps.

Tasks:

- Update Docker image dependencies.
- Add MCP service to `docker-compose.yml` if using a separate process.
- Add environment variables for MCP token and optional heart-rate zones.
- Update nginx routing for `/mcp/` with SSE buffering disabled.
- Update deployment workflow only after local Docker testing passes.
- Document Claude Desktop proxy config with secret placeholders only.

Acceptance criteria:

- Existing `/api/` and frontend routes continue to serve as before.
- Existing webhook registration workflow remains valid.
- MCP endpoint is reachable only with the configured token.
- Secrets are not committed.

## Phase 10: Hardening

Improve reliability after the first end-to-end version works.

Possible improvements:

- Dedicated worker container.
- Durable queue with Redis, RQ, or Celery.
- Read-only Postgres role for MCP.
- More derived metrics in `metadata`.
- User-configurable heart-rate zones.
- Stream retention policy if storage grows too much.
- WebSocket progress updates if polling becomes noisy.

Do these only when the simpler version shows a real limitation.

## Suggested PR Breakdown

Keep PRs small enough to review safely.

1. Regression tests for current behavior.
2. Ingestion tables and migrations.
3. Strava client additions.
4. Ingestion service and tests.
5. Webhook fan-out.
6. Backfill API.
7. Backfill UI.
8. MCP server.
9. Deployment updates.

Each PR should prove that existing behavior remains unchanged.

## Documentation Map

- `docs/STRAVA-INGESTION-ARCHITECTURE.md`: overall design and current code integration points.
- `docs/STRAVA-DATA-MODEL.md`: proposed Postgres schema and JSONB strategy.
- `docs/STRAVA-BACKFILL-AND-RATE-LIMITING.md`: historical sync and Strava rate-limit strategy.
- `docs/STRAVA-MCP-SERVER.md`: FastMCP tools, SSE transport, auth, and Claude Desktop proxy setup.

## Final Compatibility Checklist

Before considering the feature complete:

- Current Telegram shoe picker still works for runs.
- Current gym hiding still works for gym/workout activities.
- Existing dashboard pages still load and use the same API contracts.
- Existing Strava OAuth flow still works.
- Existing webhook verification still works.
- Ingestion can be disabled or fail without taking down current automation.
- MCP server is read-only and token-protected.
- Backfill respects Strava rate limits.
- Tests run inside Docker and pass.
