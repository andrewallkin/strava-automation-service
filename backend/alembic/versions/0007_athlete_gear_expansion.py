"""athlete profile, athlete stats, gear detail expansion

Revision ID: 0007_athlete_gear_expansion
Revises: 0006_mcp_api_keys
Create Date: 2026-05-02

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0007_athlete_expand"
down_revision: str | None = "0006_mcp_api_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Expand gear table with full detail fields
    op.add_column("gear", sa.Column("nickname", sa.String(255), nullable=True))
    op.add_column("gear", sa.Column("distance_m", sa.Float(), nullable=True))
    op.add_column("gear", sa.Column("brand_name", sa.String(255), nullable=True))
    op.add_column("gear", sa.Column("model_name", sa.String(255), nullable=True))
    op.add_column("gear", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("gear", sa.Column("retired", sa.Boolean(), nullable=True))
    op.add_column("gear", sa.Column("notification_distance_m", sa.Float(), nullable=True))
    op.add_column("gear", sa.Column("raw_data", JSONB(), nullable=True))
    op.add_column("gear", sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True))

    # athlete_profile: one row per athlete, upserted on each sync
    op.create_table(
        "athlete_profile",
        sa.Column("athlete_id", sa.BigInteger(), primary_key=True),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("firstname", sa.String(255), nullable=True),
        sa.Column("lastname", sa.String(255), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("city", sa.String(255), nullable=True),
        sa.Column("state", sa.String(255), nullable=True),
        sa.Column("country", sa.String(255), nullable=True),
        sa.Column("sex", sa.String(10), nullable=True),
        sa.Column("premium", sa.Boolean(), nullable=True),
        sa.Column("summit", sa.Boolean(), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("ftp_watts", sa.Integer(), nullable=True),
        sa.Column("athlete_type", sa.Integer(), nullable=True),
        sa.Column("measurement_preference", sa.String(50), nullable=True),
        sa.Column("strava_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_data", JSONB(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # athlete_stats: one row per athlete, upserted on each sync
    op.create_table(
        "athlete_stats",
        sa.Column("athlete_id", sa.BigInteger(), primary_key=True),

        sa.Column("biggest_ride_distance_m", sa.Float(), nullable=True),
        sa.Column("biggest_climb_elevation_gain_m", sa.Float(), nullable=True),

        sa.Column("recent_ride_count", sa.Integer(), nullable=True),
        sa.Column("recent_ride_distance_m", sa.Float(), nullable=True),
        sa.Column("recent_ride_moving_time_seconds", sa.Integer(), nullable=True),
        sa.Column("recent_ride_elapsed_time_seconds", sa.Integer(), nullable=True),
        sa.Column("recent_ride_elevation_gain_m", sa.Float(), nullable=True),
        sa.Column("recent_ride_achievement_count", sa.Integer(), nullable=True),

        sa.Column("recent_run_count", sa.Integer(), nullable=True),
        sa.Column("recent_run_distance_m", sa.Float(), nullable=True),
        sa.Column("recent_run_moving_time_seconds", sa.Integer(), nullable=True),
        sa.Column("recent_run_elapsed_time_seconds", sa.Integer(), nullable=True),
        sa.Column("recent_run_elevation_gain_m", sa.Float(), nullable=True),
        sa.Column("recent_run_achievement_count", sa.Integer(), nullable=True),

        sa.Column("recent_swim_count", sa.Integer(), nullable=True),
        sa.Column("recent_swim_distance_m", sa.Float(), nullable=True),
        sa.Column("recent_swim_moving_time_seconds", sa.Integer(), nullable=True),
        sa.Column("recent_swim_elapsed_time_seconds", sa.Integer(), nullable=True),
        sa.Column("recent_swim_elevation_gain_m", sa.Float(), nullable=True),
        sa.Column("recent_swim_achievement_count", sa.Integer(), nullable=True),

        sa.Column("all_ride_count", sa.Integer(), nullable=True),
        sa.Column("all_ride_distance_m", sa.Float(), nullable=True),
        sa.Column("all_ride_moving_time_seconds", sa.Integer(), nullable=True),
        sa.Column("all_ride_elapsed_time_seconds", sa.Integer(), nullable=True),
        sa.Column("all_ride_elevation_gain_m", sa.Float(), nullable=True),

        sa.Column("all_run_count", sa.Integer(), nullable=True),
        sa.Column("all_run_distance_m", sa.Float(), nullable=True),
        sa.Column("all_run_moving_time_seconds", sa.Integer(), nullable=True),
        sa.Column("all_run_elapsed_time_seconds", sa.Integer(), nullable=True),
        sa.Column("all_run_elevation_gain_m", sa.Float(), nullable=True),

        sa.Column("all_swim_count", sa.Integer(), nullable=True),
        sa.Column("all_swim_distance_m", sa.Float(), nullable=True),
        sa.Column("all_swim_moving_time_seconds", sa.Integer(), nullable=True),
        sa.Column("all_swim_elapsed_time_seconds", sa.Integer(), nullable=True),
        sa.Column("all_swim_elevation_gain_m", sa.Float(), nullable=True),

        sa.Column("ytd_ride_count", sa.Integer(), nullable=True),
        sa.Column("ytd_ride_distance_m", sa.Float(), nullable=True),
        sa.Column("ytd_ride_moving_time_seconds", sa.Integer(), nullable=True),
        sa.Column("ytd_ride_elapsed_time_seconds", sa.Integer(), nullable=True),
        sa.Column("ytd_ride_elevation_gain_m", sa.Float(), nullable=True),

        sa.Column("ytd_run_count", sa.Integer(), nullable=True),
        sa.Column("ytd_run_distance_m", sa.Float(), nullable=True),
        sa.Column("ytd_run_moving_time_seconds", sa.Integer(), nullable=True),
        sa.Column("ytd_run_elapsed_time_seconds", sa.Integer(), nullable=True),
        sa.Column("ytd_run_elevation_gain_m", sa.Float(), nullable=True),

        sa.Column("ytd_swim_count", sa.Integer(), nullable=True),
        sa.Column("ytd_swim_distance_m", sa.Float(), nullable=True),
        sa.Column("ytd_swim_moving_time_seconds", sa.Integer(), nullable=True),
        sa.Column("ytd_swim_elapsed_time_seconds", sa.Integer(), nullable=True),
        sa.Column("ytd_swim_elevation_gain_m", sa.Float(), nullable=True),

        sa.Column("raw_data", JSONB(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("athlete_stats")
    op.drop_table("athlete_profile")

    op.drop_column("gear", "fetched_at")
    op.drop_column("gear", "raw_data")
    op.drop_column("gear", "notification_distance_m")
    op.drop_column("gear", "retired")
    op.drop_column("gear", "description")
    op.drop_column("gear", "model_name")
    op.drop_column("gear", "brand_name")
    op.drop_column("gear", "distance_m")
    op.drop_column("gear", "nickname")
