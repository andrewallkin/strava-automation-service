"""initial tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("strava_athlete_id", sa.BigInteger(), nullable=True, unique=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True, unique=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "gear",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("strava_gear_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_table(
        "pending_activities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("activity_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("activity_id", name="uq_pending_activity_id"),
    )
    op.create_table(
        "event_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_event_log_created_at", "event_log", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_event_log_created_at", table_name="event_log")
    op.drop_table("event_log")
    op.drop_table("pending_activities")
    op.drop_table("gear")
    op.drop_table("users")
