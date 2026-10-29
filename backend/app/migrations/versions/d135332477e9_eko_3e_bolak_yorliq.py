"""eko 3e bolak yorliq

Revision ID: d135332477e9
Revises: 9e40040d8960
Create Date: 2026-10-29 12:08:24.000574

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d135332477e9"
down_revision: Union[str, None] = "9e40040d8960"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ombor_bolak_yorliq",
        sa.Column("bolak_id", sa.Integer(), nullable=False),
        sa.Column("waste_id", sa.Integer(), nullable=False),
        sa.Column("qr", sa.String(length=120), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bolak_id"],
            ["ombor_bolak.id"],
        ),
        sa.ForeignKeyConstraint(
            ["waste_id"],
            ["waste_item.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("qr"),
        sa.UniqueConstraint("waste_id"),
    )
    op.create_index(op.f("ix_ombor_bolak_yorliq_bolak_id"), "ombor_bolak_yorliq", ["bolak_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ombor_bolak_yorliq_bolak_id"), table_name="ombor_bolak_yorliq")
    op.drop_table("ombor_bolak_yorliq")
