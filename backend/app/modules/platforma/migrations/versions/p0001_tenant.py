"""tenant — obunachilar ro'yxati (EKO TIZIM TZ §2.4)

Revision ID: p0001
Revises:
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "p0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenant",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kod", sa.String(31), nullable=False, unique=True),
        sa.Column("nomi", sa.String(200), nullable=False),
        sa.Column("holat", sa.String(20), nullable=False, server_default="faol"),
        sa.Column("modules", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("tenant")
