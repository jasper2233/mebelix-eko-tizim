"""OVAL postida detal BITTA marta skanlanadi.

Kod OVAL ni KROMKA bilan bir qatorga qo'ygan edi: marshrutda birinchi kelganda
`per_instance` = detalning kromkalanadigan qirralari soni, ya'ni 4 qirrali detal
oval kromkada ham 4 marta skanlanardi. Bu XATO — oval kromkada detal bitta
o'tishda ishlanadi (egasi 2026-08-19 da tasdiqladi), KROMKA esa har qirrani
alohida yopishtiradi.

Kodning o'z izohlari allaqachon "bitta skan" deb turgan edi
(`KromkaView.tsx:39`, `terminal.py:515`, `seed_defaults.py:37`) — faqat ijro
etiluvchi qism (`orders.py`, `giblab/ingest.py`) boshqacha ishlagan.

Mavjud marshrutlar shu yerda tenglashtiriladi: `per_instance = 1`,
`total_required = part.count`. `total_done` ortiqcha bo'lib qolishi mumkin
(4 skan yozilgan, endi 1 kerak) — u chegaraga tushiriladi, aks holda tablo va
terminalda bosqich 100% dan oshib ketardi. `scan` yozuvlari TEGILMAYDI: ular
haqiqatan bo'lib o'tgan ish tarixi va ish haqi hisobi shundan o'qiydi.

Revision ID: c3d97a1e5b02
Revises: b1f27ce03d94
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c3d97a1e5b02"
down_revision: str | None = "b1f27ce03d94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        UPDATE part_route pr
        SET per_instance = 1,
            total_required = p.count,
            total_done = LEAST(pr.total_done, p.count)
        FROM part p, post po
        WHERE p.id = pr.part_id
          AND po.id = pr.post_id
          AND po.code = 'OVAL'
          AND pr.per_instance > 1
    """)


def downgrade() -> None:
    # Qaytarilmaydi: eski xatti-harakat XATO edi va uni tiklash operatorni
    # bir detalni to'rt marta skanlashga majburlardi. Sxema o'zgarmagan,
    # shuning uchun downgrade'ga hech narsa kerak emas.
    pass
