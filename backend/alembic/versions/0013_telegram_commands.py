"""telegram rename waits and weekly digest sends

Revision ID: 0013_telegram_commands
Revises: 0012_external_api_key
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_telegram_commands"
down_revision: str | None = "0012_external_api_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_rename_waits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("activity_id", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("chat_id", name="uq_telegram_rename_wait_chat"),
    )
    op.create_table(
        "weekly_digest_sends",
        sa.Column("week_start", sa.Date(), primary_key=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("weekly_digest_sends")
    op.drop_table("telegram_rename_waits")
