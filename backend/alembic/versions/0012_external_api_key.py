"""external API key columns and drop coach-only tables

Revision ID: 0012_external_api_key
Revises: 0011_user_coach_settings
Create Date: 2026-10-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_external_api_key"
down_revision: str | None = "0011_user_coach_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("external_api_key_prefix", sa.String(length=12), nullable=True))
    op.add_column("users", sa.Column("external_api_key_hash", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("external_api_key_created_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("idx_users_external_api_key_prefix", "users", ["external_api_key_prefix"])
    op.drop_table("user_coach_settings")
    op.drop_table("user_openai_api_keys")


def downgrade() -> None:
    op.create_table(
        "user_openai_api_keys",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "user_coach_settings",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("vector_store_id", sa.String(length=255), nullable=True),
        sa.Column("agent_name", sa.String(length=255), nullable=False, server_default="Coach"),
        sa.Column("agent_instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column("openai_model", sa.String(length=128), nullable=False, server_default="gpt-4.1-mini"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.drop_index("idx_users_external_api_key_prefix", table_name="users")
    op.drop_column("users", "external_api_key_created_at")
    op.drop_column("users", "external_api_key_hash")
    op.drop_column("users", "external_api_key_prefix")
