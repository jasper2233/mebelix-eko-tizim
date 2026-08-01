"""bridge_agent.machine_id — skan-forvard: agent skanini qaysi stanok nomidan yozish

Revision ID: f4b8c2a91e55
Revises: d5e81a24c3b7
Create Date: 2026-08-01
"""

import sqlalchemy as sa
from alembic import op

revision = "f4b8c2a91e55"
down_revision = "d5e81a24c3b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bridge_agent",
        sa.Column("machine_id", sa.Integer(), sa.ForeignKey("machine.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("bridge_agent", "machine_id")
