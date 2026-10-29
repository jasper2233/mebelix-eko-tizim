"""eko 2.3b material sorov

Revision ID: 8e885719d47a
Revises: 47b9face772e
Create Date: 2026-10-29 10:14:31.187886

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8e885719d47a"
down_revision: Union[str, None] = "47b9face772e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "material_sorov",
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("post", sa.String(length=12), nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=True),
        sa.Column("izoh", sa.String(length=200), nullable=False),
        sa.Column("holat", sa.String(length=12), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("yopilgan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("yopgan_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["machine.id"],
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["order.id"],
        ),
        sa.ForeignKeyConstraint(
            ["yopgan_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_material_sorov_ochiq",
        "material_sorov",
        ["order_id", "post"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted AND holat = 'yangi'"),
    )
    op.create_index(op.f("ix_material_sorov_order_id"), "material_sorov", ["order_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_material_sorov_order_id"), table_name="material_sorov")
    op.drop_index(
        "ix_material_sorov_ochiq",
        table_name="material_sorov",
        postgresql_where=sa.text("NOT is_deleted AND holat = 'yangi'"),
    )
    op.drop_table("material_sorov")
