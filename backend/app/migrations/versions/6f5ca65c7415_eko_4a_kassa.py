"""eko 4a kassa

Revision ID: 6f5ca65c7415
Revises: d135332477e9
Create Date: 2026-10-29 12:58:19.094718

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "6f5ca65c7415"
down_revision: Union[str, None] = "d135332477e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kassa_hisob",
        sa.Column("kod", sa.String(length=20), nullable=False),
        sa.Column("nom", sa.String(length=100), nullable=False),
        sa.Column("tur", sa.String(length=10), nullable=False),
        sa.Column("boshlangich", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("komissiya_foiz", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("faol", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kod"),
    )
    op.create_table(
        "kassa_smena",
        sa.Column("no", sa.String(length=20), nullable=False),
        sa.Column("hisob_id", sa.Integer(), nullable=False),
        sa.Column("ochgan_id", sa.Integer(), nullable=True),
        sa.Column("ochilgan_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ochilish_naqd", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("ochilish_kitob", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("ochilish_kupyura", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("yopgan_id", sa.Integer(), nullable=True),
        sa.Column("yopilgan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("yopilish_naqd", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("yopilish_kupyura", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("kirim", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("chiqim", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("kutilgan", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("farq", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("terminal_z", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("karta_tushum", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["hisob_id"],
            ["kassa_hisob.id"],
        ),
        sa.ForeignKeyConstraint(
            ["ochgan_id"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["yopgan_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("no"),
    )
    op.create_index(
        "ix_kassa_smena_ochiq",
        "kassa_smena",
        ["hisob_id"],
        unique=True,
        postgresql_where=sa.text("yopilgan_at IS NULL"),
    )
    op.create_table(
        "kassa_order",
        sa.Column("no", sa.String(length=20), nullable=False),
        sa.Column("tur", sa.String(length=6), nullable=False),
        sa.Column("maqsad", sa.String(length=12), nullable=False),
        sa.Column("hisob_id", sa.Integer(), nullable=False),
        sa.Column("summa", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("valyuta_summa", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("kurs", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("smena_id", sa.Integer(), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("stock_doc_id", sa.Integer(), nullable=True),
        sa.Column("kontragent", sa.String(length=150), nullable=False),
        sa.Column("turkum", sa.String(length=60), nullable=False),
        sa.Column("izoh", sa.String(length=300), nullable=False),
        sa.Column("guruh", sa.String(length=20), nullable=True),
        sa.Column("mijoz_berdi", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("qaytim", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("kassir_id", sa.Integer(), nullable=True),
        sa.Column("storno_of_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.CheckConstraint("tur IN ('kirim', 'chiqim')", name="ck_kassa_order_tur"),
        sa.CheckConstraint("summa > 0 OR storno_of_id IS NOT NULL", name="ck_kassa_order_summa"),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["client.id"],
        ),
        sa.ForeignKeyConstraint(
            ["hisob_id"],
            ["kassa_hisob.id"],
        ),
        sa.ForeignKeyConstraint(
            ["kassir_id"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["order.id"],
        ),
        sa.ForeignKeyConstraint(
            ["smena_id"],
            ["kassa_smena.id"],
        ),
        sa.ForeignKeyConstraint(
            ["stock_doc_id"],
            ["stock_doc.id"],
        ),
        sa.ForeignKeyConstraint(
            ["storno_of_id"],
            ["kassa_order.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("no"),
    )
    op.create_index(op.f("ix_kassa_order_client_id"), "kassa_order", ["client_id"], unique=False)
    op.create_index(op.f("ix_kassa_order_guruh"), "kassa_order", ["guruh"], unique=False)
    op.create_index("ix_kassa_order_hisob", "kassa_order", ["hisob_id", "id"], unique=False)
    op.create_index(op.f("ix_kassa_order_order_id"), "kassa_order", ["order_id"], unique=False)
    op.create_index(op.f("ix_kassa_order_smena_id"), "kassa_order", ["smena_id"], unique=False)
    op.create_index(
        "ix_kassa_order_storno_of",
        "kassa_order",
        ["storno_of_id"],
        unique=True,
        postgresql_where=sa.text("storno_of_id IS NOT NULL"),
    )
    op.create_table(
        "kassa_taqsimot",
        sa.Column("kassa_order_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("summa", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["kassa_order_id"],
            ["kassa_order.id"],
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["order.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kassa_taqsimot_kassa_order_id"), "kassa_taqsimot", ["kassa_order_id"], unique=False)
    op.create_index(op.f("ix_kassa_taqsimot_order_id"), "kassa_taqsimot", ["order_id"], unique=False)
    # Kassa jurnali faqat qo'shiladi (EKO 2.4 funksiyasi): xato order — storno orderi bilan
    for t in ("kassa_order", "kassa_taqsimot"):
        op.execute(
            f"CREATE TRIGGER {t}_faqat_qoshiladi BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION eko_jurnal_ozgarmaydi()"
        )
    op.execute(
        "INSERT INTO kassa_hisob (kod, nom, tur, boshlangich, komissiya_foiz, faol, is_deleted, created_at) VALUES "
        "('naqd', 'Naqd kassa', 'naqd', 0, 0, true, false, now()), "
        "('karta', 'Karta terminali', 'karta', 0, 0, true, false, now()), "
        "('bank', 'Bank hisobi', 'bank', 0, 0, true, false, now())"
    )


def downgrade() -> None:
    for t in ("kassa_order", "kassa_taqsimot"):
        op.execute(f"DROP TRIGGER IF EXISTS {t}_faqat_qoshiladi ON {t}")
    op.drop_index(op.f("ix_kassa_taqsimot_order_id"), table_name="kassa_taqsimot")
    op.drop_index(op.f("ix_kassa_taqsimot_kassa_order_id"), table_name="kassa_taqsimot")
    op.drop_table("kassa_taqsimot")
    op.drop_index(
        "ix_kassa_order_storno_of", table_name="kassa_order", postgresql_where=sa.text("storno_of_id IS NOT NULL")
    )
    op.drop_index(op.f("ix_kassa_order_smena_id"), table_name="kassa_order")
    op.drop_index(op.f("ix_kassa_order_order_id"), table_name="kassa_order")
    op.drop_index("ix_kassa_order_hisob", table_name="kassa_order")
    op.drop_index(op.f("ix_kassa_order_guruh"), table_name="kassa_order")
    op.drop_index(op.f("ix_kassa_order_client_id"), table_name="kassa_order")
    op.drop_table("kassa_order")
    op.drop_index("ix_kassa_smena_ochiq", table_name="kassa_smena", postgresql_where=sa.text("yopilgan_at IS NULL"))
    op.drop_table("kassa_smena")
    op.drop_table("kassa_hisob")
