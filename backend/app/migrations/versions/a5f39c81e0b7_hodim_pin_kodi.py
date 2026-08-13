"""Hodimga shaxsiy PIN kodi

Beyjik kimlikning YAGONA tashuvchisi edi, ya'ni QR skaneri yo'q postda kirish
imkonsiz. ARRA aynan shunday: u yerda chek chiqarish skanning o'zi, shuning uchun
skaner umuman qo'yilmagan va faqat kirish uchun uni sotib olish keraksiz xarajat.

PIN o'sha kimlikning ikkinchi tashuvchisi: monoblokda hodim ismini bosadi va 4-6
raqam teradi (sensorli ekranda raqam paneli — klaviatura kerak emas). Kimlik
baribir SHU `employee` yozuvi, ya'ni smena, skan va ish haqi beyjik bilan bir xil
ishlaydi.

Rolga emas ODAMGA bog'langan: kodda hech qayerda "arrachi" yozilmaydi, admin PIN'ni
kimga kerak bo'lsa o'shanga qo'yadi. Skaner qo'yilsa yoki buzilsa — kod tegilmaydi.

Revision ID: a5f39c81e0b7
Revises: c7e2b4f81d39
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a5f39c81e0b7"
down_revision: str | None = "c7e2b4f81d39"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("employee", sa.Column("pin_hash", sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column("employee", "pin_hash")
