"""Materiallar ombori pozitsiyalari

`stock_item` — omborchi yuritadigan katalog: kod, qoldiq, minimal zaxira, narx.
Mavjud `material` jadvalidan AYRIM: u GibLab `.project` faylidan avtomat to'ladi
va har yuklashda qayta yoziladi, ya'ni qoldiq va narx u yerda tura olmaydi.
Furnitura esa `.project` da umuman uchramaydi.

Kod `K-GG-MMM-VV` (`F-RC-001-01`). `catalog` VARCHAR-enum: F (furnitura) va
M (material). Yuklangan katalogdagi X (xizmatlar) omborga kirmaydi — xizmatning
qoldig'i bo'lmaydi.

Revision ID: b4d1e79c53a8
Revises: c7e2b4f81d39
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b4d1e79c53a8"
down_revision: str | None = "c7e2b4f81d39"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stock_item",
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column(
            "catalog",
            sa.Enum("F", "M", name="stockcatalog", native_enum=False, length=8),
            nullable=False,
        ),
        sa.Column("group_code", sa.String(length=4), nullable=False),
        sa.Column("group_name", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("variant", sa.String(length=40), nullable=True),
        sa.Column("size", sa.String(length=40), nullable=True),
        sa.Column("unit", sa.String(length=16), nullable=True),
        sa.Column("qty", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("min_qty", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("purchase_usd", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("purchase_uzs", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("sale_uzs", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=True
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_item_is_deleted", "stock_item", ["is_deleted"])
    # Qisman unique: soft-delete qilingan pozitsiya kodni band qilib turmasin
    op.create_index(
        "ix_stock_item_code", "stock_item", ["code"], unique=True, postgresql_where=sa.text("NOT is_deleted")
    )
    op.create_index("ix_stock_item_catalog", "stock_item", ["catalog"])
    op.create_index("ix_stock_item_group_code", "stock_item", ["group_code"])


def downgrade() -> None:
    op.drop_index("ix_stock_item_is_deleted", table_name="stock_item")
    op.drop_index("ix_stock_item_group_code", table_name="stock_item")
    op.drop_index("ix_stock_item_catalog", table_name="stock_item")
    op.drop_index("ix_stock_item_code", table_name="stock_item")
    op.drop_table("stock_item")
