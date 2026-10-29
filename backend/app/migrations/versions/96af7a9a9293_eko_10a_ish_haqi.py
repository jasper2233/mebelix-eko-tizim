"""eko 10a ish haqi

Revision ID: 96af7a9a9293
Revises: d051e35cfe69
Create Date: 2026-10-29 17:38:01.456576

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "96af7a9a9293"
down_revision: Union[str, None] = "d051e35cfe69"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ish_haqi_vedomost",
        sa.Column("no", sa.String(length=20), nullable=False),
        sa.Column("dan", sa.Date(), nullable=False),
        sa.Column("gacha", sa.Date(), nullable=False),
        sa.Column("holat", sa.String(length=14), nullable=False),
        sa.Column("jami", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("skanlar", sa.Integer(), nullable=False),
        sa.Column("yaratgan_id", sa.Integer(), nullable=True),
        sa.Column("tasdiqlagan_id", sa.Integer(), nullable=True),
        sa.Column("tasdiqlangan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.CheckConstraint("holat IN ('qoralama', 'tasdiqlangan', 'bekor')", name="ck_ish_haqi_vedomost_holat"),
        sa.CheckConstraint("dan <= gacha", name="ck_ish_haqi_vedomost_davr"),
        sa.ForeignKeyConstraint(
            ["tasdiqlagan_id"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["yaratgan_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("no"),
    )
    op.create_index(
        "ix_ish_haqi_vedomost_davr",
        "ish_haqi_vedomost",
        ["dan", "gacha"],
        unique=False,
        postgresql_where=sa.text("holat <> 'bekor'"),
    )
    op.create_table(
        "ish_stavka",
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("process_code", sa.Integer(), nullable=True),
        sa.Column("narx", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("amal_boshi", sa.Date(), nullable=False),
        sa.Column("yozgan_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.CheckConstraint("narx >= 0", name="ck_ish_stavka_narx"),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["post.id"],
        ),
        sa.ForeignKeyConstraint(
            ["yozgan_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ish_stavka_kalit",
        "ish_stavka",
        ["post_id", "process_code", "amal_boshi"],
        unique=True,
        postgresql_nulls_not_distinct=True,
    )
    op.create_table(
        "ish_haqi_qator",
        sa.Column("vedomost_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("hajm", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("skanlar", sa.Integer(), nullable=False),
        sa.Column("summa", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employee.id"],
        ),
        sa.ForeignKeyConstraint(
            ["post_id"],
            ["post.id"],
        ),
        sa.ForeignKeyConstraint(["vedomost_id"], ["ish_haqi_vedomost.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ish_haqi_qator_vedomost_id"), "ish_haqi_qator", ["vedomost_id"], unique=False)
    op.add_column("kassa_modda", sa.Column("pnl_emas", sa.Boolean(), server_default="false", nullable=False))
    # Ishbay ish haqi to'lovi uchun modda: P&L xarajati emas (xarajat tannarxda), buxgalteriyada 6710 ni yopadi
    op.execute(
        "INSERT INTO kassa_modda (nom, tartib, faol, pnl_emas, is_deleted, created_at) "
        "SELECT 'Ish haqi (ishbay)', COALESCE(MAX(tartib), 0) + 1, true, true, false, now() FROM kassa_modda"
    )
    op.execute(
        "INSERT INTO bux_qoida (kalit, schyot, is_deleted, created_at) "
        "VALUES ('xarajat:Ish haqi (ishbay)', '6710', false, now())"
    )


def downgrade() -> None:
    op.execute("DELETE FROM bux_qoida WHERE kalit = 'xarajat:Ish haqi (ishbay)'")
    op.execute("DELETE FROM kassa_modda WHERE nom = 'Ish haqi (ishbay)'")
    op.drop_column("kassa_modda", "pnl_emas")
    op.drop_index(op.f("ix_ish_haqi_qator_vedomost_id"), table_name="ish_haqi_qator")
    op.drop_table("ish_haqi_qator")
    op.drop_index("ix_ish_stavka_kalit", table_name="ish_stavka", postgresql_nulls_not_distinct=True)
    op.drop_table("ish_stavka")
    op.drop_index(
        "ix_ish_haqi_vedomost_davr", table_name="ish_haqi_vedomost", postgresql_where=sa.text("holat <> 'bekor'")
    )
    op.drop_table("ish_haqi_vedomost")
