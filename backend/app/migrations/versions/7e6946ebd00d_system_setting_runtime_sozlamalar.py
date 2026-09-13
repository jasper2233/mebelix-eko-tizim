"""Ish vaqtida tahrirlanadigan sozlamalar: system_setting (kalit/qiymat).

Birinchi kalit — `custom_part_suffix`: bazisda nomi shu belgi bilan tugagan detal
yuklashda NOSTANDART deb belgilanadi (tsexda belgilanmagan nostandart detallar
ishlab chiqarishga o'tib ketgan edi). `.env` yaramaydi: belgini o'zgartirish uchun
serverga kirib konteynerni qayta ishga tushirish kerak bo'lardi. Kalit/qiymat
shakli — sahifaga keyin stanoklar sozlamalari qo'shiladi.

Revision ID: 7e6946ebd00d
Revises: 9c4e1a7b2d03
Create Date: 2026-09-13
"""

import sqlalchemy as sa
from alembic import op

revision = "7e6946ebd00d"
down_revision = "9c4e1a7b2d03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_setting",
        sa.Column("key", sa.String(length=60), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_system_setting_key"), "system_setting", ["key"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_system_setting_key"), table_name="system_setting")
    op.drop_table("system_setting")
