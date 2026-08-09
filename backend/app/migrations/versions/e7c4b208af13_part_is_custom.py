"""Nostandart detal bayrog'i: part.is_custom.

Texnolog matritsada detalni "nostandart" deb belgilaydi va marshrutini alohida tabda
qo'lda chizadi. Standart detal fayldan avtomatik marshrut oladi (ARRA + kromka +
prisadka); nostandart detalda avtomatika umuman ishlamaydi.

Revision ID: e7c4b208af13
Revises: d5a1c93b70e2
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op

revision = "e7c4b208af13"
down_revision = "d5a1c93b70e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("part", sa.Column("is_custom", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("part", "is_custom", server_default=None)
    op.create_index("ix_part_is_custom", "part", ["is_custom"])


def downgrade() -> None:
    op.drop_index("ix_part_is_custom", table_name="part")
    op.drop_column("part", "is_custom")
