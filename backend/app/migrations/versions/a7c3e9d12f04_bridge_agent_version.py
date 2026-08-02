"""bridge_agent.version — agent exe versiyasi (X-Agent-Version headeridan)

Revision ID: a7c3e9d12f04
Revises: f4b8c2a91e55
Create Date: 2026-08-02
"""

import sqlalchemy as sa
from alembic import op

revision = "a7c3e9d12f04"
down_revision = "f4b8c2a91e55"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bridge_agent", sa.Column("version", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("bridge_agent", "version")
