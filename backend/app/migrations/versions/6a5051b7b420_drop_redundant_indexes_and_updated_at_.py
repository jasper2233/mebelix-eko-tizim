"""drop redundant indexes and updated_at default

Revision ID: 6a5051b7b420
Revises: e5b73c04a19f
Create Date: 2026-09-03 05:59:30.849134

Uchta tozalash, hammasi eski kod bilan mos (deploy yiqilsa eski image shu sxemada
ishlayveradi — rollback `SKIP_MIGRATIONS=1`):

* 19 ta `ix_<jadval>_is_deleted` — boolean ustun tanlovsiz, har so'rov uni aniqroq ustun
  bilan filtrlaydi; issiq yo'llardagi PARTIAL indekslar (`WHERE NOT is_deleted`) qoladi.
  Yetim jadvallar (`env.LEGACY_TABLES`) tegilmaydi.
* `ix_pachka_order_status` va `ix_pachka_status` — kodda `pachka.status` yakka predikat emas;
  `ix_pachka_order_id` (order_id) hamma so'rovni qoplaydi.
* `updated_at` ning `current_timestamp(0)` server defaulti — busiz INSERT'da ustun NULL
  qoladi va «hech tahrirlanmagan» belgisi ma'noga ega bo'ladi. Mavjud qatorlar: DB defaulti
  `created_at` bilan bir soniyada qo'ygan vaqt NULL ga to'ldiriladi (soniya aniqligi:
  `current_timestamp(0)` yaxlitlaydi, `created_at` mikrosoniyali).
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6a5051b7b420"
down_revision: Union[str, None] = "e5b73c04a19f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Jonli modellar (SoftDeleteMixin + TimestampMixin); yetim jadvallar ro'yxatda YO'Q.
_TABLES = (
    "audit_log",
    "bridge_agent",
    "client",
    "employee",
    "machine",
    "order",
    "order_file",
    "organization",
    "pachka",
    "pachka_item",
    "part",
    "part_instance",
    "part_route",
    "post",
    "product",
    "scan",
    "user",
    "waste_item",
    "work_session",
)
_PACHKA_INDEXES = (
    ("ix_pachka_order_status", ["order_id", "status"]),
    ("ix_pachka_status", ["status"]),
)


def upgrade() -> None:
    for table in _TABLES:
        op.drop_index(f"ix_{table}_is_deleted", table_name=table)
    for name, _ in _PACHKA_INDEXES:
        op.drop_index(name, table_name="pachka")
    for table in _TABLES:
        op.execute(f'ALTER TABLE "{table}" ALTER COLUMN updated_at DROP DEFAULT')
        op.execute(
            f'UPDATE "{table}" SET updated_at = NULL '
            "WHERE updated_at IS NOT NULL AND updated_at - created_at < interval '1 second'"
        )


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f'UPDATE "{table}" SET updated_at = created_at WHERE updated_at IS NULL')
        op.alter_column(table, "updated_at", server_default=sa.text("current_timestamp(0)"))
    for name, cols in _PACHKA_INDEXES:
        op.create_index(name, "pachka", cols, unique=False)
    for table in _TABLES:
        op.create_index(f"ix_{table}_is_deleted", table, ["is_deleted"], unique=False)
