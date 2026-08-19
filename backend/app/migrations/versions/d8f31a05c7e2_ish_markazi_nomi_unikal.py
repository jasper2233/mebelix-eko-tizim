"""Ish markazi nomi unikal bo'ldi.

Nom `machine` jadvalida oddiy matn edi, hech qanday cheklovsiz: bitta postga
ikkita "01 ARRA" qo'shsa bo'lardi (sinab ko'rildi — baza qabul qiladi). Bunda:
  - monoblokda operator FAQAT nomni ko'radi (`terminal.tsx` sarlavhasi), ya'ni
    qaysi stanokda turganini ajrata olmaydi;
  - buyurtmani stanokka biriktirishda ro'yxatda ikkita bir xil qator chiqadi;
  - loglarda va hisobotda qaysi biri ekani noma'lum qoladi.

Indeks PARTIAL: o'chirilgan yozuvlar hisobga olinmaydi (loyihadagi boshqa
unikal indekslar bilan bir xil qoida — `ix_employee_badge_id`, `ix_stock_item_code`).

Revision ID: d8f31a05c7e2
Revises: a9e14b7c2d63
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d8f31a05c7e2"
down_revision: str | None = "a9e14b7c2d63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Mavjud dublikatlar bo'lsa indeks yaratilmaydi — avval ularni ajratamiz:
    # ikkinchi va keyingi nusxalarga " (2)", " (3)" qo'shiladi
    op.execute("""
        UPDATE machine m
        SET name = m.name || ' (' || d.rn || ')'
        FROM (
            SELECT id, row_number() OVER (PARTITION BY name ORDER BY id) AS rn
            FROM machine WHERE NOT is_deleted
        ) d
        WHERE d.id = m.id AND d.rn > 1
    """)
    op.create_index(
        "ix_machine_name",
        "machine",
        ["name"],
        unique=True,
        postgresql_where="NOT is_deleted",
    )


def downgrade() -> None:
    op.drop_index("ix_machine_name", table_name="machine")
