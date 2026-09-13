"""andon_event — stanok signal ustunidan (Pico) kelgan xom hodisalar

1-bosqich: prisadka stanogi chiroqlarini Pico o'qiydi, MebeliX agenti USB orqali
olib serverga yuboradi. Jadval faqat xom hodisalarni saqlaydi — to'xtashlar va
OEE keyingi bosqichda shu ma'lumotdan quriladi. Eski OEE jadvallari
(`stop_reason`, `machine_stop`) bu migratsiyada TEGILMAYDI.

Revision ID: 5d8e2a61c0f4
Revises: 7e6946ebd00d
Create Date: 2026-09-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "5d8e2a61c0f4"
down_revision = "7e6946ebd00d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "andon_event",
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("agent_id", sa.Integer(), nullable=True),
        sa.Column("session", sa.String(length=16), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=True),
        sa.Column("prev_state", sa.String(length=16), nullable=True),
        sa.Column("prev_duration_s", sa.Integer(), nullable=True),
        sa.Column("happened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["bridge_agent.id"]),
        sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_andon_event_key", "andon_event", ["machine_id", "session", "seq"], unique=True)
    op.create_index("ix_andon_event_machine_at", "andon_event", ["machine_id", "happened_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_andon_event_machine_at", table_name="andon_event")
    op.drop_index("ix_andon_event_key", table_name="andon_event")
    op.drop_table("andon_event")
