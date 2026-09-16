"""system_setting.value: String(255) -> Text — ish jadvali JSON bo'lib saqlanadi.

`work_schedule` kaliti smenalar, tanaffuslar, haftalik dam olish kunlari va bayram
sanalarini bitta JSON'da saqlaydi (OEE reja vaqti shundan hisoblanadi). 255 belgi
bir necha bayram sanasidan keyin tugab qolardi. Kalit/qiymat shakli saqlanadi —
jadval faqat butunicha o'qiladi va yoziladi, alohida jadvallar ortiqcha bo'lardi.

Revision ID: c1e8a4b7d9f2
Revises: 5d8e2a61c0f4
Create Date: 2026-09-16
"""

import sqlalchemy as sa
from alembic import op

revision = "c1e8a4b7d9f2"
down_revision = "5d8e2a61c0f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "system_setting", "value", existing_type=sa.String(length=255), type_=sa.Text(), existing_nullable=False
    )


def downgrade() -> None:
    # 255 dan uzun qiymat (katta ish jadvali) bo'lsa downgrade yiqiladi — jimgina kesib
    # yuborishdan ko'ra to'g'ri: kesilgan JSON o'qib bo'lmaydigan bo'lib qolardi.
    op.alter_column(
        "system_setting", "value", existing_type=sa.Text(), type_=sa.String(length=255), existing_nullable=False
    )
