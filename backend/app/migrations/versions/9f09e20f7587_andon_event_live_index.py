"""`andon_event` — faqat tirik qatorlar bo'yicha qisman indeks (tur, stanok, vaqt)

2026-09-24 dagi Pico dublikatlari yumshoq o'chirilgan (`scripts/kromka_dedup.sql`) va
jadvalda turibdi. Hisobot/tablo so'rovlari `NOT is_deleted` bilan filtrlaydi, lekin
umumiy `(machine_id, happened_at)` indeksi bo'yicha ularni ham o'qib, keyin tashlardi.
Prod nusxasida o'lchandi: natija baytma-bayt bir xil, Kromka-1 oynasi 2,0 -> 1,1 s.

Revision ID: 9f09e20f7587
Revises: d058ecddc8fe
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9f09e20f7587"
down_revision: str | None = "d058ecddc8fe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_andon_event_live",
        "andon_event",
        ["kind", "machine_id", "happened_at"],
        unique=False,
        postgresql_where=sa.text("NOT is_deleted"),
    )


def downgrade() -> None:
    op.drop_index("ix_andon_event_live", table_name="andon_event", postgresql_where=sa.text("NOT is_deleted"))
