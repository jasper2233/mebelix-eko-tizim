"""eko 10b stanok asbob

Revision ID: eb9573545e9c
Revises: 96af7a9a9293
Create Date: 2026-10-29 17:50:01.210019

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eb9573545e9c"
down_revision: Union[str, None] = "96af7a9a9293"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "asbob_stavka",
        sa.Column("amal", sa.String(length=16), nullable=False),
        sa.Column("narx", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("amal_boshi", sa.Date(), nullable=False),
        sa.Column("yozgan_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "amal IN ('teshik', 'qirra_teshik', 'paz', 'freza', 'rover_metr', 'kromka_metr', 'arra_m2')",
            name="ck_asbob_stavka_amal",
        ),
        sa.CheckConstraint("narx >= 0", name="ck_asbob_stavka_narx"),
        sa.ForeignKeyConstraint(
            ["yozgan_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_asbob_stavka_kalit", "asbob_stavka", ["amal", "amal_boshi"], unique=True)
    op.create_table(
        "stanok_narx",
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("soat_narxi", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("amal_boshi", sa.Date(), nullable=False),
        sa.Column("yozgan_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.CheckConstraint("soat_narxi >= 0", name="ck_stanok_narx_soat"),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["machine.id"],
        ),
        sa.ForeignKeyConstraint(
            ["yozgan_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stanok_narx_kalit", "stanok_narx", ["machine_id", "amal_boshi"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_stanok_narx_kalit", table_name="stanok_narx")
    op.drop_table("stanok_narx")
    op.drop_index("ix_asbob_stavka_kalit", table_name="asbob_stavka")
    op.drop_table("asbob_stavka")
