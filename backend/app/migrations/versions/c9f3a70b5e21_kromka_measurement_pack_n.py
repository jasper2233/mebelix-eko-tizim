"""kromka_measurement.pack_n — paketda nechta bo'lak o'tgani (docs/12 §4.26)

Revision ID: c9f3a70b5e21
Revises: b8e2f4a6c013
Create Date: 2026-10-18

15 sm dan kichik detal kromkada yolg'iz o'tmaydi (qaltiraydi) — 4 tagacha detal zich
tiqilib birga o'tkaziladi, Pico esa paketni bitta detal deb o'lchaydi. Shunday o'lchov
bir nechta qirrani yopadi; `pack_n` o'sha qatorlarda paketdagi bo'laklar sonini saqlaydi,
yolg'iz o'tgan detalda esa bo'sh qoladi.
"""

import sqlalchemy as sa
from alembic import op

revision = "c9f3a70b5e21"
down_revision = "b8e2f4a6c013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kromka_measurement", sa.Column("pack_n", sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("kromka_measurement", "pack_n")
