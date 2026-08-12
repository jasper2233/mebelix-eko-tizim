"""Terminal qurilmasini stanokka bog'lash (beyjik bilan kirish uchun).

Monoblok bir marta 8 belgili kod bilan stanokka bog'lanadi va doimiy token
oladi. Shundan keyin operator login parolsiz, faqat beyjik skani bilan kiradi —
beyjik qog'ozdagi QR bo'lgani uchun u FAQAT bog'langan qurilmada ishlaydi.

Revision ID: d5b71c0a9e34
Revises: c9d4e2f81a70
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5b71c0a9e34"
down_revision: str | None = "c9d4e2f81a70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("machine", sa.Column("pair_code", sa.String(length=8), nullable=True))
    op.add_column("machine", sa.Column("pair_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("machine", sa.Column("token_hash", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_machine_pair_code"), "machine", ["pair_code"], unique=False)
    op.create_index(op.f("ix_machine_token_hash"), "machine", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_machine_token_hash"), table_name="machine")
    op.drop_index(op.f("ix_machine_pair_code"), table_name="machine")
    op.drop_column("machine", "token_hash")
    op.drop_column("machine", "pair_expires_at")
    op.drop_column("machine", "pair_code")
