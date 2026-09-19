"""part_defect — brak qaydi (OEE Quality)

Operator terminalda skan tasmasidagi BRAK tugmasi bilan belgilaydi; hisobotda
Quality = (skanlar − brak) ÷ skanlar, brak yo'q bo'lsa 100%.

Nomi `defect` EMAS: o'sha nomdagi eski jadval `a1c9d4f2b60e` da tushirilgan,
uni qayta tiklash tarixni chalkashtirardi (`downtime_reason` bilan bir xil sabab).
Sabab MATN bo'lib saqlanadi — ro'yxat `system_setting.defect_reasons` da va admin
uni o'zgartirsa eski yozuvning ma'nosi buzilmasin.

Revision ID: b3f5c17a9d84
Revises: 9e4b7c1d2a60
Create Date: 2026-09-19
"""

import sqlalchemy as sa
from alembic import op

revision = "b3f5c17a9d84"
down_revision = "9e4b7c1d2a60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "part_defect",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("part_id", sa.Integer(), nullable=False),
        sa.Column("instance_id", sa.Integer(), nullable=False),
        sa.Column("scan_id", sa.Integer(), nullable=True),
        sa.Column("machine_id", sa.Integer(), nullable=True),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=60), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.ForeignKeyConstraint(["instance_id"], ["part_instance.id"]),
        sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["order.id"]),
        sa.ForeignKeyConstraint(["part_id"], ["part.id"]),
        sa.ForeignKeyConstraint(["post_id"], ["post.id"]),
        sa.ForeignKeyConstraint(["scan_id"], ["scan.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_part_defect_machine_at", "part_defect", ["machine_id", "created_at"], unique=False)
    op.create_index("ix_part_defect_instance", "part_defect", ["instance_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_part_defect_instance", table_name="part_defect")
    op.drop_index("ix_part_defect_machine_at", table_name="part_defect")
    op.drop_table("part_defect")
