"""Kromka stansiyasi o'zi ochgan brak qaydlarini tozalash

Datchik uzunlikka qarab XATO o'lchayotgani aniqlandi (2026-09-20), ya'ni «o'lcham
mos emas» degan avtomatik qaydlar soxta. Avtomatik brak kodda o'chirildi
(`services/kromka.py`), bu ko'chirish esa allaqachon yozilganlarini olib tashlaydi.

YUMSHOQ o'chirish: qator audit uchun bazada qoladi, lekin brak ro'yxatida ham,
OEE Quality hisobida ham ko'rinmaydi. Faqat TASDIQ KUTAYOTGANLARI: menejer ko'rib
chiqqan qarorga tegilmaydi (tasdiq marshrutni qayta ochgan bo'lishi mumkin).

Revision ID: d4b8e1f37c92
Revises: e9c1b7d40a26
Create Date: 2026-09-20
"""

import sqlalchemy as sa
from alembic import op

revision = "d4b8e1f37c92"
down_revision = "e9c1b7d40a26"
branch_labels = None
depends_on = None

#: Avtomatik qayd shu ikki belgi bilan tanildi (`services/kromka.py: _auto_defect`)
_SABAB = "O'lcham mos emas"
_IZOH = "Stansiya o'lchovi:%"


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE part_defect
               SET is_deleted = true,
                   deleted_at = now()
             WHERE is_deleted = false
               AND status = 'pending'
               AND reason = :sabab
               AND note LIKE :izoh
            """
        ).bindparams(sabab=_SABAB, izoh=_IZOH)
    )


def downgrade() -> None:
    # Qaytarish: o'sha belgilarga mos, shu ko'chirishda o'chirilgan qatorlar
    op.execute(
        sa.text(
            """
            UPDATE part_defect
               SET is_deleted = false,
                   deleted_at = NULL
             WHERE is_deleted = true
               AND status = 'pending'
               AND reason = :sabab
               AND note LIKE :izoh
            """
        ).bindparams(sabab=_SABAB, izoh=_IZOH)
    )
