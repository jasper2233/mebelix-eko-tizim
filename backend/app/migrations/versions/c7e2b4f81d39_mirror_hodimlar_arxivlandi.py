"""Mirror hodim yozuvlari arxivlandi

Ilgari `scanning.operator_employee` post-rol hisobi bilan smena ochilganda
avtomat hodim yozuvi yaratardi: ismi rol nomi ("arrachi", "omborchi"), lavozimi
ham shu. Ular odam emas edi, lekin Hodimlar ro'yxatida haqiqiy ishchilar bilan
aralashib turardi va beyjik ham chiqarilardi.

Post rollari parol bilan kira olmagach (`login.py`) bu yozuvlar smena ocholmaydi
— funksiya butunlay olib tashlandi. Yozuvlarning o'zi QOLADI: ularda haqiqiy skan
tarixi bor va o'chirilsa mahsuldorlik hisoboti buzilardi. Faqat NOFAOL qilinadi,
ya'ni faol ishchilar ro'yxatidan chiqadi.

Ochiq smenalar ham yopiladi: mirror endi `active_session` da E006 beradi, ya'ni
o'sha smena baribir ishlamaydi — operator beyjik bilan qayta kirishi kerak.

Revision ID: c7e2b4f81d39
Revises: d1c4e7a90b52
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e2b4f81d39"
down_revision: str | None = "d1c4e7a90b52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE work_session SET status = 'ended', ended_at = now()
            WHERE status = 'active'
              AND employee_id IN (SELECT id FROM employee WHERE user_id IS NOT NULL)
            """
        )
    )
    op.execute(sa.text("UPDATE employee SET status = 'inactive' WHERE user_id IS NOT NULL"))


def downgrade() -> None:
    # Yozuvlar QAYTA FAOLLASHTIRILMAYDI: qaysi biri ilgari nofaol bo'lganini
    # ajratib bo'lmaydi va mirror'ni faollashtirish uni yana ishchilar
    # ro'yxatiga qaytarardi. Yopilgan smenalar ham tiklanmaydi — ular
    # muddati o'tgan smena bilan bir xil holatda.
    pass
