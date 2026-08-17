"""Audit jurnalidagi eski modul nomlari joriylariga birlashtirildi.

Ikki modul qayta nomlangan, lekin `audit_log.module` da eski qiymatlar qolib
ketgan — tarix ikkiga bo'linib, loglar sahifasidagi filtr eski yozuvlarni
umuman ko'rsatmaydi:

  `ombor`     -> `tmo`     (TMO qabul/yuklash; post kodi `f2a08c47b6d1` da
                            OMBOR dan TMO ga o'zgargan, modul nomi qolgan)
  `materials` -> `stock`   (materiallar ombori endpointi `/materials` dan
                            `/stock` ga o'tgan)

Faqat TASNIF maydoni o'zgaradi — `message`, `action`, `user_id`, `created_at`
va `meta` tegilmaydi, ya'ni yozuvning mazmuni saqlanadi. `action` qiymatlari
allaqachon joriy modullar bilan bir xil (`accepted`/`shipped`/`delivered`
tmo.py da, `stock_kirim`/`stock_chiqim` esa endi `move`).

Revision ID: e5b83c04d7a1
Revises: a7c40e29b168
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e5b83c04d7a1"
down_revision: str | None = "a7c40e29b168"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE audit_log SET module = 'tmo' WHERE module = 'ombor'")
    op.execute("UPDATE audit_log SET module = 'stock' WHERE module = 'materials'")


def downgrade() -> None:
    # Eski nom faqat eski amallar bo'yicha tiklanadi — birlashtirilgandan keyin
    # yozilgan yangi qatorlar joriy modulda qolishi kerak. Downgrade TO'LIQ EMAS:
    # `materials` dagi `updated` qatorlarini ajratishning yo'li yo'q (joriy stock
    # tahrirlari ham `updated` yozadi), ular `stock` da qoladi.
    op.execute(
        "UPDATE audit_log SET module = 'ombor' WHERE module = 'tmo' AND action IN ('accepted', 'shipped', 'delivered')"
    )
    op.execute(
        "UPDATE audit_log SET module = 'materials' WHERE module = 'stock' AND action IN ('stock_kirim', 'stock_chiqim')"
    )
