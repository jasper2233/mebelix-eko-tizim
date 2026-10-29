"""eko 3a kroy qoldiq ombori va inbox

Revision ID: 244608b72e61
Revises: e24a0c1b7f31
Create Date: 2026-10-29 10:54:35.430445

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "244608b72e61"
down_revision: Union[str, None] = "e24a0c1b7f31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integ_inbox",
        sa.Column("manba", sa.String(length=20), nullable=False),
        sa.Column("kalit", sa.String(length=200), nullable=False),
        sa.Column("tur", sa.String(length=40), nullable=False),
        sa.Column("xesh", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("natija", sa.String(length=200), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integ_inbox_kalit", "integ_inbox", ["manba", "kalit"], unique=True)
    op.create_table(
        "kroy_intake",
        sa.Column("no", sa.String(length=20), nullable=False),
        sa.Column("mx_loyiha", sa.String(length=40), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("holat", sa.String(length=8), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("consumed", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["order.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("no"),
    )
    op.create_index(op.f("ix_kroy_intake_mx_loyiha"), "kroy_intake", ["mx_loyiha"], unique=False)
    op.add_column("ombor_bolak", sa.Column("material_kod", sa.String(length=60), server_default="", nullable=False))
    op.add_column("ombor_bolak", sa.Column("tur", sa.String(length=20), server_default="", nullable=False))
    op.add_column("ombor_bolak", sa.Column("qalinlik", sa.Numeric(precision=6, scale=1), nullable=True))
    op.add_column("ombor_bolak", sa.Column("qty", sa.Integer(), server_default="1", nullable=False))
    op.add_column("ombor_bolak", sa.Column("qty_pending", sa.Integer(), server_default="0", nullable=False))
    op.add_column("ombor_bolak", sa.Column("jami", sa.Integer(), server_default="1", nullable=False))
    op.add_column("ombor_bolak", sa.Column("manba", sa.String(length=4), server_default="mes", nullable=False))
    op.add_column("ombor_bolak", sa.Column("kirim_id", sa.String(length=20), nullable=True))
    op.add_column("ombor_bolak", sa.Column("karta", sa.Integer(), nullable=True))
    op.add_column("ombor_bolak", sa.Column("nusxa", sa.Integer(), server_default="1", nullable=False))
    op.add_column("ombor_bolak", sa.Column("mx_loyiha", sa.String(length=40), nullable=True))
    op.add_column("ombor_bolak", sa.Column("mx_op", sa.String(length=40), nullable=True))
    op.add_column("ombor_bolak", sa.Column("mx_raqam", sa.String(length=40), nullable=True))
    op.add_column("ombor_bolak", sa.Column("band_loyiha", sa.String(length=40), nullable=True))
    op.add_column("ombor_bolak", sa.Column("band_raqam", sa.String(length=40), nullable=True))
    op.add_column("ombor_bolak", sa.Column("chiziqli", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("ombor_bolak", sa.Column("toza_chet", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("ombor_bolak", sa.Column("list_m2", sa.Numeric(precision=8, scale=4), nullable=True))
    op.add_column("ombor_bolak", sa.Column("foiz", sa.Numeric(precision=5, scale=1), nullable=True))
    op.add_column("ombor_bolak", sa.Column("m2_narx", sa.Numeric(precision=14, scale=4), nullable=True))
    op.add_column("ombor_bolak", sa.Column("izoh", sa.String(length=200), server_default="", nullable=False))
    op.alter_column("ombor_bolak", "waste_id", existing_type=sa.INTEGER(), nullable=True)
    op.alter_column("ombor_bolak", "manba_order_id", existing_type=sa.INTEGER(), nullable=True)
    op.create_index(op.f("ix_ombor_bolak_band_loyiha"), "ombor_bolak", ["band_loyiha"], unique=False)
    op.create_index("ix_ombor_bolak_kirim", "ombor_bolak", ["kirim_id"], unique=False)
    # Eski (2.3b) yopilgan bo'laklarda dona 0 bo'lsin — `qty` endi «omborda nechta»
    op.execute("UPDATE ombor_bolak SET qty = 0 WHERE joy <> 'ombor'")
    op.create_check_constraint("ck_ombor_bolak_qty", "ombor_bolak", "qty >= 0 AND qty_pending >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_ombor_bolak_qty", "ombor_bolak", type_="check")
    op.drop_index("ix_ombor_bolak_kirim", table_name="ombor_bolak")
    op.drop_index(op.f("ix_ombor_bolak_band_loyiha"), table_name="ombor_bolak")
    op.alter_column("ombor_bolak", "manba_order_id", existing_type=sa.INTEGER(), nullable=False)
    op.alter_column("ombor_bolak", "waste_id", existing_type=sa.INTEGER(), nullable=False)
    op.drop_column("ombor_bolak", "izoh")
    op.drop_column("ombor_bolak", "m2_narx")
    op.drop_column("ombor_bolak", "foiz")
    op.drop_column("ombor_bolak", "list_m2")
    op.drop_column("ombor_bolak", "toza_chet")
    op.drop_column("ombor_bolak", "chiziqli")
    op.drop_column("ombor_bolak", "band_raqam")
    op.drop_column("ombor_bolak", "band_loyiha")
    op.drop_column("ombor_bolak", "mx_raqam")
    op.drop_column("ombor_bolak", "mx_op")
    op.drop_column("ombor_bolak", "mx_loyiha")
    op.drop_column("ombor_bolak", "nusxa")
    op.drop_column("ombor_bolak", "karta")
    op.drop_column("ombor_bolak", "kirim_id")
    op.drop_column("ombor_bolak", "manba")
    op.drop_column("ombor_bolak", "jami")
    op.drop_column("ombor_bolak", "qty_pending")
    op.drop_column("ombor_bolak", "qty")
    op.drop_column("ombor_bolak", "qalinlik")
    op.drop_column("ombor_bolak", "tur")
    op.drop_column("ombor_bolak", "material_kod")
    op.drop_index(op.f("ix_kroy_intake_mx_loyiha"), table_name="kroy_intake")
    op.drop_table("kroy_intake")
    op.drop_index("ix_integ_inbox_kalit", table_name="integ_inbox")
    op.drop_table("integ_inbox")
