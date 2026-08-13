"""Qurilma bog'lash olib tashlandi — beyjik yolg'iz kifoya.

`d5b71c0a9e34` qo'shgan uchta ustun endi ishlatilmaydi: tsexda kirish uchun
faqat beyjik skani kerak, monoblokni stanokka bog'lash qadami bekor qilindi.

Nega add-keyin-drop juftligi qoldi: `d5b71c0a9e34` allaqachon tarqalgan va
bazalarda bajarilgan. Uni fayldan o'chirib tashlash `alembic` ga o'z holatini
yo'qottirardi ("Can't locate revision"), shuning uchun zanjir buzilmaydi —
ustunlar oldinga qarab olib tashlanadi.

`IF EXISTS`: `d5b71c0a9e34` ni umuman ko'rmagan bazalar ham bor (o'sha qisqa
oyna ichida yaratilganlari).

Revision ID: b83e1f7a25c9
Revises: f2a08c47b6d1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b83e1f7a25c9"
down_revision: str | None = "f2a08c47b6d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_machine_token_hash")
    op.execute("DROP INDEX IF EXISTS ix_machine_pair_code")
    op.execute("ALTER TABLE machine DROP COLUMN IF EXISTS token_hash")
    op.execute("ALTER TABLE machine DROP COLUMN IF EXISTS pair_expires_at")
    op.execute("ALTER TABLE machine DROP COLUMN IF EXISTS pair_code")


def downgrade() -> None:
    op.add_column("machine", sa.Column("pair_code", sa.String(length=8), nullable=True))
    op.add_column("machine", sa.Column("pair_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("machine", sa.Column("token_hash", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_machine_pair_code"), "machine", ["pair_code"], unique=False)
    op.create_index(op.f("ix_machine_token_hash"), "machine", ["token_hash"], unique=True)
