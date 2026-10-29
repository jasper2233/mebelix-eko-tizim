"""eko 2.3b ombor bolak

Revision ID: d5f2d32fb705
Revises: 8e885719d47a
Create Date: 2026-10-29 10:19:12.726682

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5f2d32fb705"
down_revision: Union[str, None] = "8e885719d47a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ombor_bolak",
        sa.Column("waste_id", sa.Integer(), nullable=False),
        sa.Column("barkod", sa.String(length=120), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("material_nom", sa.String(length=150), nullable=False),
        sa.Column("uzunlik", sa.Numeric(precision=8, scale=1), nullable=False),
        sa.Column("eni", sa.Numeric(precision=8, scale=1), nullable=False),
        sa.Column("manba_order_id", sa.Integer(), nullable=False),
        sa.Column("joy", sa.String(length=12), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("qabul_by_id", sa.Integer(), nullable=True),
        sa.Column("yopilgan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["catalog_item.id"],
        ),
        sa.ForeignKeyConstraint(
            ["manba_order_id"],
            ["order.id"],
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["order.id"],
        ),
        sa.ForeignKeyConstraint(
            ["qabul_by_id"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["waste_id"],
            ["waste_item.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ombor_bolak_barkod"), "ombor_bolak", ["barkod"], unique=False)
    op.create_index("ix_ombor_bolak_joy_item", "ombor_bolak", ["joy", "item_id"], unique=False)
    op.create_index(
        "ix_ombor_bolak_waste", "ombor_bolak", ["waste_id"], unique=True, postgresql_where=sa.text("NOT is_deleted")
    )


def downgrade() -> None:
    op.drop_index("ix_ombor_bolak_waste", table_name="ombor_bolak", postgresql_where=sa.text("NOT is_deleted"))
    op.drop_index("ix_ombor_bolak_joy_item", table_name="ombor_bolak")
    op.drop_index(op.f("ix_ombor_bolak_barkod"), table_name="ombor_bolak")
    op.drop_table("ombor_bolak")
