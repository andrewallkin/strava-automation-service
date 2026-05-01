"""redesign strava analytics schema

Revision ID: 0005_redesign_strava_analytics_schema
Revises: 0004_strava_ingestion_tables
Create Date: 2026-05-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005_redesign_strava_analytics_schema"
down_revision: str | None = "0004_strava_ingestion_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _drop_redesigned_tables() -> None:
    for table_name in (
        "strava_activity_metrics",
        "strava_athlete_zones",
        "strava_activity_zone_buckets",
        "strava_ingestion_jobs",
        "strava_activity_best_efforts",
        "strava_activity_splits",
        "strava_activity_laps",
        "strava_backfill_runs",
        "strava_activities",
    ):
        op.drop_table(table_name)


def _drop_previous_tables() -> None:
    for table_name in (
        "strava_ingestion_jobs",
        "strava_activity_streams",
        "strava_activity_zones",
        "strava_activity_best_efforts",
        "strava_activity_splits",
        "strava_activity_segment_efforts",
        "strava_activity_laps",
        "strava_backfill_runs",
        "strava_activities",
    ):
        op.drop_table(table_name)


def upgrade() -> None:
    _drop_previous_tables()

    op.create_table(
        "strava_activities",
        sa.Column("activity_id", sa.BigInteger(), primary_key=True),
        sa.Column("athlete_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("activity_type", sa.String(length=50), nullable=True),
        sa.Column("sport_type", sa.String(length=50), nullable=True),
        sa.Column("workout_type", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_date_local", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.Text(), nullable=True),
        sa.Column("local_date", sa.Date(), nullable=True),
        sa.Column("local_year", sa.Integer(), nullable=True),
        sa.Column("local_month", sa.Integer(), nullable=True),
        sa.Column("local_week", sa.Integer(), nullable=True),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("moving_time_seconds", sa.Integer(), nullable=True),
        sa.Column("elapsed_time_seconds", sa.Integer(), nullable=True),
        sa.Column("total_elevation_gain_m", sa.Float(), nullable=True),
        sa.Column("elev_high_m", sa.Float(), nullable=True),
        sa.Column("elev_low_m", sa.Float(), nullable=True),
        sa.Column("average_speed_mps", sa.Float(), nullable=True),
        sa.Column("max_speed_mps", sa.Float(), nullable=True),
        sa.Column("average_grade_adjusted_speed_mps", sa.Float(), nullable=True),
        sa.Column("gap_source", sa.String(length=32), nullable=False, server_default="unavailable"),
        sa.Column("has_heartrate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("average_heartrate_bpm", sa.Float(), nullable=True),
        sa.Column("max_heartrate_bpm", sa.Float(), nullable=True),
        sa.Column("average_cadence_spm", sa.Float(), nullable=True),
        sa.Column("average_watts", sa.Float(), nullable=True),
        sa.Column("max_watts", sa.Float(), nullable=True),
        sa.Column("weighted_average_watts", sa.Float(), nullable=True),
        sa.Column("kilojoules", sa.Float(), nullable=True),
        sa.Column("device_watts", sa.Boolean(), nullable=True),
        sa.Column("calories", sa.Float(), nullable=True),
        sa.Column("suffer_score", sa.Float(), nullable=True),
        sa.Column("trainer", sa.Boolean(), nullable=True),
        sa.Column("commute", sa.Boolean(), nullable=True),
        sa.Column("manual", sa.Boolean(), nullable=True),
        sa.Column("private", sa.Boolean(), nullable=True),
        sa.Column("flagged", sa.Boolean(), nullable=True),
        sa.Column("hide_from_home", sa.Boolean(), nullable=True),
        sa.Column("gear_id", sa.String(length=128), nullable=True),
        sa.Column("device_name", sa.Text(), nullable=True),
        sa.Column("has_laps", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_splits", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_best_efforts", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_zones", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("has_gap", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("data_quality", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("detail_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_strava_activities_athlete_start", "strava_activities", ["athlete_id", "start_date_local"])
    op.create_index("idx_strava_activities_type_start", "strava_activities", ["sport_type", "start_date_local"])
    op.create_index("idx_strava_activities_local_date", "strava_activities", ["local_date"])
    op.create_index("idx_strava_activities_year_month", "strava_activities", ["local_year", "local_month"])
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

    op.create_table(
        "strava_activity_laps",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("activity_id", sa.BigInteger(), sa.ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False),
        sa.Column("athlete_id", sa.BigInteger(), nullable=True),
        sa.Column("lap_index", sa.Integer(), nullable=False),
        sa.Column("lap_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("split", sa.Integer(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_date_local", sa.DateTime(timezone=True), nullable=True),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("moving_time_seconds", sa.Integer(), nullable=True),
        sa.Column("elapsed_time_seconds", sa.Integer(), nullable=True),
        sa.Column("average_speed_mps", sa.Float(), nullable=True),
        sa.Column("max_speed_mps", sa.Float(), nullable=True),
        sa.Column("average_grade_adjusted_speed_mps", sa.Float(), nullable=True),
        sa.Column("gap_source", sa.String(length=32), nullable=False, server_default="unavailable"),
        sa.Column("average_heartrate_bpm", sa.Float(), nullable=True),
        sa.Column("max_heartrate_bpm", sa.Float(), nullable=True),
        sa.Column("average_cadence_spm", sa.Float(), nullable=True),
        sa.Column("average_watts", sa.Float(), nullable=True),
        sa.Column("device_watts", sa.Boolean(), nullable=True),
        sa.Column("total_elevation_gain_m", sa.Float(), nullable=True),
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
        "strava_activity_splits",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("activity_id", sa.BigInteger(), sa.ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False),
        sa.Column("split_source", sa.String(length=20), nullable=False),
        sa.Column("split", sa.Integer(), nullable=False),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("moving_time_seconds", sa.Integer(), nullable=True),
        sa.Column("elapsed_time_seconds", sa.Integer(), nullable=True),
        sa.Column("average_speed_mps", sa.Float(), nullable=True),
        sa.Column("average_grade_adjusted_speed_mps", sa.Float(), nullable=True),
        sa.Column("gap_source", sa.String(length=32), nullable=False, server_default="unavailable"),
        sa.Column("average_heartrate_bpm", sa.Float(), nullable=True),
        sa.Column("elevation_difference_m", sa.Float(), nullable=True),
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
        sa.Column("activity_id", sa.BigInteger(), sa.ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False),
        sa.Column("best_effort_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("distance_m", sa.Float(), nullable=True),
        sa.Column("moving_time_seconds", sa.Integer(), nullable=True),
        sa.Column("elapsed_time_seconds", sa.Integer(), nullable=True),
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
        "strava_activity_zone_buckets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("activity_id", sa.BigInteger(), sa.ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False),
        sa.Column("athlete_id", sa.BigInteger(), nullable=True),
        sa.Column("zone_type", sa.String(length=50), nullable=False),
        sa.Column("bucket_index", sa.Integer(), nullable=False),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column("time_seconds", sa.Integer(), nullable=True),
        sa.Column("sensor_based", sa.Boolean(), nullable=True),
        sa.Column("custom_zones", sa.Boolean(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="strava"),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("activity_id", "zone_type", "bucket_index", name="uq_strava_zone_bucket_activity_type_index"),
    )
    op.create_index("idx_strava_zone_buckets_activity", "strava_activity_zone_buckets", ["activity_id", "zone_type"])
    op.create_index("idx_strava_zone_buckets_athlete", "strava_activity_zone_buckets", ["athlete_id", "zone_type", "bucket_index"])
    op.create_index("idx_strava_zone_buckets_range", "strava_activity_zone_buckets", ["zone_type", "min_value", "max_value"])

    op.create_table(
        "strava_athlete_zones",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("athlete_id", sa.BigInteger(), nullable=False),
        sa.Column("zone_type", sa.String(length=50), nullable=False),
        sa.Column("bucket_index", sa.Integer(), nullable=False),
        sa.Column("min_value", sa.Float(), nullable=True),
        sa.Column("max_value", sa.Float(), nullable=True),
        sa.Column("custom_zones", sa.Boolean(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="strava"),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("raw_data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_strava_athlete_zones_effective", "strava_athlete_zones", ["athlete_id", "zone_type", "effective_at"])
    op.create_index("idx_strava_athlete_zones_bucket", "strava_athlete_zones", ["athlete_id", "zone_type", "bucket_index"])

    op.create_table(
        "strava_activity_metrics",
        sa.Column("activity_id", sa.BigInteger(), sa.ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("moving_time_seconds", sa.Integer(), nullable=True),
        sa.Column("elapsed_time_seconds", sa.Integer(), nullable=True),
        sa.Column("pace_seconds_per_km", sa.Float(), nullable=True),
        sa.Column("gap_seconds_per_km", sa.Float(), nullable=True),
        sa.Column("average_speed_kmh", sa.Float(), nullable=True),
        sa.Column("average_grade_adjusted_speed_kmh", sa.Float(), nullable=True),
        sa.Column("average_cadence_spm", sa.Float(), nullable=True),
        sa.Column("hr_zone_1_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("hr_zone_2_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("hr_zone_3_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("hr_zone_4_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("hr_zone_5_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_hr_zone_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("easy_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("moderate_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("hard_seconds", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("lap_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("split_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("best_effort_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("fastest_split_pace_seconds_per_km", sa.Float(), nullable=True),
        sa.Column("fastest_split_gap_seconds_per_km", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    _drop_redesigned_tables()
