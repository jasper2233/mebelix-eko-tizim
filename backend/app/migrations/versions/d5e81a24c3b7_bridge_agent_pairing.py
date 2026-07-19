"""bridge_agent — printer agentlari: ulanish kodi (pairing) + token xeshi

Revision ID: d5e81a24c3b7
Revises: a91c7d34f6e2
Create Date: 2026-07-19
"""

import sqlalchemy as sa
from alembic import op

revision = "d5e81a24c3b7"
down_revision = "a91c7d34f6e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bridge_agent",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organization.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=True),
        sa.Column("pair_code", sa.String(16), nullable=True),
        sa.Column("pair_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=True
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_bridge_agent_token_hash", "bridge_agent", ["token_hash"], unique=True)
    op.create_index("ix_bridge_agent_pair_code", "bridge_agent", ["pair_code"])
    op.create_index("ix_bridge_agent_is_deleted", "bridge_agent", ["is_deleted"])


def downgrade() -> None:
    op.drop_table("bridge_agent")
