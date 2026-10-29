"""eko 6a soliq

Revision ID: ee9b646a438a
Revises: daf7e6650edf
Create Date: 2026-10-29 14:30:03.518965

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ee9b646a438a"
down_revision: Union[str, None] = "daf7e6650edf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "soliq_korxona",
        sa.Column("nomi", sa.String(length=200), nullable=False),
        sa.Column("stir", sa.String(length=9), nullable=False),
        sa.Column("manzil", sa.String(length=300), nullable=False),
        sa.Column("bank", sa.String(length=150), nullable=False),
        sa.Column("mfo", sa.String(length=5), nullable=False),
        sa.Column("hisob_raqam", sa.String(length=20), nullable=False),
        sa.Column("direktor", sa.String(length=120), nullable=False),
        sa.Column("buxgalter", sa.String(length=120), nullable=False),
        sa.Column("qqs_kod", sa.String(length=20), nullable=False),
        sa.Column("esf_operator", sa.String(length=20), nullable=False),
        sa.Column("buyurtma_nomi", sa.String(length=200), nullable=False),
        sa.Column("buyurtma_mxik", sa.String(length=17), nullable=False),
        sa.Column("buyurtma_birlik", sa.String(length=10), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "soliq_sinov_operator",
        sa.Column("operator_id", sa.String(length=64), nullable=False),
        sa.Column("yonalish", sa.String(length=10), nullable=False),
        sa.Column("holat", sa.String(length=14), nullable=False),
        sa.Column("xabar", sa.String(length=300), nullable=False),
        sa.Column("hujjat", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("operator_id"),
    )
    op.create_table(
        "soliq_mijoz",
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("yuridik", sa.Boolean(), nullable=False),
        sa.Column("nomi", sa.String(length=200), nullable=False),
        sa.Column("stir", sa.String(length=9), nullable=False),
        sa.Column("jshshir", sa.String(length=14), nullable=False),
        sa.Column("bank", sa.String(length=150), nullable=False),
        sa.Column("mfo", sa.String(length=5), nullable=False),
        sa.Column("hisob_raqam", sa.String(length=20), nullable=False),
        sa.Column("qqs_kod", sa.String(length=20), nullable=False),
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
        "soliq_rejim",
        sa.Column("amal_boshi", sa.Date(), nullable=False),
        sa.Column("rejim", sa.String(length=8), nullable=False),
        sa.Column("qqs_foiz", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("aylanma_foiz", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("yozgan_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.CheckConstraint("rejim IN ('qqs', 'aylanma')", name="ck_soliq_rejim_rejim"),
        sa.CheckConstraint("aylanma_foiz >= 0 AND aylanma_foiz <= 50", name="ck_soliq_rejim_aylanma"),
        sa.CheckConstraint("qqs_foiz >= 0 AND qqs_foiz <= 50", name="ck_soliq_rejim_qqs"),
        sa.ForeignKeyConstraint(
            ["yozgan_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("amal_boshi"),
    )
    op.create_table(
        "soliq_esf",
        sa.Column("no", sa.String(length=20), nullable=False),
        sa.Column("tur", sa.String(length=10), nullable=False),
        sa.Column("holat", sa.String(length=14), nullable=False),
        sa.Column("sana", sa.Date(), nullable=False),
        sa.Column("raqam", sa.String(length=40), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("stock_doc_id", sa.Integer(), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("kontragent", sa.String(length=200), nullable=False),
        sa.Column("kontragent_stir", sa.String(length=14), nullable=False),
        sa.Column("rekvizit", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("qatorlar", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rejim", sa.String(length=8), nullable=False),
        sa.Column("summa", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("qqs", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("jami", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("operator", sa.String(length=20), nullable=False),
        sa.Column("operator_id", sa.String(length=64), nullable=True),
        sa.Column("xato", sa.Text(), nullable=False),
        sa.Column("urinish", sa.Integer(), nullable=False),
        sa.Column("keyingi_urinish", sa.DateTime(timezone=True), nullable=True),
        sa.Column("yuborilgan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("javob_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("yaratgan_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.CheckConstraint("tur IN ('chiquvchi', 'kiruvchi')", name="ck_soliq_esf_tur"),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["client.id"],
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["order.id"],
        ),
        sa.ForeignKeyConstraint(
            ["stock_doc_id"],
            ["stock_doc.id"],
        ),
        sa.ForeignKeyConstraint(
            ["yaratgan_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("no"),
        sa.UniqueConstraint("operator_id"),
    )
    op.create_index(
        "ix_soliq_esf_doc_tirik",
        "soliq_esf",
        ["stock_doc_id", "tur"],
        unique=True,
        postgresql_where=sa.text("stock_doc_id IS NOT NULL AND holat NOT IN ('bekor', 'rad_etildi')"),
    )
    op.create_index("ix_soliq_esf_holat", "soliq_esf", ["holat", "keyingi_urinish"], unique=False)
    op.create_index(
        "ix_soliq_esf_order_tirik",
        "soliq_esf",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text("order_id IS NOT NULL AND holat NOT IN ('bekor', 'rad_etildi')"),
    )
    op.create_index(op.f("ix_soliq_esf_sana"), "soliq_esf", ["sana"], unique=False)
    op.add_column("catalog_item", sa.Column("mxik", sa.String(length=17), nullable=True))
    op.add_column("catalog_item", sa.Column("birlik_kod", sa.String(length=10), nullable=True))
    op.add_column("catalog_item", sa.Column("qqs_turi", sa.String(length=8), server_default="standart", nullable=False))


def downgrade() -> None:
    op.drop_column("catalog_item", "qqs_turi")
    op.drop_column("catalog_item", "birlik_kod")
    op.drop_column("catalog_item", "mxik")
    op.drop_index(op.f("ix_soliq_esf_sana"), table_name="soliq_esf")
    op.drop_index(
        "ix_soliq_esf_order_tirik",
        table_name="soliq_esf",
        postgresql_where=sa.text("order_id IS NOT NULL AND holat NOT IN ('bekor', 'rad_etildi')"),
    )
    op.drop_index("ix_soliq_esf_holat", table_name="soliq_esf")
    op.drop_index(
        "ix_soliq_esf_doc_tirik",
        table_name="soliq_esf",
        postgresql_where=sa.text("stock_doc_id IS NOT NULL AND holat NOT IN ('bekor', 'rad_etildi')"),
    )
    op.drop_table("soliq_esf")
    op.drop_table("soliq_rejim")
    op.drop_table("soliq_mijoz")
    op.drop_table("soliq_sinov_operator")
    op.drop_table("soliq_korxona")
