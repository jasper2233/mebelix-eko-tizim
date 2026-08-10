"""Qadoq (pachka) va uning tarkibi.

Qadoqni ALGORITM emas, qadoqlovchi yig'adi: "Qadoq yaratish" -> detallarni
birma-bir skanerlash -> "Yakunlash". Shuning uchun tarkib alohida jadvalda va
oldindan hisoblanmaydi.

`pachka.code` — chekdagi QR matni (`PK-B-2026-014-03`). Detal QR'ida ostki chiziq
bo'ladi (`{mahsulot}_{detal}`), qadoqnikida yo'q — terminal skanni shundan ajratadi.

`pachka_item.instance_id` YAGONA: bitta detal nusxasi bitta qadoqda bo'ladi, aks
holda ombordan ikki marta chiqarilardi. Ochiq qadoqdan chiqarish — yumshoq o'chirish.

Revision ID: 7e2e0ae9f7f3
Revises: f1b6d0c73a25
Create Date: 2026-08-10
"""

import sqlalchemy as sa
from alembic import op

revision = "7e2e0ae9f7f3"
down_revision = "f1b6d0c73a25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pachka",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "closed", "shipped", name="pachkastatus", native_enum=False, length=30),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=True
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["order.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pachka_code", "pachka", ["code"], unique=True, postgresql_where=sa.text("NOT is_deleted"))
    op.create_index(op.f("ix_pachka_is_deleted"), "pachka", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_pachka_order_id"), "pachka", ["order_id"], unique=False)
    op.create_index("ix_pachka_order_status", "pachka", ["order_id", "status"], unique=False)
    op.create_index(op.f("ix_pachka_status"), "pachka", ["status"], unique=False)
    op.create_table(
        "pachka_item",
        sa.Column("pachka_id", sa.Integer(), nullable=False),
        sa.Column("instance_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=True
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instance_id"],
            ["part_instance.id"],
        ),
        sa.ForeignKeyConstraint(
            ["pachka_id"],
            ["pachka.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_pachka_item_instance",
        "pachka_item",
        ["instance_id"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted"),
    )
    op.create_index(op.f("ix_pachka_item_is_deleted"), "pachka_item", ["is_deleted"], unique=False)
    op.create_index("ix_pachka_item_pachka", "pachka_item", ["pachka_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_pachka_item_pachka", table_name="pachka_item")
    op.drop_index(op.f("ix_pachka_item_is_deleted"), table_name="pachka_item")
    op.drop_index("ix_pachka_item_instance", table_name="pachka_item", postgresql_where=sa.text("NOT is_deleted"))
    op.drop_table("pachka_item")
    op.drop_index(op.f("ix_pachka_status"), table_name="pachka")
    op.drop_index("ix_pachka_order_status", table_name="pachka")
    op.drop_index(op.f("ix_pachka_order_id"), table_name="pachka")
    op.drop_index(op.f("ix_pachka_is_deleted"), table_name="pachka")
    op.drop_index("ix_pachka_code", table_name="pachka", postgresql_where=sa.text("NOT is_deleted"))
    op.drop_table("pachka")
