"""add mcp api keys

Revision ID: 0006_mcp_api_keys
Revises: 0005_strava_mcp_schema
Create Date: 2026-05-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0006_mcp_api_keys"
down_revision: str | None = "0005_strava_mcp_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_api_keys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_mcp_api_keys_user", "mcp_api_keys", ["user_id", "created_at"])
    op.create_index("idx_mcp_api_keys_hash", "mcp_api_keys", ["key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("idx_mcp_api_keys_hash", table_name="mcp_api_keys")
    op.drop_index("idx_mcp_api_keys_user", table_name="mcp_api_keys")
    op.drop_table("mcp_api_keys")
