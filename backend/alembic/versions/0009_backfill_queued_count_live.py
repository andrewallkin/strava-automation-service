"""recompute backfill queued_count as pending jobs

Revision ID: 0009_backfill_queued_live
Revises: 0008_backfill_rate_limit
Create Date: 2026-05-03

queued_count is maintained as the number of ingestion jobs still queued or running.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009_backfill_queued_live"
down_revision: str | None = "0008_backfill_rate_limit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE strava_backfill_runs AS r
        SET queued_count = COALESCE(
            (
                SELECT COUNT(*)::integer
                FROM strava_ingestion_jobs AS j
                WHERE j.backfill_run_id = r.id
                  AND j.status IN ('queued', 'running')
            ),
            0
        )
        WHERE EXISTS (
            SELECT 1 FROM strava_ingestion_jobs AS j WHERE j.backfill_run_id = r.id
        )
        """
    )


def downgrade() -> None:
    # Cannot restore prior snapshot totals; new rows use live semantics only.
    pass
