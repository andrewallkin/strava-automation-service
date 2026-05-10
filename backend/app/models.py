from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strava_athlete_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    run_shoe_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    gym_hide_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    athlete_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    athlete_profile_url: Mapped[str | None] = mapped_column(Text, nullable=True)


class McpApiKey(Base):
    __tablename__ = "mcp_api_keys"
    __table_args__ = (
        Index("idx_mcp_api_keys_user", "user_id", "created_at"),
        Index("idx_mcp_api_keys_hash", "key_hash", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserOpenAiApiKey(Base):
    """Encrypted OpenAI API key for vector store / OpenAI UI (plaintext only in memory)."""

    __tablename__ = "user_openai_api_keys"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class Gear(Base):
    __tablename__ = "gear"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strava_gear_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    nickname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    brand_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    retired: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notification_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PendingActivity(Base):
    __tablename__ = "pending_activities"
    __table_args__ = (UniqueConstraint("activity_id", name="uq_pending_activity_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class EventLog(Base):
    __tablename__ = "event_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class StravaActivity(Base):
    __tablename__ = "strava_activities"
    __table_args__ = (
        Index("idx_strava_activities_athlete_start", "athlete_id", "start_date_local"),
        Index("idx_strava_activities_type_start", "sport_type", "start_date_local"),
        Index("idx_strava_activities_local_date", "local_date"),
        Index("idx_strava_activities_year_month", "local_year", "local_month"),
        Index(
            "idx_strava_activities_not_deleted",
            "start_date_local",
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    activity_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    athlete_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    activity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sport_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    workout_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_date_local: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    local_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    local_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    local_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    moving_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    elev_high_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    elev_low_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_grade_adjusted_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    gap_source: Mapped[str] = mapped_column(String(32), default="unavailable", nullable=False)
    has_heartrate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    average_heartrate_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_heartrate_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_cadence_spm: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_watts: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_watts: Mapped[float | None] = mapped_column(Float, nullable=True)
    weighted_average_watts: Mapped[float | None] = mapped_column(Float, nullable=True)
    kilojoules: Mapped[float | None] = mapped_column(Float, nullable=True)
    device_watts: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    calories: Mapped[float | None] = mapped_column(Float, nullable=True)
    suffer_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    trainer: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    commute: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    manual: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    private: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    flagged: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    hide_from_home: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    gear_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    device_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_laps: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_splits: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_best_efforts: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_zones: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_gap: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data_quality: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    detail_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StravaActivityLap(Base):
    __tablename__ = "strava_activity_laps"
    __table_args__ = (
        UniqueConstraint("activity_id", "lap_index", name="uq_strava_lap_activity_index"),
        Index("idx_strava_laps_activity", "activity_id", "lap_index"),
        Index("idx_strava_laps_start", "start_date_local"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False
    )
    athlete_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    lap_index: Mapped[int] = mapped_column(Integer, nullable=False)
    lap_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    split: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_date_local: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    moving_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_grade_adjusted_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    gap_source: Mapped[str] = mapped_column(String(32), default="unavailable", nullable=False)
    average_heartrate_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_heartrate_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_cadence_spm: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_watts: Mapped[float | None] = mapped_column(Float, nullable=True)
    device_watts: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    total_elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    pace_zone: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

class StravaActivitySplit(Base):
    __tablename__ = "strava_activity_splits"
    __table_args__ = (
        UniqueConstraint("activity_id", "split_source", "split", name="uq_strava_split_activity_source_split"),
        Index("idx_strava_splits_activity", "activity_id", "split_source", "split"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False
    )
    split_source: Mapped[str] = mapped_column(String(20), nullable=False)
    split: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    moving_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_grade_adjusted_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    gap_source: Mapped[str] = mapped_column(String(32), default="unavailable", nullable=False)
    average_heartrate_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_difference_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    pace_zone: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class StravaActivityBestEffort(Base):
    __tablename__ = "strava_activity_best_efforts"
    __table_args__ = (
        Index("idx_strava_best_efforts_activity", "activity_id"),
        Index("idx_strava_best_efforts_name", "name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False
    )
    best_effort_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    moving_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_date_local: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class StravaActivityZoneBucket(Base):
    __tablename__ = "strava_activity_zone_buckets"
    __table_args__ = (
        UniqueConstraint("activity_id", "zone_type", "bucket_index", name="uq_strava_zone_bucket_activity_type_index"),
        Index("idx_strava_zone_buckets_activity", "activity_id", "zone_type"),
        Index("idx_strava_zone_buckets_athlete", "athlete_id", "zone_type", "bucket_index"),
        Index("idx_strava_zone_buckets_range", "zone_type", "min_value", "max_value"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False
    )
    athlete_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    zone_type: Mapped[str] = mapped_column(String(50), nullable=False)
    bucket_index: Mapped[int] = mapped_column(Integer, nullable=False)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sensor_based: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    custom_zones: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="strava", nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class StravaAthleteZone(Base):
    __tablename__ = "strava_athlete_zones"
    __table_args__ = (
        Index("idx_strava_athlete_zones_effective", "athlete_id", "zone_type", "effective_at"),
        Index("idx_strava_athlete_zones_bucket", "athlete_id", "zone_type", "bucket_index"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    athlete_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    zone_type: Mapped[str] = mapped_column(String(50), nullable=False)
    bucket_index: Mapped[int] = mapped_column(Integer, nullable=False)
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    custom_zones: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="strava", nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class StravaActivityMetric(Base):
    __tablename__ = "strava_activity_metrics"

    activity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), primary_key=True
    )
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    moving_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pace_seconds_per_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    gap_seconds_per_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_grade_adjusted_speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_cadence_spm: Mapped[float | None] = mapped_column(Float, nullable=True)
    hr_zone_1_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hr_zone_2_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hr_zone_3_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hr_zone_4_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hr_zone_5_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_hr_zone_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    easy_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    moderate_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hard_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lap_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    split_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_effort_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fastest_split_pace_seconds_per_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    fastest_split_gap_seconds_per_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class StravaIngestionJob(Base):
    __tablename__ = "strava_ingestion_jobs"
    __table_args__ = (
        Index("idx_strava_ingestion_jobs_status", "status", "queued_at"),
        Index("idx_strava_ingestion_jobs_activity", "activity_id", "queued_at"),
        Index("idx_strava_ingestion_jobs_backfill", "backfill_run_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    athlete_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    aspect_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    backfill_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("strava_backfill_runs.id", ondelete="SET NULL"), nullable=True
    )
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class StravaBackfillRun(Base):
    __tablename__ = "strava_backfill_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    athlete_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    force_refresh: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Jobs still queued or running (updated as ingestion progresses; not a historical snapshot).
    queued_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    succeeded_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    rate_limit_wait_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rate_limit_wait_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class AthleteProfile(Base):
    __tablename__ = "athlete_profile"

    athlete_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    firstname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lastname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    premium: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    summit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    ftp_watts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    athlete_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    measurement_preference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    strava_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class AthleteStats(Base):
    __tablename__ = "athlete_stats"

    athlete_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    biggest_ride_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    biggest_climb_elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    recent_ride_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recent_ride_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    recent_ride_moving_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recent_ride_elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recent_ride_elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    recent_ride_achievement_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    recent_run_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recent_run_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    recent_run_moving_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recent_run_elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recent_run_elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    recent_run_achievement_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    recent_swim_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recent_swim_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    recent_swim_moving_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recent_swim_elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recent_swim_elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    recent_swim_achievement_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    all_ride_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    all_ride_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    all_ride_moving_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    all_ride_elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    all_ride_elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    all_run_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    all_run_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    all_run_moving_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    all_run_elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    all_run_elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    all_swim_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    all_swim_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    all_swim_moving_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    all_swim_elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    all_swim_elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    ytd_ride_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ytd_ride_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_ride_moving_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ytd_ride_elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ytd_ride_elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    ytd_run_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ytd_run_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_run_moving_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ytd_run_elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ytd_run_elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    ytd_swim_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ytd_swim_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    ytd_swim_moving_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ytd_swim_elapsed_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ytd_swim_elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    raw_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
