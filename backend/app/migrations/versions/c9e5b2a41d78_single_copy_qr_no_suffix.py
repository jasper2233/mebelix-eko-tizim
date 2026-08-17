"""Yagona nusxa QR suffikssiz: count=1 detallarda `_1` olib tashlanadi.

Chekdagi detal kodi, QR matni va SCX fayl nomi endi bir xil — Nanxing skan
mosligi. Migratsiyadan keyin faol buyurtmalarda "SCX qayta yaratish" bosiladi
(fayl nomlari bazadagi QR'dan olinadi); eski chop etilgan `_1` li yorliqlarni
skan qilish suffikssiz fallback orqali ishlayveradi.

Revision ID: c9e5b2a41d78
Revises: a7c3e9d12f04
Create Date: 2026-08-02
"""

from alembic import op

revision = "c9e5b2a41d78"
down_revision = "a7c3e9d12f04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE part_instance pi
        SET qr_text = left(pi.qr_text, -2)
        FROM part p
        WHERE p.id = pi.part_id
          AND p.count = 1
          AND right(pi.qr_text, 2) = '_1'
        """
    )


def downgrade() -> None:
    # Qaytarilmaydi: `_1` bilan tugagan detal kodlari (GibLab `{blok}_{tovar}`
    # sxemasi) uchun teskari UPDATE noaniq — `X_P_1` asli `X_P_1` (kod) ham,
    # `X_P` + suffiks ham bo'lishi mumkin, qo'shish esa unique indeksga uriladi.
    # Eski app kodi baribir yangi QR'larni topa olmaydi — rollback'da yorliqlar
    # qayta chop etiladi.
    pass
