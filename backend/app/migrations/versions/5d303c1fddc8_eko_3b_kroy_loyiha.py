"""eko 3b kroy loyiha

Revision ID: 5d303c1fddc8
Revises: 244608b72e61
Create Date: 2026-10-29 11:08:14.180080

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5d303c1fddc8"
down_revision: Union[str, None] = "244608b72e61"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kroy_loyiha",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(length=40), nullable=False),
        sa.Column("number", sa.String(length=40), nullable=False),
        sa.Column("holat", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["order.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id"),
        sa.UniqueConstraint("project_id"),
    )


def downgrade() -> None:
    op.drop_table("kroy_loyiha")
