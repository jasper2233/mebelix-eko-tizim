"""Material katalogi olib tashlandi

`material` jadvali FAQAT `/material-catalog` sahifasi tomonidan o'qilardi. Sahifa
egasining talabi bilan olib tashlangach, jadval faqat YOZILADIGAN, hech kim
o'qimaydigan holatga tushdi: `ingest._upsert_materials` har `.project` yuklanishida
unga yangi qator qo'shardi, natijadan esa hech kim foydalanmasdi.

Material sarfi hisoboti `Order.material_usage` (JSONB) ga tayanadi, yorliq va kesish
xaritasi esa `Part.material_name` ga — ikkalasi ham bu jadvalga tegmaydi, shuning
uchun hisobotlar buzilmaydi. Jadvalga birorta FK ham yo'q edi (tekshirilgan).

`MaterialType` enum ham ketdi: uning yagona ishlatilgan joyi shu jadvalga qator
yozish edi.

Revision ID: d2b71f4c86e9
Revises: c9a3e15d84b6
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2b71f4c86e9"
down_revision: str | None = "c9a3e15d84b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("material")


def downgrade() -> None:
    """Jadval tuzilmasi tiklanadi, MAZMUNI esa yo'q — u `.project` fayllaridan
    avtomat to'lardi, ya'ni buyurtmalar qayta yuklanganda o'zi paydo bo'lardi."""
    op.create_table(
        "material",
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=True),
        sa.Column(
            "type",
            sa.Enum("sheet", "band", "hardware", name="materialtype", native_enum=False, length=30),
            nullable=False,
        ),
        sa.Column("thickness", sa.Float(), nullable=True),
        sa.Column("width", sa.Float(), nullable=True),
        sa.Column("length", sa.Float(), nullable=True),
        sa.Column("default_supplier", sa.String(length=100), nullable=True),
        sa.Column("price_per_unit", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("color", sa.String(length=30), nullable=True),
        sa.Column("glossiness", sa.String(length=30), nullable=True),
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
    op.create_index("ix_material_is_deleted", "material", ["is_deleted"])
    op.create_index(
        "ix_material_name_type", "material", ["name", "type"], unique=True, postgresql_where=sa.text("NOT is_deleted")
    )
