"""user.name 30 -> 100 belgi

Ustun VARCHAR(30) edi, `UserCreate`/`UserUpdate` esa 100 belgigacha qabul qilardi
(`schemas/users.py:_NAME_FIELD`) — 31-100 belgili F.I.Sh validatsiyadan o'tib
INSERT da yiqilardi. `employee.full_name` allaqachon 100, ikkalasi bir xil bo'ladi.

Revision ID: e5b73c04a19f
Revises: af6809b43a73
Create Date: 2026-08-29 12:00:00.000000

"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5b73c04a19f"
down_revision: Union[str, None] = "af6809b43a73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "user",
        "name",
        existing_type=sa.String(length=30),
        type_=sa.String(length=100),
        existing_nullable=True,
    )


def downgrade() -> None:
    # 100 belgili nom 30 ga sig'maydi — qisqartirib qaytariladi.
    op.execute('UPDATE "user" SET name = left(name, 30) WHERE length(name) > 30')
    op.alter_column(
        "user",
        "name",
        existing_type=sa.String(length=100),
        type_=sa.String(length=30),
        existing_nullable=True,
    )
