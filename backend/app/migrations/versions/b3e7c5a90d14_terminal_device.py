"""terminal_device: chek chiqara oladigan post qurilmasi (monoblok)

Terminal hisobi odamga bog'langan, qurilmaga emas — arrachi telefondan o'z
hisobiga kirsa ham chek postdagi printerdan chiqardi (2026-09-24 da ikki bir
xil chek). Ish markazida ulangan qurilma bo'lsa, chek faqat o'sha brauzerdan
chiqadi: admin bir martalik kod beradi, monoblokda kiritiladi, brauzerga
httpOnly cookie (token) yoziladi, bazada — sha256 xeshi (`bridge_agent`
naqshi). Batafsil: `models/terminal_device.py`, docs/03.

Revision ID: b3e7c5a90d14
Revises: c7a2f4e19b03
Create Date: 2026-09-24
"""

import sqlalchemy as sa
from alembic import op

revision = "b3e7c5a90d14"
down_revision = "c7a2f4e19b03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "terminal_device",
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("pair_code", sa.String(length=16), nullable=True),
        sa.Column("pair_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paired_user_agent", sa.String(length=200), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_terminal_device_token_hash"), "terminal_device", ["token_hash"], unique=True)
    op.create_index(op.f("ix_terminal_device_pair_code"), "terminal_device", ["pair_code"])


def downgrade() -> None:
    op.drop_table("terminal_device")
