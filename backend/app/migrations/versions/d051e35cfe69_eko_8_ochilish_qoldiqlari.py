"""eko 8 ochilish qoldiqlari

Revision ID: d051e35cfe69
Revises: f22d75df2c83
Create Date: 2026-10-29 15:41:03.438876

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d051e35cfe69"
down_revision: Union[str, None] = "f22d75df2c83"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kassa_ochilish",
        sa.Column("tur", sa.String(length=10), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("kontragent", sa.String(length=150), nullable=False),
        sa.Column("summa", sa.Numeric(precision=16, scale=2), nullable=False),
        sa.Column("sana", sa.Date(), nullable=False),
        sa.Column("izoh", sa.String(length=300), nullable=False),
        sa.Column("yaratgan_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.CheckConstraint("tur = 'taminotchi' OR client_id IS NOT NULL", name="ck_kassa_ochilish_mijoz"),
        sa.CheckConstraint("tur IN ('mijoz', 'taminotchi')", name="ck_kassa_ochilish_tur"),
        sa.CheckConstraint("summa <> 0", name="ck_kassa_ochilish_summa"),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["client.id"],
        ),
        sa.ForeignKeyConstraint(
            ["yaratgan_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kassa_ochilish_client_id"), "kassa_ochilish", ["client_id"], unique=False)
    op.add_column("kassa_taqsimot", sa.Column("ochilish_client_id", sa.Integer(), nullable=True))
    op.alter_column("kassa_taqsimot", "order_id", existing_type=sa.INTEGER(), nullable=True)
    op.create_index(
        op.f("ix_kassa_taqsimot_ochilish_client_id"), "kassa_taqsimot", ["ochilish_client_id"], unique=False
    )
    op.create_foreign_key(
        "fk_kassa_taqsimot_ochilish_client", "kassa_taqsimot", "client", ["ochilish_client_id"], ["id"]
    )
    op.create_check_constraint(
        "ck_kassa_taqsimot_manzil", "kassa_taqsimot", "(order_id IS NULL) <> (ochilish_client_id IS NULL)"
    )
    # Ochilish qoldiqlari — jurnal (EKO 2.4 funksiyasi): tuzatish teskari ishorali qator
    op.execute(
        "CREATE TRIGGER kassa_ochilish_faqat_qoshiladi BEFORE UPDATE OR DELETE ON kassa_ochilish "
        "FOR EACH ROW EXECUTE FUNCTION eko_jurnal_ozgarmaydi()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS kassa_ochilish_faqat_qoshiladi ON kassa_ochilish")
    op.drop_constraint("ck_kassa_taqsimot_manzil", "kassa_taqsimot", type_="check")
    op.drop_constraint("fk_kassa_taqsimot_ochilish_client", "kassa_taqsimot", type_="foreignkey")
    op.drop_index(op.f("ix_kassa_taqsimot_ochilish_client_id"), table_name="kassa_taqsimot")
    op.alter_column("kassa_taqsimot", "order_id", existing_type=sa.INTEGER(), nullable=False)
    op.drop_column("kassa_taqsimot", "ochilish_client_id")
    op.drop_index(op.f("ix_kassa_ochilish_client_id"), table_name="kassa_ochilish")
    op.drop_table("kassa_ochilish")
