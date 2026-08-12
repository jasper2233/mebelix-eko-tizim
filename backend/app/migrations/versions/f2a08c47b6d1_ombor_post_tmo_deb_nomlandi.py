"""OMBOR posti TMO deb nomlandi (Tayyor Mahsulot Ombori).

Kelishilgan atama — tayyor mahsulot qabul qilinadigan joy TMO deyiladi. Faqat
NOM o'zgaradi: post qatori, marshrutlar, skanlar va hisoblagichlar o'z joyida
qoladi (`post.id` tegilmaydi, FK'lar buzilmaydi).

`post.code` VARCHAR ustun (`db_enum(native_enum=False)`), shuning uchun enum
turini o'zgartirish shart emas — qatorni UPDATE qilish yetarli.

Revision ID: f2a08c47b6d1
Revises: d5b71c0a9e34
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f2a08c47b6d1"
down_revision: str | None = "d5b71c0a9e34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE post SET code = 'TMO', name = 'TMO' WHERE code = 'OMBOR'")


def downgrade() -> None:
    op.execute("UPDATE post SET code = 'OMBOR', name = 'Ombor' WHERE code = 'TMO'")
