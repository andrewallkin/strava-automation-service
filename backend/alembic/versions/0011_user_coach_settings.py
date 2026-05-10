"""user coach settings per user

Revision ID: 0011_user_coach_settings
Revises: 0010_user_openai_api_keys
Create Date: 2026-05-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_user_coach_settings"
down_revision: str | None = "0010_user_openai_api_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_coach_settings",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("vector_store_id", sa.String(length=255), nullable=True),
        sa.Column("agent_name", sa.String(length=255), nullable=False, server_default="Coach"),
        sa.Column("agent_instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column("openai_model", sa.String(length=128), nullable=False, server_default="gpt-4.1-mini"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_table("user_coach_settings")
