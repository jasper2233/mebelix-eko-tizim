"""`pg_stat_statements` kengaytmasi — qaysi so'rov og'irligini baza o'zi aytsin

2026-09-26 da tsexdagi sekinlik sababi loglardan qo'lda qidirildi: baza qaysi
so'rov qancha vaqt olganini saqlamasdi. Kengaytma `shared_preload_libraries`
bilan yuklanadi (docker-compose.*.yml), bu migratsiya faqat uning ko'rinishini
bazada yaratadi. Yuklanmagan serverda ham CREATE o'tadi — ko'rinishni O'QISH
xato beradi, «Tizim holati» sahifasi buni ushlab «yoqilmagan» deb ko'rsatadi.

Revision ID: d058ecddc8fe
Revises: 6d9d9f645802
"""

from collections.abc import Sequence

from alembic import op

revision: str = "d058ecddc8fe"
down_revision: str | None = "6d9d9f645802"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_stat_statements")
