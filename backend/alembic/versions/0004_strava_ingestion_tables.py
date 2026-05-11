"""strava ingestion tables

Revision ID: 0004_strava_ingestion_tables
Revises: 0003_athlete_profile
Create Date: 2026-04-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0004_strava_ingestion_tables"
down_revision: str | None = "0003_athlete_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "strava_activities",
        sa.Column("activity_id", sa.BigInteger(), primary_key=True),
        sa.Column("athlete_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("activity_type", sa.String(length=50), nullable=True),
        sa.Column("sport_type", sa.String(length=50), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_date_local", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.Text(), nullable=True),
        sa.Column("distance", sa.Float(), nullable=True),
        sa.Column("moving_time", sa.Integer(), nullable=True),
        sa.Column("elapsed_time", sa.Integer(), nullable=True),
        sa.Column("total_elevation_gain", sa.Float(), nullable=True),
        sa.Column("elev_high", sa.Float(), nullable=True),
        sa.Column("elev_low", sa.Float(), nullable=True),
        sa.Column("average_speed", sa.Float(), nullable=True),
        sa.Column("max_speed", sa.Float(), nullable=True),
        sa.Column("has_heartrate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("average_heartrate", sa.Float(), nullable=True),
        sa.Column("max_heartrate", sa.Float(), nullable=True),
        sa.Column("average_cadence", sa.Float(), nullable=True),
        sa.Column("average_watts", sa.Float(), nullable=True),
        sa.Column("max_watts", sa.Float(), nullable=True),
        sa.Column("weighted_average_watts", sa.Float(), nullable=True),
        sa.Column("kilojoules", sa.Float(), nullable=True),
        sa.Column("device_watts", sa.Boolean(), nullable=True),
        sa.Column("calories", sa.Float(), nullable=True),
        sa.Column("suffer_score", sa.Float(), nullable=True),
        sa.Column("gear_id", sa.String(length=128), nullable=True),
        sa.Column("trainer", sa.Boolean(), nullable=True),
        sa.Column("commute", sa.Boolean(), nullable=True),
        sa.Column("manual", sa.Boolean(), nullable=True),
        sa.Column("private", sa.Boolean(), nullable=True),
        sa.Column("flagged", sa.Boolean(), nullable=True),
        sa.Column("hide_from_home", sa.Boolean(), nullable=True),
        sa.Column("workout_type", sa.Integer(), nullable=True),
        sa.Column("achievement_count", sa.Integer(), nullable=True),
        sa.Column("pr_count", sa.Integer(), nullable=True),
        sa.Column("kudos_count", sa.Integer(), nullable=True),
        sa.Column("athlete_count", sa.Integer(), nullable=True),
        sa.Column("device_name", sa.Text(), nullable=True),
        sa.Column("map_id", sa.String(length=128), nullable=True),
        sa.Column("summary_polyline", sa.Text(), nullable=True),
        sa.Column("start_latlng", postgresql.JSONB(), nullable=True),
        sa.Column("end_latlng", postgresql.JSONB(), nullable=True),
        sa.Column("has_laps", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_splits", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_segments", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_best_efforts", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_zones", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_streams", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("detail_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_strava_activities_athlete_start", "strava_activities", ["athlete_id", "start_date_local"])
    op.create_index("idx_strava_activities_type_start", "strava_activities", ["sport_type", "start_date_local"])
    op.create_index("idx_strava_activities_detail_gin", "strava_activities", ["detail_data"], postgresql_using="gin")
    op.create_index("idx_strava_activities_metadata_gin", "strava_activities", ["metadata"], postgresql_using="gin")
    op.create_index(
        "idx_strava_activities_not_deleted",
        "strava_activities",
        ["start_date_local"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "strava_backfill_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("athlete_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("force_refresh", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("missing_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("queued_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("succeeded_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "strava_activity_laps",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("lap_id", sa.BigInteger(), nullable=True),
        sa.Column("activity_id", sa.BigInteger(), sa.ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False),
        sa.Column("athlete_id", sa.BigInteger(), nullable=True),
        sa.Column("lap_index", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("split", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_date_local", sa.DateTime(timezone=True), nullable=True),
        sa.Column("distance", sa.Float(), nullable=True),
        sa.Column("moving_time", sa.Integer(), nullable=True),
        sa.Column("elapsed_time", sa.Integer(), nullable=True),
        sa.Column("average_speed", sa.Float(), nullable=True),
        sa.Column("max_speed", sa.Float(), nullable=True),
        sa.Column("average_heartrate", sa.Float(), nullable=True),
        sa.Column("max_heartrate", sa.Float(), nullable=True),
        sa.Column("average_cadence", sa.Float(), nullable=True),
        sa.Column("average_watts", sa.Float(), nullable=True),
        sa.Column("device_watts", sa.Boolean(), nullable=True),
        sa.Column("total_elevation_gain", sa.Float(), nullable=True),
        sa.Column("pace_zone", sa.Integer(), nullable=True),
        sa.Column("start_index", sa.Integer(), nullable=True),
        sa.Column("end_index", sa.Integer(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("activity_id", "lap_index", name="uq_strava_lap_activity_index"),
    )
    op.create_index("idx_strava_laps_activity", "strava_activity_laps", ["activity_id", "lap_index"])
    op.create_index("idx_strava_laps_start", "strava_activity_laps", ["start_date_local"])

    op.create_table(
        "strava_activity_segment_efforts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("segment_effort_id", sa.BigInteger(), nullable=True),
        sa.Column("activity_id", sa.BigInteger(), sa.ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("segment_id", sa.BigInteger(), nullable=True),
        sa.Column("segment_name", sa.Text(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_date_local", sa.DateTime(timezone=True), nullable=True),
        sa.Column("distance", sa.Float(), nullable=True),
        sa.Column("moving_time", sa.Integer(), nullable=True),
        sa.Column("elapsed_time", sa.Integer(), nullable=True),
        sa.Column("start_index", sa.Integer(), nullable=True),
        sa.Column("end_index", sa.Integer(), nullable=True),
        sa.Column("average_heartrate", sa.Float(), nullable=True),
        sa.Column("max_heartrate", sa.Float(), nullable=True),
        sa.Column("average_cadence", sa.Float(), nullable=True),
        sa.Column("average_watts", sa.Float(), nullable=True),
        sa.Column("device_watts", sa.Boolean(), nullable=True),
        sa.Column("is_kom", sa.Boolean(), nullable=True),
        sa.Column("kom_rank", sa.Integer(), nullable=True),
        sa.Column("pr_rank", sa.Integer(), nullable=True),
        sa.Column("hidden", sa.Boolean(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_strava_segment_efforts_activity", "strava_activity_segment_efforts", ["activity_id"])
    op.create_index("idx_strava_segment_efforts_segment", "strava_activity_segment_efforts", ["segment_id", "start_date_local"])

    op.create_table(
        "strava_activity_splits",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("activity_id", sa.BigInteger(), sa.ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False),
        sa.Column("split_source", sa.String(length=20), nullable=False),
        sa.Column("split", sa.Integer(), nullable=False),
        sa.Column("distance", sa.Float(), nullable=True),
        sa.Column("moving_time", sa.Integer(), nullable=True),
        sa.Column("elapsed_time", sa.Integer(), nullable=True),
        sa.Column("average_speed", sa.Float(), nullable=True),
        sa.Column("elevation_difference", sa.Float(), nullable=True),
        sa.Column("pace_zone", sa.Integer(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("activity_id", "split_source", "split", name="uq_strava_split_activity_source_split"),
    )
    op.create_index("idx_strava_splits_activity", "strava_activity_splits", ["activity_id", "split_source", "split"])

    op.create_table(
        "strava_activity_best_efforts",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("best_effort_id", sa.BigInteger(), nullable=True),
        sa.Column("activity_id", sa.BigInteger(), sa.ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("distance", sa.Float(), nullable=True),
        sa.Column("moving_time", sa.Integer(), nullable=True),
        sa.Column("elapsed_time", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_date_local", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_index", sa.Integer(), nullable=True),
        sa.Column("end_index", sa.Integer(), nullable=True),
        sa.Column("pr_rank", sa.Integer(), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_strava_best_efforts_activity", "strava_activity_best_efforts", ["activity_id"])
    op.create_index("idx_strava_best_efforts_name", "strava_activity_best_efforts", ["name"])

    op.create_table(
        "strava_activity_zones",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("activity_id", sa.BigInteger(), sa.ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False),
        sa.Column("zone_type", sa.String(length=50), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="strava"),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("activity_id", "zone_type", name="uq_strava_zone_activity_type"),
    )
    op.create_index("idx_strava_zones_activity", "strava_activity_zones", ["activity_id"])

    op.create_table(
        "strava_activity_streams",
        sa.Column("activity_id", sa.BigInteger(), sa.ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("stream_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("stream_keys", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("ARRAY[]::TEXT[]")),
        sa.Column("sample_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("resolution", sa.String(length=20), nullable=True),
        sa.Column("series_type", sa.String(length=20), nullable=True),
        sa.Column("first_time_seconds", sa.Integer(), nullable=True),
        sa.Column("last_time_seconds", sa.Integer(), nullable=True),
        sa.Column("first_distance_m", sa.Float(), nullable=True),
        sa.Column("last_distance_m", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_strava_streams_keys", "strava_activity_streams", ["stream_keys"], postgresql_using="gin")

    op.create_table(
        "strava_ingestion_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("activity_id", sa.BigInteger(), nullable=False),
        sa.Column("athlete_id", sa.BigInteger(), nullable=True),
        sa.Column("trigger_type", sa.String(length=32), nullable=False),
        sa.Column("aspect_type", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("backfill_run_id", sa.BigInteger(), sa.ForeignKey("strava_backfill_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_strava_ingestion_jobs_status", "strava_ingestion_jobs", ["status", "queued_at"])
    op.create_index("idx_strava_ingestion_jobs_activity", "strava_ingestion_jobs", ["activity_id", "queued_at"])
    op.create_index("idx_strava_ingestion_jobs_backfill", "strava_ingestion_jobs", ["backfill_run_id"])


def downgrade() -> None:
    op.drop_table("strava_ingestion_jobs")
    op.drop_table("strava_activity_streams")
    op.drop_table("strava_activity_zones")
    op.drop_table("strava_activity_best_efforts")
    op.drop_table("strava_activity_splits")
    op.drop_table("strava_activity_segment_efforts")
    op.drop_table("strava_activity_laps")
    op.drop_table("strava_backfill_runs")
    op.drop_table("strava_activities")
