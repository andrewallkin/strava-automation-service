"""athlete profile

Revision ID: 0003_athlete_profile
Revises: 0002_user_preferences
Create Date: 2026-02-26

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_athlete_profile"
down_revision: str | None = "0002_user_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("athlete_name", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("athlete_profile_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "athlete_profile_url")
    op.drop_column("users", "athlete_name")
