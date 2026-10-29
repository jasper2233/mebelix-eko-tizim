"""eko 3d integ outbox

Revision ID: f0e248d647d3
Revises: 5d303c1fddc8
Create Date: 2026-10-29 11:50:23.165359

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f0e248d647d3"
down_revision: Union[str, None] = "5d303c1fddc8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integ_outbox",
        sa.Column("manba", sa.String(length=20), nullable=False),
        sa.Column("kalit", sa.String(length=200), nullable=False),
        sa.Column("method", sa.String(length=8), nullable=False),
        sa.Column("path", sa.String(length=300), nullable=False),
        sa.Column("body", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("holat", sa.String(length=10), nullable=False),
        sa.Column("urinish", sa.Integer(), server_default="0", nullable=False),
        sa.Column("keyingi_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("yuborilgan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("xato", sa.String(length=300), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integ_outbox_kalit", "integ_outbox", ["manba", "kalit"], unique=True)
    op.create_index(
        "ix_integ_outbox_navbat",
        "integ_outbox",
        ["manba", "id"],
        unique=False,
        postgresql_where=sa.text("holat = 'yangi'"),
    )


def downgrade() -> None:
    op.drop_index("ix_integ_outbox_navbat", table_name="integ_outbox", postgresql_where=sa.text("holat = 'yangi'"))
    op.drop_index("ix_integ_outbox_kalit", table_name="integ_outbox")
    op.drop_table("integ_outbox")
