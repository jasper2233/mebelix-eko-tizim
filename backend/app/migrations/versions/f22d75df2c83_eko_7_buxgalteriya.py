"""eko 7 buxgalteriya

Revision ID: f22d75df2c83
Revises: ee9b646a438a
Create Date: 2026-10-29 14:56:35.519665

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f22d75df2c83"
down_revision: Union[str, None] = "ee9b646a438a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bux_qoida",
        sa.Column("kalit", sa.String(length=80), nullable=False),
        sa.Column("schyot", sa.String(length=8), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kalit"),
    )
    op.create_table(
        "bux_schyot",
        sa.Column("kod", sa.String(length=8), nullable=False),
        sa.Column("nom", sa.String(length=150), nullable=False),
        sa.Column("tur", sa.String(length=2), nullable=False),
        sa.Column("faol", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.CheckConstraint("tur IN ('A', 'P', 'AP')", name="ck_bux_schyot_tur"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kod"),
    )
    op.create_table(
        "bux_yozuv",
        sa.Column("sana", sa.Date(), nullable=False),
        sa.Column("debet", sa.String(length=8), nullable=False),
        sa.Column("kredit", sa.String(length=8), nullable=False),
        sa.Column("summa", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("izoh", sa.String(length=300), nullable=False),
        sa.Column("guruh", sa.String(length=60), nullable=True),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("kontragent", sa.String(length=150), nullable=False),
        sa.Column("yozgan_id", sa.Integer(), nullable=True),
        sa.Column("storno_of_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.CheckConstraint("debet <> kredit", name="ck_bux_yozuv_tomon"),
        sa.CheckConstraint("summa > 0", name="ck_bux_yozuv_summa"),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["client.id"],
        ),
        sa.ForeignKeyConstraint(
            ["storno_of_id"],
            ["bux_yozuv.id"],
        ),
        sa.ForeignKeyConstraint(
            ["yozgan_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storno_of_id"),
    )
    op.create_index(op.f("ix_bux_yozuv_client_id"), "bux_yozuv", ["client_id"], unique=False)
    op.create_index("ix_bux_yozuv_debet", "bux_yozuv", ["debet", "sana"], unique=False)
    op.create_index(op.f("ix_bux_yozuv_guruh"), "bux_yozuv", ["guruh"], unique=False)
    op.create_index("ix_bux_yozuv_kredit", "bux_yozuv", ["kredit", "sana"], unique=False)
    op.create_index("ix_bux_yozuv_sana", "bux_yozuv", ["sana"], unique=False)
    # Provodkalar jurnali faqat qo'shiladi (EKO 2.4 funksiyasi)
    op.execute(
        "CREATE TRIGGER bux_yozuv_faqat_qoshiladi BEFORE UPDATE OR DELETE ON bux_yozuv "
        "FOR EACH ROW EXECUTE FUNCTION eko_jurnal_ozgarmaydi()"
    )
    # Schyotlar rejasi — BHMS 21 asosida, asosiy schyotlar (buxgalter to'ldiradi va nomlarini tasdiqlaydi)
    schyotlar = [
        ("0100", "Asosiy vositalar", "A"),
        ("0200", "Asosiy vositalar eskirishi", "P"),
        ("1010", "Xom ashyo va materiallar", "A"),
        ("2010", "Asosiy ishlab chiqarish", "A"),
        ("2510", "Umumishlab chiqarish xarajatlari", "A"),
        ("2810", "Tayyor mahsulot", "A"),
        ("4010", "Xaridor va buyurtmachilardan olinadigan schyotlar", "AP"),
        ("4310", "Mol yetkazib beruvchilarga berilgan bo'naklar", "A"),
        ("4410", "Byudjetga soliqlar bo'yicha bo'naklar", "A"),
        ("5010", "Milliy valyutadagi kassa", "A"),
        ("5110", "Hisob-kitob schyoti", "A"),
        ("5710", "Yo'ldagi pul o'tkazmalari (karta terminali)", "A"),
        ("6010", "Mol yetkazib beruvchilar va pudratchilarga to'lanadigan schyotlar", "AP"),
        ("6310", "Xaridor va buyurtmachilardan olingan bo'naklar", "P"),
        ("6410", "Byudjetga to'lovlar bo'yicha qarz", "AP"),
        ("6520", "Davlat maqsadli jamg'armalariga to'lovlar", "P"),
        ("6710", "Mehnatga haq to'lash bo'yicha xodimlar bilan hisoblashuvlar", "P"),
        ("8330", "Ustav kapitali", "P"),
        ("8710", "Taqsimlanmagan foyda (qoplanmagan zarar)", "AP"),
        ("9010", "Tayyor mahsulotni sotishdan daromadlar", "P"),
        ("9020", "Tovarlarni sotishdan daromadlar", "P"),
        ("9110", "Sotilgan tayyor mahsulot tannarxi", "A"),
        ("9120", "Sotilgan tovarlar tannarxi", "A"),
        ("9390", "Boshqa operatsion daromadlar", "P"),
        ("9410", "Sotish xarajatlari", "A"),
        ("9420", "Ma'muriy xarajatlar", "A"),
        ("9430", "Boshqa operatsion xarajatlar", "A"),
        ("9690", "Moliyaviy faoliyat bo'yicha boshqa xarajatlar", "A"),
        ("9810", "Soliq xarajatlari (foyda / aylanma soliq)", "A"),
        ("9910", "Yakuniy moliyaviy natija", "AP"),
    ]
    for kod, nom, tur in schyotlar:
        op.execute(
            sa.text(
                "INSERT INTO bux_schyot (kod, nom, tur, faol, is_deleted, created_at) "
                "VALUES (:k, :n, :t, true, false, now())"
            ).bindparams(k=kod, n=nom, t=tur)
        )
    qoidalar = [
        ("hisob:naqd", "5010"),
        ("hisob:karta", "5710"),
        ("hisob:bank", "5110"),
        ("inkassatsiya", "5710"),
        ("komissiya", "9690"),
        ("farq:kamomad", "9430"),
        ("farq:ortiqcha", "9390"),
        ("kirim:boshqa", "9390"),
        ("chiqim:boshqa", "9430"),
        ("xarajat:*", "9420"),
        ("xarajat:Transport va yetkazish", "9410"),
        ("xarajat:Bank komissiyasi", "9690"),
    ]
    for kalit, sch in qoidalar:
        op.execute(
            sa.text(
                "INSERT INTO bux_qoida (kalit, schyot, is_deleted, created_at) VALUES (:k, :s, false, now())"
            ).bindparams(k=kalit, s=sch)
        )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS bux_yozuv_faqat_qoshiladi ON bux_yozuv")
    op.drop_index("ix_bux_yozuv_sana", table_name="bux_yozuv")
    op.drop_index("ix_bux_yozuv_kredit", table_name="bux_yozuv")
    op.drop_index(op.f("ix_bux_yozuv_guruh"), table_name="bux_yozuv")
    op.drop_index("ix_bux_yozuv_debet", table_name="bux_yozuv")
    op.drop_index(op.f("ix_bux_yozuv_client_id"), table_name="bux_yozuv")
    op.drop_table("bux_yozuv")
    op.drop_table("bux_schyot")
    op.drop_table("bux_qoida")
