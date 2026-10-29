"""eko 3e kroy katalog

Revision ID: 9e40040d8960
Revises: f0e248d647d3
Create Date: 2026-10-29 12:02:06.716084

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9e40040d8960"
down_revision: Union[str, None] = "f0e248d647d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kroy_katalog",
        sa.Column("kod", sa.String(length=64), nullable=False),
        sa.Column("xesh", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kod"),
    )
    op.alter_column("integ_outbox", "body", existing_type=postgresql.JSONB(astext_type=sa.Text()), nullable=False)


def downgrade() -> None:
    op.alter_column("integ_outbox", "body", existing_type=postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    op.drop_table("kroy_katalog")
