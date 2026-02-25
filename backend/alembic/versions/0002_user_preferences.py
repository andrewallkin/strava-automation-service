"""user preferences

Revision ID: 0002_user_preferences
Revises: 0001_initial
Create Date: 2026-02-24

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_user_preferences"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("run_shoe_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("users", sa.Column("gym_hide_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))


def downgrade() -> None:
    op.drop_column("users", "gym_hide_enabled")
    op.drop_column("users", "run_shoe_enabled")
