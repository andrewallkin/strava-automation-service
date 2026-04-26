from datetime import date, datetime

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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
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


class Gear(Base):
    __tablename__ = "gear"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strava_gear_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


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
        Index("idx_strava_activities_detail_gin", "detail_data", postgresql_using="gin"),
        Index("idx_strava_activities_metadata_gin", "metadata", postgresql_using="gin"),
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
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_date_local: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone: Mapped[str | None] = mapped_column(Text, nullable=True)
    distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    moving_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elapsed_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_elevation_gain: Mapped[float | None] = mapped_column(Float, nullable=True)
    elev_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    elev_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    has_heartrate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    average_heartrate: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_heartrate: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_cadence: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_watts: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_watts: Mapped[float | None] = mapped_column(Float, nullable=True)
    weighted_average_watts: Mapped[float | None] = mapped_column(Float, nullable=True)
    kilojoules: Mapped[float | None] = mapped_column(Float, nullable=True)
    device_watts: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    calories: Mapped[float | None] = mapped_column(Float, nullable=True)
    suffer_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    gear_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trainer: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    commute: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    manual: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    private: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    flagged: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    hide_from_home: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    workout_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    achievement_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kudos_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    athlete_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    map_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    summary_polyline: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_latlng: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    end_latlng: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    has_laps: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_splits: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_segments: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_best_efforts: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_zones: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_streams: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    detail_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ingestion_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
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
    lap_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    activity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False
    )
    athlete_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    lap_index: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    split: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_date_local: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    moving_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elapsed_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_heartrate: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_heartrate: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_cadence: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_watts: Mapped[float | None] = mapped_column(Float, nullable=True)
    device_watts: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    total_elevation_gain: Mapped[float | None] = mapped_column(Float, nullable=True)
    pace_zone: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class StravaActivitySegmentEffort(Base):
    __tablename__ = "strava_activity_segment_efforts"
    __table_args__ = (
        Index("idx_strava_segment_efforts_activity", "activity_id"),
        Index("idx_strava_segment_efforts_segment", "segment_id", "start_date_local"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    segment_effort_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    activity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    segment_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    segment_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_date_local: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    moving_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elapsed_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_heartrate: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_heartrate: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_cadence: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_watts: Mapped[float | None] = mapped_column(Float, nullable=True)
    device_watts: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_kom: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    kom_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hidden: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
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
    distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    moving_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elapsed_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_difference: Mapped[float | None] = mapped_column(Float, nullable=True)
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
    best_effort_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    activity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    distance: Mapped[float | None] = mapped_column(Float, nullable=True)
    moving_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elapsed_time: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_date_local: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pr_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class StravaActivityZone(Base):
    __tablename__ = "strava_activity_zones"
    __table_args__ = (
        UniqueConstraint("activity_id", "zone_type", name="uq_strava_zone_activity_type"),
        Index("idx_strava_zones_activity", "activity_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), nullable=False
    )
    zone_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="strava", nullable=False)
    raw_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class StravaActivityStream(Base):
    __tablename__ = "strava_activity_streams"
    __table_args__ = (
        Index("idx_strava_streams_keys", "stream_keys", postgresql_using="gin"),
    )

    activity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("strava_activities.activity_id", ondelete="CASCADE"), primary_key=True
    )
    stream_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    stream_keys: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    series_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    first_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
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
    queued_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    succeeded_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
