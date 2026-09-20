"""kromka_measurement: o'lchovni detalga bog'lash

Xom hodisa `andon_event` da qoladi; bu jadval hukmni saqlaydi — qaysi nusxa,
qaysi tomon guruhi (uzunlik/eni), kutilgan o'lcham va farq (docs/12-oee.md §4.10).

Revision ID: e9c1b7d40a26
Revises: d7a2f4e61c58
Create Date: 2026-09-20
"""

import sqlalchemy as sa
from alembic import op

revision = "e9c1b7d40a26"
down_revision = "d7a2f4e61c58"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kromka_measurement",
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("code", sa.String(length=10), nullable=False),
        sa.Column(
            "verdict",
            sa.Enum(
                "mos",
                "nomos",
                "ortiqcha",
                "shubhali",
                "skanersiz",
                name="kromkaverdict",
                native_enum=False,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column("measured_mm", sa.Numeric(precision=9, scale=1), nullable=True),
        sa.Column("scan_id", sa.Integer(), nullable=True),
        sa.Column("instance_id", sa.Integer(), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("side_group", sa.String(length=10), nullable=True),
        sa.Column("expected_mm", sa.Numeric(precision=9, scale=1), nullable=True),
        sa.Column("delta_mm", sa.Numeric(precision=9, scale=1), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["instance_id"], ["part_instance.id"]),
        sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["order.id"]),
        sa.ForeignKeyConstraint(["scan_id"], ["scan.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_kromka_measurement_instance", "kromka_measurement", ["instance_id"])
    op.create_index("ix_kromka_measurement_machine_at", "kromka_measurement", ["machine_id", "measured_at"])
    op.create_index(op.f("ix_kromka_measurement_verdict"), "kromka_measurement", ["verdict"])


def downgrade() -> None:
    op.drop_table("kromka_measurement")
