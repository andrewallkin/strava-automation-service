"""backfill rate limit wait status

Revision ID: 0008_backfill_rate_limit_wait
Revises: 0007_athlete_expand
Create Date: 2026-05-03

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0008_backfill_rate_limit"
down_revision: str | None = "0007_athlete_expand"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "strava_backfill_runs",
        sa.Column("rate_limit_wait_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "strava_backfill_runs",
        sa.Column("rate_limit_wait_reason", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("strava_backfill_runs", "rate_limit_wait_reason")
    op.drop_column("strava_backfill_runs", "rate_limit_wait_until")
