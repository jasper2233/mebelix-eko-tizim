"""downtime_reason + downtime — stanok to'xtashlari va ularning sababi (OEE Availability)

To'xtash Pico xom hodisalaridan (`andon_event`) chiqariladi, sababni smenadagi hodim terminalda
kiritadi. Sabablar ro'yxatini admin yuritadi. Eski `stop_reason` / `machine_stop` jadvallari
(`LEGACY_TABLES`) bu migratsiyada TEGILMAYDI — nomlar ataylab boshqa.

Revision ID: 9e4b7c1d2a60
Revises: c1e8a4b7d9f2
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from alembic import op

revision = "9e4b7c1d2a60"
down_revision = "c1e8a4b7d9f2"
branch_labels = None
depends_on = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "downtime_reason",
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("is_planned", sa.Boolean(), nullable=False),
        sa.Column("needs_note", sa.Boolean(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        *_base_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "downtime",
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("fault", "off", "idle", "lock", name="downtimekind", native_enum=False, length=30),
            nullable=False,
        ),
        sa.Column("start_key", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("reason_at", sa.DateTime(timezone=True), nullable=True),
        *_base_columns(),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
        sa.ForeignKeyConstraint(["reason_id"], ["downtime_reason.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_downtime_machine_key", "downtime", ["machine_id", "start_key"], unique=True)
    op.create_index("ix_downtime_machine_started", "downtime", ["machine_id", "started_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_downtime_machine_started", table_name="downtime")
    op.drop_index("ix_downtime_machine_key", table_name="downtime")
    op.drop_table("downtime")
    op.drop_table("downtime_reason")
