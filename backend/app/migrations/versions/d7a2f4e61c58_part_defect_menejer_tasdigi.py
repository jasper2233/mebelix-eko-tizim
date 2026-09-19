"""part_defect: menejer tasdig'i — status, aybdor qadam, qayta boshlash nuqtasi

Operator faqat QAYD qiladi; kim aybdor va qayerdan qayta boshlanishini menejer
belgilaydi (docs/12-oee.md §7). OEE Quality `rejected` dan boshqasini sanaydi.

Mavjud qatorlar `pending` bo'lib qoladi — `server_default` faqat shu ko'chirish
uchun, modelda u yo'q (`alembic check` server default'ni solishtirmaydi).

Revision ID: d7a2f4e61c58
Revises: b3f5c17a9d84
Create Date: 2026-09-19
"""

import sqlalchemy as sa
from alembic import op

revision = "d7a2f4e61c58"
down_revision = "b3f5c17a9d84"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "part_defect",
        sa.Column(
            "status",
            sa.Enum("pending", "confirmed", "rejected", name="defectstatus", native_enum=False, length=30),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column("part_defect", sa.Column("blame_route_id", sa.Integer(), nullable=True))
    op.add_column("part_defect", sa.Column("blame_employee_id", sa.Integer(), nullable=True))
    op.add_column("part_defect", sa.Column("restart_route_id", sa.Integer(), nullable=True))
    op.add_column("part_defect", sa.Column("reviewed_by_id", sa.Integer(), nullable=True))
    op.add_column("part_defect", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_part_defect_status"), "part_defect", ["status"], unique=False)
    op.create_foreign_key(None, "part_defect", "part_route", ["blame_route_id"], ["id"])
    op.create_foreign_key(None, "part_defect", "employee", ["blame_employee_id"], ["id"])
    op.create_foreign_key(None, "part_defect", "part_route", ["restart_route_id"], ["id"])
    op.create_foreign_key(None, "part_defect", "user", ["reviewed_by_id"], ["id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_part_defect_status"), table_name="part_defect")
    for column in (
        "reviewed_at",
        "reviewed_by_id",
        "restart_route_id",
        "blame_employee_id",
        "blame_route_id",
        "status",
    ):
        op.drop_column("part_defect", column)
