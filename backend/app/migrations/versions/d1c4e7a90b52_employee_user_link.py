"""Hodim <-> operator hisobi bog'lami; ko'zgu beyjiklar haqiqiy beyjikka o'tkazildi.

Ilgari bog'lam `badge_id = "user-{user.id}"` orqali edi. Ikki muammosi bor edi:

1. `user-N` skanerlanadigan beyjik BO'LMASLIGI kerak edi, lekin beyjik kirish
   kaliti bo'lgach u ham kirita boshladi. `N` — kichik butun son, ya'ni terib
   ko'rish bilan istalgan operator nomidan kirsa bo'lardi.
2. Bunday hodimga haqiqiy beyjik chiqarish bog'lamni UZARDI: `operator_employee`
   uni topolmay ikkinchi hodim yozuvi yaratardi va ish haqi ikkiga bo'linardi.

Endi bog'lam alohida `user_id` ustunida, `badge_id` esa erkin — sexda ishlaydigan
HAR bir hodimga haqiqiy beyjik chiqariladi.

Migratsiya `user-N` yozuvlarini topib, `user_id` ni to'ldiradi va beyjikni yangi
UUID ga almashtiradi. `employee.id` tegilmaydi, ya'ni skanlar va ish haqi tarixi
o'z joyida qoladi.

Revision ID: d1c4e7a90b52
Revises: b83e1f7a25c9
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1c4e7a90b52"
down_revision: str | None = "b83e1f7a25c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("employee", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_employee_user_id", "employee", "user", ["user_id"], ["id"])
    op.create_index(
        "ix_employee_user_id",
        "employee",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted"),
    )

    # `user-N` -> user_id = N. Faqat mavjud foydalanuvchiga bog'lanadi: hisob
    # o'chirilgan bo'lsa hodim yozuvi bog'lamsiz qoladi (tarixi saqlanadi).
    #
    # REGEX-CAPTURE bilan: `substring(... from '^user-([0-9]+)$')` mos kelmasa
    # NULL qaytaradi, ya'ni cast xavfsiz. Alohida `~` qo'riqchisi + `substring
    # (... from 6)::int` YARAMAYDI — Postgres AND shartlarini istalgan tartibda
    # bajaradi va cast UUID beyjikda yiqilardi (prodda quruq yurishda tutildi:
    # "invalid input syntax for type integer: 7c1-5260-...").
    op.execute(
        """
        UPDATE employee e
           SET user_id = u.id
          FROM "user" u
         WHERE u.id = substring(e.badge_id from '^user-([0-9]+)$')::int
        """
    )
    # Endi beyjik erkin: har biriga haqiqiy UUID. `gen_random_uuid()` PG13+ da
    # o'rnatilgan (prod PG15.18 da tekshirildi).
    op.execute("UPDATE employee SET badge_id = gen_random_uuid()::text WHERE badge_id ~ '^user-[0-9]+$'")


def downgrade() -> None:
    # Beyjiklar `user-N` ga QAYTARILMAYDI. Ikki sabab:
    #   1. `user-N` — taxmin qilinadigan kirish kaliti edi; uni tiklash, ayniqsa
    #      kod hali yangi bo'lsa, aynan yopilgan teshikni qayta ochardi.
    #      Bu yerda qaysi qator ilgari ko'zgu bo'lganini ajratadigan ustun ham yo'q,
    #      ya'ni chop etib berilgan haqiqiy beyjiklar ham o'chib ketardi.
    #   2. Eski kod baribir bog'lamni topolmay yangi qator yaratadi — bu ish haqi
    #      bo'linishi, lekin taxmin qilinadigan paroldan ko'ra kam zarar.
    op.drop_index("ix_employee_user_id", table_name="employee")
    op.drop_constraint("fk_employee_user_id", "employee", type_="foreignkey")
    op.drop_column("employee", "user_id")
