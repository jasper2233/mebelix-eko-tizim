"""Yig'ma buyum: mayda detalni asosiy detalga biriktirish.

Stolyarkada bir nechta mayda detal asosiy detalga yopishtirilib yaxlit buyum
bo'ladi. `part.assembly_parent_id` shu bog'lamni saqlaydi, `scan.parent_scan_id`
esa asosiy detal skani yozgan hosila skanlarni belgilaydi (birga bekor bo'lishi
uchun).

Revision ID: c9d4e2f81a70
Revises: a3f8d61c9b04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9d4e2f81a70"
down_revision: str | None = "a3f8d61c9b04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("part", sa.Column("assembly_parent_id", sa.Integer(), nullable=True))
    op.create_index("ix_part_assembly_parent_id", "part", ["assembly_parent_id"])
    op.create_foreign_key("fk_part_assembly_parent", "part", "part", ["assembly_parent_id"], ["id"])

    op.add_column("scan", sa.Column("parent_scan_id", sa.Integer(), nullable=True))
    op.create_index("ix_scan_parent_scan_id", "scan", ["parent_scan_id"])
    op.create_foreign_key("fk_scan_parent_scan", "scan", "scan", ["parent_scan_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_scan_parent_scan", "scan", type_="foreignkey")
    op.drop_index("ix_scan_parent_scan_id", table_name="scan")
    op.drop_column("scan", "parent_scan_id")

    op.drop_constraint("fk_part_assembly_parent", "part", type_="foreignkey")
    op.drop_index("ix_part_assembly_parent_id", table_name="part")
    op.drop_column("part", "assembly_parent_id")
