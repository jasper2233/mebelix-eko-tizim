"""order advance_payment (boshlang'ich to'lov)

Revision ID: 7d2c9f5e1b3a
Revises: 3b4e0b90f440
Create Date: 2026-07-10
"""

import sqlalchemy as sa
from alembic import op

revision = "7d2c9f5e1b3a"
down_revision = "3b4e0b90f440"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("order", sa.Column("advance_payment", sa.Numeric(14, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("order", "advance_payment")
