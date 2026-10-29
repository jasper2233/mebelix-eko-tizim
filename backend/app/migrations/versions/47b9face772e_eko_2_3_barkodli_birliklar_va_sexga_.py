"""eko 2.3 barkodli birliklar va sexga berish

Revision ID: 47b9face772e
Revises: d5b092eb17e0
Create Date: 2026-10-29 09:57:44.312448

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "47b9face772e"
down_revision: Union[str, None] = "d5b092eb17e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "material_birlik",
        sa.Column("barkod", sa.String(length=20), nullable=True),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("ishlab_kod", sa.String(length=60), nullable=True),
        sa.Column("hajm", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("qoldiq", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("joy", sa.String(length=10), nullable=False),
        sa.Column("doc_id", sa.Integer(), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("sexga_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["doc_id"],
            ["stock_doc.id"],
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["catalog_item.id"],
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["order.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("barkod"),
    )
    op.create_index(op.f("ix_material_birlik_item_id"), "material_birlik", ["item_id"], unique=False)
    op.create_index(
        "ix_material_birlik_item_joy",
        "material_birlik",
        ["item_id", "joy", "id"],
        unique=False,
        postgresql_where=sa.text("qoldiq > 0"),
    )
    op.add_column("catalog_item", sa.Column("birlik_hajm", sa.Numeric(precision=12, scale=3), nullable=True))
    op.add_column("catalog_item", sa.Column("ishlab_barkod", sa.String(length=40), nullable=True))
    op.create_index(op.f("ix_catalog_item_ishlab_barkod"), "catalog_item", ["ishlab_barkod"], unique=False)
    op.add_column(
        "rezerv_line", sa.Column("berilgan_qty", sa.Numeric(precision=14, scale=3), server_default="0", nullable=False)
    )
    op.add_column("stock_doc_line", sa.Column("hajm", sa.Numeric(precision=12, scale=3), nullable=True))
    op.add_column("stock_movement", sa.Column("order_id", sa.Integer(), nullable=True))
    op.add_column("stock_movement", sa.Column("birlik_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_stock_movement_order_id"), "stock_movement", ["order_id"], unique=False)
    op.create_foreign_key("stock_movement_order_id_fkey", "stock_movement", "order", ["order_id"], ["id"])
    op.create_foreign_key("stock_movement_birlik_id_fkey", "stock_movement", "material_birlik", ["birlik_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("stock_movement_birlik_id_fkey", "stock_movement", type_="foreignkey")
    op.drop_constraint("stock_movement_order_id_fkey", "stock_movement", type_="foreignkey")
    op.drop_index(op.f("ix_stock_movement_order_id"), table_name="stock_movement")
    op.drop_column("stock_movement", "birlik_id")
    op.drop_column("stock_movement", "order_id")
    op.drop_column("stock_doc_line", "hajm")
    op.drop_column("rezerv_line", "berilgan_qty")
    op.drop_index(op.f("ix_catalog_item_ishlab_barkod"), table_name="catalog_item")
    op.drop_column("catalog_item", "ishlab_barkod")
    op.drop_column("catalog_item", "birlik_hajm")
    op.drop_index("ix_material_birlik_item_joy", table_name="material_birlik", postgresql_where=sa.text("qoldiq > 0"))
    op.drop_index(op.f("ix_material_birlik_item_id"), table_name="material_birlik")
    op.drop_table("material_birlik")
