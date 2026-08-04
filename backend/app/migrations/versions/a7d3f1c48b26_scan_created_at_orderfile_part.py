"""Yana ikki issiq yo'l indeksi.

scan.created_at — dashboard "bugungi skanlar" hisoblagichi har 60 soniyada
so'raydi; indekssiz butun jadval skanerlanardi va narx tarix o'sgani sari
ortardi (natija esa doim bir kunlik).

order_file.part_id — har CNC skanida detalning SCX fayli shu ustun bo'yicha
qidiriladi; boshqa barcha FK'lar indekslangan, bittasi tushib qolgan edi.

Revision ID: a7d3f1c48b26
Revises: e8b1c6d94f27
Create Date: 2026-08-04
"""

from alembic import op

revision = "a7d3f1c48b26"
down_revision = "e8b1c6d94f27"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_scan_created_at", "scan", ["created_at"])
    op.create_index(op.f("ix_order_file_part_id"), "order_file", ["part_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_order_file_part_id"), table_name="order_file")
    op.drop_index("ix_scan_created_at", table_name="scan")
