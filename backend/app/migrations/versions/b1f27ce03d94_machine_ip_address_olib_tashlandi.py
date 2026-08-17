"""`machine.ip_address` olib tashlandi — o'lik ustun.

Egasi 2026-08-17: "IP manzil kerak emas, hech qanday bog'liqlar bo'lmaydi IP
orqali". Tekshirildi: ustunga birorta so'rov, biznes-logika yoki hisobot
murojaat qilmaydi — u faqat sxemada turardi, 9 qatorning hammasida NULL.
Ish markazi bilan aloqa `user.machine_id` va `bridge_agent.machine_id` orqali,
tarmoq manzili orqali emas.

Xuddi shu sabab bilan `c7f2d84a91b3` da shu jadvaldan `mac_address`,
`icon_url`, `serial_number`, `installed_date` olib tashlangan edi.

Revision ID: b1f27ce03d94
Revises: e5b83c04d7a1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1f27ce03d94"
down_revision: str | None = "e5b83c04d7a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("machine", "ip_address")


def downgrade() -> None:
    # Faqat tuzilma qaytadi — qiymat bo'lmagan (hamma qatorda NULL edi)
    op.add_column("machine", sa.Column("ip_address", sa.String(length=45), nullable=True))
