"""mcp oauth clients and grants

Revision ID: 0014_mcp_oauth
Revises: 0013_telegram_commands
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_mcp_oauth"
down_revision: str | None = "0013_telegram_commands"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_oauth_clients",
        sa.Column("client_id", sa.String(length=255), primary_key=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "mcp_oauth_grants",
        sa.Column("token_hash", sa.String(length=64), primary_key=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("partner_hash", sa.String(length=64), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_mcp_oauth_grants_user", "mcp_oauth_grants", ["user_id", "kind"])


def downgrade() -> None:
    op.drop_index("idx_mcp_oauth_grants_user", table_name="mcp_oauth_grants")
    op.drop_table("mcp_oauth_grants")
    op.drop_table("mcp_oauth_clients")
