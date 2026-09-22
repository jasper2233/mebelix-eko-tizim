"""Bazis modeli fayli va yig'uvchi uchun ochiq havola

Ikki narsa qo'shiladi:

1. `FileKind.BAZIS` — texnolog `.project` YONIGA yuklaydigan Bazis `.b3d`
   fayli. DDL kerak emas: `db_enum` `native_enum=False` bilan VARCHAR yaratadi
   (`enums.py:8` — «painless ALTERs on new members»), check-cheklov yo'q.
   `.project` dan farqli, bitta buyurtmada MAHSULOT SONICHA bo'ladi (prodda
   o'lchandi: `2083 Anvar` da uchta — `208301`, `208302`, `208303`).
   Mahsulotga `OrderFile.meta["product_code"]` orqali bog'lanadi: `.b3d`
   sarlavhasidagi `Code` maydoni `Product.code` ning AYNAN o'zi.

2. `order.share_token` — `/3d/{token}` ochiq sahifasi uchun. Buyurtma raqami
   EMAS: raqam bo'lsa havolani olgan odam uni o'zgartirib butun sexning
   buyurtmalarini ochib chiqardi. `uuid4`, unikal indeks; qayta generatsiya
   eski havolani o'ldiradi (`Employee.badge_id` bilan bir xil naqsh).

Revision ID: c7a2f4e19b03
Revises: d4b8e1f37c92
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7a2f4e19b03"
down_revision: str | None = "d4b8e1f37c92"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("order", sa.Column("share_token", sa.String(length=36), nullable=True))
    op.create_index(
        "ix_order_share_token",
        "order",
        ["share_token"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted"),
    )


def downgrade() -> None:
    op.drop_index("ix_order_share_token", table_name="order")
    op.drop_column("order", "share_token")
