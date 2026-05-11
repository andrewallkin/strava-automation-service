"""user openai api keys (encrypted)

Revision ID: 0010_user_openai_api_keys
Revises: 0009_backfill_queued_live
Create Date: 2026-05-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_user_openai_api_keys"
down_revision: str | None = "0009_backfill_queued_live"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_openai_api_keys",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.String(length=64), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_table("user_openai_api_keys")
