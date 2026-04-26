# Strava Data Model

This document proposes the Postgres schema for full Strava activity ingestion.

The schema is intentionally separate from the current application tables. Do not rename, repurpose, or change the meaning of `users`, `gear`, `pending_activities`, or `event_log` for this feature.

## Goals

- Store every Strava activity in a queryable local cache.
- Preserve raw Strava detail and stream payloads for future analysis.
- Extract common scalar fields for fast filtering and sorting.
- Make ingestion idempotent and observable.
- Support Claude-facing MCP tools without repeatedly calling Strava.

## Table Overview

Recommended new tables:

- `strava_activities`: one row per Strava activity, with extracted scalar fields and raw detailed activity JSON.
- `strava_activity_streams`: one row per activity containing stream JSON and stream metadata.
- `strava_ingestion_jobs`: one row per ingestion attempt or backfill item.
- `strava_backfill_runs`: one row per manually requested date-range backfill.

Keep these tables independent from current Telegram automation tables. The existing app may read from the new tables later, but the current workflows should not depend on them.

## `strava_activities`

Primary read model for activity-level analytics.

```sql
CREATE TABLE strava_activities (
    activity_id BIGINT PRIMARY KEY,
    athlete_id BIGINT NOT NULL,
    name TEXT,
    activity_type VARCHAR(50),
    sport_type VARCHAR(50),
    start_date TIMESTAMP WITH TIME ZONE,
    start_date_local TIMESTAMP WITH TIME ZONE,
    timezone TEXT,
    distance DOUBLE PRECISION,
    moving_time INTEGER,
    elapsed_time INTEGER,
    total_elevation_gain DOUBLE PRECISION,
    average_speed DOUBLE PRECISION,
    max_speed DOUBLE PRECISION,
    average_heartrate DOUBLE PRECISION,
    max_heartrate DOUBLE PRECISION,
    average_cadence DOUBLE PRECISION,
    average_watts DOUBLE PRECISION,
    weighted_average_watts DOUBLE PRECISION,
    kilojoules DOUBLE PRECISION,
    calories DOUBLE PRECISION,
    suffer_score DOUBLE PRECISION,
    gear_id TEXT,
    summary_polyline TEXT,
    summary_data JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_updated_at TIMESTAMP WITH TIME ZONE,
    first_ingested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_ingested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);
```

Suggested indexes:

```sql
CREATE INDEX idx_strava_activities_athlete_start
    ON strava_activities (athlete_id, start_date_local DESC);

CREATE INDEX idx_strava_activities_type_start
    ON strava_activities (sport_type, start_date_local DESC);

CREATE INDEX idx_strava_activities_summary_gin
    ON strava_activities USING GIN (summary_data);

CREATE INDEX idx_strava_activities_metadata_gin
    ON strava_activities USING GIN (metadata);

CREATE INDEX idx_strava_activities_not_deleted
    ON strava_activities (start_date_local DESC)
    WHERE deleted_at IS NULL;
```

### Scalar Columns

Scalar columns are duplicated from `summary_data` on purpose. They make common queries simple and fast:

- Activity list by date range.
- Run-only or ride-only filtering.
- Weekly distance and elevation summaries.
- Heart-rate or power availability checks.
- MCP tool search and summarization.

`summary_data` remains the complete source payload for fields not yet promoted to columns.

### Metadata JSON

Use `metadata` for values derived by this app, not returned directly by Strava.

Examples:

```json
{
  "has_streams": true,
  "stream_keys": ["time", "distance", "heartrate"],
  "sample_count": 5320,
  "hr_zone_minutes": {
    "z1": 12.5,
    "z2": 34.0,
    "z3": 18.25,
    "z4": 5.5,
    "z5": 0.0
  },
  "pace_drift_percent": 3.8
}
```

Keep metadata reproducible. If a value depends on a configurable zone model, store the model version or assumptions.

## `strava_activity_streams`

Streams can be large. Keep them in a separate table so activity list queries do not load high-volume JSON by accident.

```sql
CREATE TABLE strava_activity_streams (
    activity_id BIGINT PRIMARY KEY
        REFERENCES strava_activities(activity_id)
        ON DELETE CASCADE,
    stream_data JSONB NOT NULL,
    stream_keys TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    sample_count INTEGER NOT NULL DEFAULT 0,
    resolution VARCHAR(20),
    series_type VARCHAR(20),
    first_time_seconds INTEGER,
    last_time_seconds INTEGER,
    first_distance_m DOUBLE PRECISION,
    last_distance_m DOUBLE PRECISION,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Suggested indexes:

```sql
CREATE INDEX idx_strava_streams_keys
    ON strava_activity_streams USING GIN (stream_keys);

