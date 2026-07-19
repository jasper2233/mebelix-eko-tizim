"""order.survey — mijoz anketasi va o'lchov varag'i (xonalar bo'yicha)

Revision ID: a91c7d34f6e2
Revises: 7d2c9f5e1b3a
Create Date: 2026-07-19
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "a91c7d34f6e2"
down_revision = "7d2c9f5e1b3a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order", sa.Column("survey", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("order", "survey")
