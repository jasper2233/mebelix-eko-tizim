"""TMO ish markazi "01 OMBOR" dan "01 TMO" ga o'zgartirildi.

Yolg'iz "Ombor" so'zi kelishilgan atamaga ko'ra ishlatilmaydi (`docs/09-mes-domain.md`
1.1) — tsexda ikkita ombor bor, nomsiz atalganda qaysi biri ekani yo'qoladi. Post
kodi `f2a08c47b6d1` da TMO deb nomlangan edi, ish markazining nomi esa eski qolib
ketgan: admin ro'yxatida ham, terminal sarlavhasida ham "01 OMBOR" ko'rinardi.

Faqat NOM o'zgaradi — `machine.id` tegilmaydi, skan/smena/marshrut FK'lari buzilmaydi.

Revision ID: a7c40e29b168
Revises: d2b71f4c86e9
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a7c40e29b168"
down_revision: str | None = "d2b71f4c86e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE machine SET name = '01 TMO' WHERE name = '01 OMBOR'")


def downgrade() -> None:
    op.execute("UPDATE machine SET name = '01 OMBOR' WHERE name = '01 TMO'")
