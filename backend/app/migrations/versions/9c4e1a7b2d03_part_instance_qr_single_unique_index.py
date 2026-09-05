"""part_instance qr: bitta global unique indeks

Revision ID: 9c4e1a7b2d03
Revises: 2f1649a8968e
Create Date: 2026-09-05 06:10:00.000000

MVP ma'lumotlari tozalangach (2026-09-05) prefikssiz jonli nusxa qolmadi, ya'ni
`ix_part_instance_qr_serial` predikatidagi `qr_text ~ '^B-...'` sharti hech nimani
chiqarib tashlamaydi. Shart olib tashlanadi va indeks GLOBAL unikal bo'ladi —
shundan keyin `ix_part_instance_order_qr` (order_id, qr_text) va oddiy lookup
indeksi `ix_part_instance_qr_text` ortiqcha: ikkalasi ham shu bitta indeks bilan
qoplanadi (order bo'yicha skan `order_id` FK indeksidan yuradi).
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c4e1a7b2d03"
down_revision: Union[str, None] = "2f1649a8968e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_SERIAL_WHERE = sa.text("NOT is_deleted AND qr_text ~ '^B-[0-9]{4}-[0-9]+_'")
_NEW_WHERE = sa.text("NOT is_deleted")


def upgrade() -> None:
    op.drop_index("ix_part_instance_qr_serial", table_name="part_instance", postgresql_where=_OLD_SERIAL_WHERE)
    op.create_index(
        "ix_part_instance_qr_serial", "part_instance", ["qr_text"], unique=True, postgresql_where=_NEW_WHERE
    )
    op.drop_index("ix_part_instance_order_qr", table_name="part_instance", postgresql_where=_NEW_WHERE)
    op.drop_index("ix_part_instance_qr_text", table_name="part_instance", postgresql_where=_NEW_WHERE)


def downgrade() -> None:
    op.create_index("ix_part_instance_qr_text", "part_instance", ["qr_text"], unique=False, postgresql_where=_NEW_WHERE)
    op.create_index(
        "ix_part_instance_order_qr", "part_instance", ["order_id", "qr_text"], unique=True, postgresql_where=_NEW_WHERE
    )
    op.drop_index("ix_part_instance_qr_serial", table_name="part_instance", postgresql_where=_NEW_WHERE)
    op.create_index(
        "ix_part_instance_qr_serial",
        "part_instance",
        ["qr_text"],
        unique=True,
        postgresql_where=_OLD_SERIAL_WHERE,
    )
