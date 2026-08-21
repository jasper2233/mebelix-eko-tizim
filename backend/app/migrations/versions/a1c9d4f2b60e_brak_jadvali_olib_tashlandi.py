"""Brak (`defect`) jadvali olib tashlandi — modul umuman ishlatilmaydi.

Brak oqimi `066cd22` da OEE bilan birga o'chirilgan (model, route, UI —
hammasi). Jadval esa bazada yetim qolib ketgan edi: kodda unga hech kim
murojaat qilmaydi, prodda 0 qator. Yetim jadval sxemani o'qishni
chalg'itadi — "demak brak bor ekan" degan xulosa chiqadi.

`10a4a7945eac` o'chirilmaydi (prodda qo'llanib bo'lingan) — o'rniga shu
migratsiya tushiradi. `downgrade` jadvalni to'liq tiklaydi.

Revision ID: a1c9d4f2b60e
Revises: 10a4a7945eac
Create Date: 2026-08-21 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c9d4f2b60e"
down_revision: str | None = "10a4a7945eac"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_defect_status_created", table_name="defect")
    op.drop_index(op.f("ix_defect_is_deleted"), table_name="defect")
    op.drop_index(op.f("ix_defect_instance_id"), table_name="defect")
    op.drop_table("defect")


def downgrade() -> None:
    op.create_table(
        "defect",
        sa.Column("instance_id", sa.Integer(), nullable=False),
        sa.Column("found_post_id", sa.Integer(), nullable=False),
        sa.Column("found_by_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "approved", "rejected", name="defectstatus", native_enum=False, length=30),
            nullable=False,
        ),
        sa.Column("blamed_post_id", sa.Integer(), nullable=True),
        sa.Column("blamed_employee_id", sa.Integer(), nullable=True),
        sa.Column("restart_post_id", sa.Integer(), nullable=True),
        sa.Column("new_instance_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=True
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["blamed_employee_id"], ["employee.id"]),
        sa.ForeignKeyConstraint(["blamed_post_id"], ["post.id"]),
        sa.ForeignKeyConstraint(["found_by_id"], ["employee.id"]),
        sa.ForeignKeyConstraint(["found_post_id"], ["post.id"]),
        sa.ForeignKeyConstraint(["instance_id"], ["part_instance.id"]),
        sa.ForeignKeyConstraint(["new_instance_id"], ["part_instance.id"]),
        sa.ForeignKeyConstraint(["restart_post_id"], ["post.id"]),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_defect_instance_id"), "defect", ["instance_id"], unique=False)
    op.create_index(op.f("ix_defect_is_deleted"), "defect", ["is_deleted"], unique=False)
    op.create_index("ix_defect_status_created", "defect", ["status", "created_at"], unique=False)
