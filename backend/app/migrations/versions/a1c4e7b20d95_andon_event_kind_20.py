"""`andon_event.kind` — 10 dan 20 belgiga

`AndonEventIn.type` kromka hodisasi `avariya_toxtash` ni qabul qiladi (15 belgi), ustun esa
`VARCHAR(10)` edi: INSERT "value too long" bilan yiqilib, butun partiya 500 qaytarardi. Agent
partiyani navbatda saqlab har 30 s qayta yuboradi — ya'ni bitta avariya hodisasidan keyin shu
stansiyaning HAMMA keyingi hodisalari (o'lchov, holat, tezlik) serverga yetmay qolardi.
Prodda 2026-09-27 11:39 da shunday bo'ldi.

`varchar` ni kengaytirish jadvalni qayta yozmaydi; `kind` ni o'z ichiga olgan qisman
`ix_andon_event_live` indeksi esa qayta quriladi (sinovda o'lchandi). Prod nusxasida (291 ming
qator, 33 ming tirik) ALTER 76 ms — jadval qulfi shuncha.

Revision ID: a1c4e7b20d95
Revises: 9f09e20f7587
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c4e7b20d95"
down_revision: str | None = "9f09e20f7587"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "andon_event", "kind", type_=sa.String(length=20), existing_type=sa.String(length=10), existing_nullable=False
    )


def downgrade() -> None:
    op.alter_column(
        "andon_event", "kind", type_=sa.String(length=10), existing_type=sa.String(length=20), existing_nullable=False
    )
