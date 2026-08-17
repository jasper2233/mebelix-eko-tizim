"""Ombor harakatlari, sotuv va to'lov

Ilgari qoldiq o'zgarishi faqat audit logga yozilardi. Miqdorni tuzatish uchun u
yetardi, lekin talab kengaydi: `.project` faylida furnitura kelmaydi va uni ombor
buyurtmaga beradi (TANNARX), ba'zan esa to'g'ridan-to'g'ri mijozga sotiladi
(DAROMAD, qarz bilan). JSON izohdan hisobot chiqmaydi.

Uchta jadval:

* `stock_move` — har o'zgarish: ishorali miqdor + NEGA (kirim/buyurtma/sotuv/chiqim)
  + `order_id` yoki `sale_id`. `stock_item.qty` shu qatorlar yig'indisining keshi.
* `sale` — sotuv hujjati: mijoz, jami, to'langan, holat. Satrlari alohida jadval
  emas — `stock_move.sale_id` orqali, chunki sotuv satri va ombor harakati bir xil
  voqea.
* `payment` — sotuvga tushgan to'lovlar (bo'lib to'lash uchun bir nechta).

Revision ID: c9a3e15d84b6
Revises: b4d1e79c53a8
Create Date: 2026-08-17
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "c9a3e15d84b6"
down_revision: str | None = "b4d1e79c53a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Har jadvalda takrorlanadigan BaseModel ustunlari
_BASE: tuple[sa.Column[Any], ...] = (
    sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=True),
    sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("is_deleted", sa.Boolean(), nullable=False),
)


def upgrade() -> None:
    op.create_table(
        "sale",
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("total_uzs", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("paid_uzs", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "status",
            sa.Enum("paid", "partial", "debt", name="salestatus", native_enum=False, length=30),
            nullable=False,
        ),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        *_BASE,
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.ForeignKeyConstraint(["client_id"], ["client.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sale_is_deleted", "sale", ["is_deleted"])
    op.create_index("ix_sale_client_id", "sale", ["client_id"])
    op.create_index("ix_sale_status", "sale", ["status"])

    op.create_table(
        "payment",
        sa.Column("sale_id", sa.Integer(), nullable=False),
        sa.Column("amount_uzs", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "method",
            sa.Enum("cash", "card", "transfer", name="paymentmethod", native_enum=False, length=30),
            nullable=False,
        ),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        *_BASE,
        sa.ForeignKeyConstraint(["sale_id"], ["sale.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_is_deleted", "payment", ["is_deleted"])
    op.create_index("ix_payment_sale_id", "payment", ["sale_id"])

    op.create_table(
        "stock_move",
        sa.Column("stock_item_id", sa.Integer(), nullable=False),
        sa.Column("qty", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("kirim", "buyurtma", "sotuv", "chiqim", name="stockmovekind", native_enum=False, length=30),
            nullable=False,
        ),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("sale_id", sa.Integer(), nullable=True),
        sa.Column("price_uzs", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        *_BASE,
        sa.ForeignKeyConstraint(["stock_item_id"], ["stock_item.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["order.id"]),
        sa.ForeignKeyConstraint(["sale_id"], ["sale.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_move_is_deleted", "stock_move", ["is_deleted"])
    op.create_index("ix_stock_move_stock_item_id", "stock_move", ["stock_item_id"])
    op.create_index("ix_stock_move_kind", "stock_move", ["kind"])
    op.create_index("ix_stock_move_order", "stock_move", ["order_id"])
    op.create_index("ix_stock_move_sale", "stock_move", ["sale_id"])


def downgrade() -> None:
    op.drop_table("stock_move")
    op.drop_table("payment")
    op.drop_table("sale")