CREATE INDEX idx_strava_streams_data_gin
    ON strava_activity_streams USING GIN (stream_data);
```

The GIN index on `stream_data` is optional. It can be useful for ad hoc JSON existence queries, but it may be expensive if stream payloads are large. Start without it if storage size or write cost becomes a concern.

## `strava_ingestion_jobs`

Tracks ingestion attempts for webhook events and backfill items.

```sql
CREATE TABLE strava_ingestion_jobs (
    id BIGSERIAL PRIMARY KEY,
    activity_id BIGINT NOT NULL,
    athlete_id BIGINT,
    trigger_type VARCHAR(32) NOT NULL,
    aspect_type VARCHAR(32),
    status VARCHAR(32) NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    backfill_run_id BIGINT,
    queued_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Expected values:

- `trigger_type`: `webhook`, `backfill`, `manual_retry`.
- `aspect_type`: `create`, `update`, `delete`, or null for manual backfill.
- `status`: `queued`, `running`, `succeeded`, `failed`, `skipped`, `deleted`.

Suggested indexes:

```sql
CREATE INDEX idx_strava_ingestion_jobs_status
    ON strava_ingestion_jobs (status, queued_at);

CREATE INDEX idx_strava_ingestion_jobs_activity
    ON strava_ingestion_jobs (activity_id, queued_at DESC);

CREATE INDEX idx_strava_ingestion_jobs_backfill
    ON strava_ingestion_jobs (backfill_run_id);
```

## `strava_backfill_runs`

Tracks date-range backfills requested from the admin UI.

```sql
CREATE TABLE strava_backfill_runs (
    id BIGSERIAL PRIMARY KEY,
    athlete_id BIGINT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(32) NOT NULL,
    requested_count INTEGER NOT NULL DEFAULT 0,
    missing_count INTEGER NOT NULL DEFAULT 0,
    queued_count INTEGER NOT NULL DEFAULT 0,
    succeeded_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Expected `status` values:

- `created`
- `discovering`
- `queued`
- `running`
- `completed`
- `completed_with_errors`
- `failed`
- `cancelled`

## SQLAlchemy Model Guidance

Add models to `backend/app/models.py` or move ingestion models to a dedicated module if the file becomes too large. If using a separate module, make sure Alembic imports it so metadata discovery still works.

Use SQLAlchemy JSON types with Postgres JSONB variants:

```python
from sqlalchemy.dialects.postgresql import JSONB

summary_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
```

Use `BigInteger` for Strava IDs. Activity IDs can exceed 32-bit integer ranges.

## Alembic Migration Guidance

Create a new migration after the current `0003_athlete_profile` revision.

The migration should:

1. Create the new tables.
2. Add indexes.
3. Avoid changes to current tables unless absolutely required.
4. Include a downgrade that drops the new tables and indexes only.

Do not backfill data inside the schema migration. Backfill should be an application-level operation so it can respect Strava rate limits and be retried safely.

## Upsert Semantics

Ingestion should be idempotent.

For `create` and `update`:

- Upsert `strava_activities` by `activity_id`.
- Upsert `strava_activity_streams` by `activity_id`.
- Preserve `first_ingested_at` on conflict.
- Always update `last_ingested_at`.
- Clear `deleted_at` if the activity exists again.

For `delete`:

- Prefer soft delete by setting `deleted_at`.
- Mark related ingestion job as `deleted`.
- Keep stream data unless storage pressure requires cleanup.

## Data Retention

Raw streams may be the largest data source. Start by retaining all stream data because the goal is complete local history for analysis.

If storage becomes a problem, add an explicit retention policy later:

- Keep raw streams for recent activities.
- Keep downsampled streams for older activities.
- Keep activity summaries forever.

Do not silently discard stream data in the first implementation.

## MCP Query Considerations

MCP tools should read from these tables, not from Strava.

Good query patterns:

- Use scalar columns to identify candidate activities.
- Load `summary_data` only for the selected activities.
- Load `stream_data` only for tools that need time-series analysis.
- Downsample or aggregate streams before returning text to Claude.

This keeps Claude responses fast and avoids sending raw multi-hour streams into the context window.
