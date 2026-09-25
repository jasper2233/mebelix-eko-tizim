"""Mahsulotlar ombori katalogi — `catalog_item`

Tsexning katalogi (2026-09-25 holatiga 2662 pozitsiya) shu paytgacha Google
Sheets'da yuritilardi. Kod tuzilishi u yerda ham shu: `M-LD-054-03` —
katalog / guruh / model / variant, va u HECH QACHON o'zgarmaydi.

Nega YANGI jadval, `stock_item` emas: `stock_item` (va `stock_move`, `sale`,
`payment`) — olib tashlangan materiallar ombori modulidan qolgan yetim
jadvallar, prodda bo'sh turibdi va `LEGACY_TABLES` da e'tiborsiz qoldiriladi
(`docs/04` §4.4). Ularning ustunlari boshqa modelga tegishli edi; nomini qayta
ishlatish eski migratsiya tarixini ham, yetimlar ro'yxatini ham chalkashtirardi.

Ma'lumot bu migratsiyada YOZILMAYDI: katalog o'zgarib turadi, migratsiya esa
prodga qo'llangach tahrirlanmaydi. Yuklash — `scripts/catalog_import.py`
(kod bo'yicha upsert, qayta yurgizish xavfsiz).

Revision ID: 6d9d9f645802
Revises: c7a2f4e19b03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "6d9d9f645802"
down_revision: str | None = "c7a2f4e19b03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_item",
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("catalog", sa.String(length=1), nullable=False),
        sa.Column("group_code", sa.String(length=2), nullable=False),
        sa.Column("group_name", sa.String(length=60), nullable=False),
        sa.Column("model_no", sa.Integer(), nullable=False),
        sa.Column("variant_no", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("unit", sa.String(length=10), nullable=True),
        sa.Column("size_text", sa.String(length=40), nullable=True),
        sa.Column("thickness_mm", sa.Numeric(precision=6, scale=1), nullable=True),
        sa.Column("article", sa.String(length=40), nullable=True),
        sa.Column("decor_no", sa.Integer(), nullable=True),
        sa.Column("decor_name", sa.String(length=80), nullable=True),
        sa.Column("matrix", sa.String(length=20), nullable=True),
        sa.Column("image_url", sa.String(length=300), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("min_quantity", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("location", sa.String(length=40), nullable=True),
        sa.Column("purchase_price", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("sale_price", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    # «Bir kod = bir mahsulot» qoidasi shu indeks bilan ushlab turiladi
    op.create_index(op.f("ix_catalog_item_code"), "catalog_item", ["code"], unique=True)
    # Kategoriya daraxti va guruh ichidagi tartib
    op.create_index(
        "ix_catalog_item_group", "catalog_item", ["catalog", "group_code", "model_no", "variant_no"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_catalog_item_group", table_name="catalog_item")
    op.drop_index(op.f("ix_catalog_item_code"), table_name="catalog_item")
    op.drop_table("catalog_item")
