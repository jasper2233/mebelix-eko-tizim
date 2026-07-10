"""drop demo item table; make user username/phone uniqueness partial (live rows only)

Revision ID: b7f3a9c41d02
Revises: e1c262d7e2ae
Create Date: 2026-07-09 23:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7f3a9c41d02"
down_revision: Union[str, None] = "e1c262d7e2ae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Demo module removed — table had no production data path.
    op.drop_index(op.f("ix_item_is_deleted"), table_name="item")
    op.drop_table("item")

    # Full unique -> partial unique: soft-deleted users release their username/phone.
    op.drop_index(op.f("ix_user_username"), table_name="user")
    op.drop_index(op.f("ix_user_phone"), table_name="user")
    op.create_index("ix_user_username", "user", ["username"], unique=True, postgresql_where=sa.text("NOT is_deleted"))
    op.create_index("ix_user_phone", "user", ["phone"], unique=True, postgresql_where=sa.text("NOT is_deleted"))


def downgrade() -> None:
    op.drop_index("ix_user_phone", table_name="user")
    op.drop_index("ix_user_username", table_name="user")
    op.create_index(op.f("ix_user_phone"), "user", ["phone"], unique=True)
    op.create_index(op.f("ix_user_username"), "user", ["username"], unique=True)

    op.create_table(
        "item",
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("current_timestamp(0)"), nullable=True
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_item_is_deleted"), "item", ["is_deleted"], unique=False)
