"""eko 5a moliya

Revision ID: daf7e6650edf
Revises: 6f5ca65c7415
Create Date: 2026-10-29 13:52:27.467936

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "daf7e6650edf"
down_revision: Union[str, None] = "6f5ca65c7415"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kassa_modda",
        sa.Column("nom", sa.String(length=60), nullable=False),
        sa.Column("oylik_limit", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("tartib", sa.Integer(), nullable=False),
        sa.Column("faol", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nom"),
    )
    op.create_table(
        "moliya_mijoz_shart",
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("shartnoma_no", sa.String(length=40), nullable=False),
        sa.Column("muddat_kun", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["client.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id"),
    )
    op.create_table(
        "moliya_davr",
        sa.Column("oy", sa.Date(), nullable=False),
        sa.Column("holat", sa.String(length=8), nullable=False),
        sa.Column("yopgan_id", sa.Integer(), nullable=True),
        sa.Column("yopilgan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("natija", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ochish_sorov_id", sa.Integer(), nullable=True),
        sa.Column("ochish_sabab", sa.String(length=200), nullable=False),
        sa.Column("ochgan_id", sa.Integer(), nullable=True),
        sa.Column("ochilgan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.CheckConstraint("holat IN ('yopiq', 'ochildi')", name="ck_moliya_davr_holat"),
        sa.ForeignKeyConstraint(
            ["ochgan_id"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["ochish_sorov_id"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["yopgan_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("oy"),
    )
    op.create_table(
        "moliya_reja",
        sa.Column("nom", sa.String(length=120), nullable=False),
        sa.Column("tur", sa.String(length=6), nullable=False),
        sa.Column("summa", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("turkum", sa.String(length=60), nullable=False),
        sa.Column("takror", sa.String(length=6), nullable=False),
        sa.Column("sana", sa.Date(), nullable=False),
        sa.Column("faol", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("yaratgan_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.CheckConstraint("takror IN ('oylik', 'bir')", name="ck_moliya_reja_takror"),
        sa.CheckConstraint("tur IN ('kirim', 'chiqim')", name="ck_moliya_reja_tur"),
        sa.CheckConstraint("summa > 0", name="ck_moliya_reja_summa"),
        sa.ForeignKeyConstraint(
            ["yaratgan_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Boshlang'ich xarajat moddalari (4a dagi ro'yxat) — Moliya sozlamasida tahrirlanadi
    moddalar = [
        "Ijara",
        "Kommunal",
        "Ish haqi",
        "Transport va yetkazish",
        "Xo'jalik mollari",
        "Ta'mirlash",
        "Soliq va to'lovlar",
        "Bank komissiyasi",
        "Boshqa",
    ]
    for i, n in enumerate(moddalar, 1):
        op.execute(
            sa.text(
                "INSERT INTO kassa_modda (nom, tartib, faol, is_deleted, created_at) "
                "VALUES (:n, :i, true, false, now())"
            ).bindparams(n=n, i=i)
        )


def downgrade() -> None:
    op.drop_table("moliya_reja")
    op.drop_table("moliya_davr")
    op.drop_table("moliya_mijoz_shart")
    op.drop_table("kassa_modda")
