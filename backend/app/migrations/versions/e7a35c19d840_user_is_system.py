"""`user.is_system` — texnik hisobni odam hisobidan ajratadi.

Tsex xodimi endi SHAXSIY login va parol bilan kirishi mumkin (skanersiz postda,
masalan ARRA). Ilgari post rolidagi HAR qanday hisobga parol bilan kirish yopiq
edi, chunki o'sha paytda har postda BITTA umumiy hisob bor edi va uning paroli
butun smenaga ma'lum bo'lardi.

Endi ikki xil hisob bir xil rolda yashaydi:
  is_system=False  odamning shaxsiy hisobi — kiradi, smenasi o'ziga yoziladi
  is_system=True   `seed_defaults` yaratgan texnik hisob — beyjik bilan kirishda
                   smena SHU hisob nomidan ochiladi (`login._terminal_user`),
                   lekin uning o'zi hech qachon kirmaydi (paroli tasodifiy)

Mavjud post hisoblarining HAMMASI texnik deb belgilanadi va bu aniq: shaxsiy
hisob tushunchasi aynan shu migratsiyadan keyin paydo bo'ladi, ya'ni undan
oldingi har bir post hisobi — `seed_defaults` yoki sinov qoldig'i, odamniki emas.
Nom/telefon shabloniga qarash mo'rt bo'lardi: eski seed boshqacha yaratgan
hisoblar belgilanmay qolib, ular bilan parol orqali kirish OCHIQ qolardi.

Revision ID: e7a35c19d840
Revises: d8f31a05c7e2
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7a35c19d840"
down_revision: str | None = "d8f31a05c7e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

POST_ROLES_SQL = (
    "'arrachi', 'kromkachi', 'ovalchi', 'prisadkachi', 'roverchi', 'stolyar', 'boyoqchi', 'upakovkachi', 'omborchi'"
)


def upgrade() -> None:
    op.add_column("user", sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute(f"""
        UPDATE "user"
        SET is_system = true
        WHERE role IN ({POST_ROLES_SQL})
    """)


def downgrade() -> None:
    op.drop_column("user", "is_system")
