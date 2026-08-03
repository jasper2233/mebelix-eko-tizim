"""Issiq yo'l indekslari: skan lookup (part_instance.qr_text) va Loglar filtri
(audit_log module/action + created_at).

Har skan qr_text bo'yicha aynan-moslik qidiradi — indekssiz eng katta jadvalda
seq scan edi. audit_log eng tez o'suvchi jadval, admin filtrlarisiz qolmasin.

Revision ID: e8b1c6d94f27
Revises: d4f7a8c25e91
Create Date: 2026-08-03
"""

import sqlalchemy as sa
from alembic import op

revision = "e8b1c6d94f27"
down_revision = "d4f7a8c25e91"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_part_instance_qr_text",
        "part_instance",
        ["qr_text"],
        postgresql_where=sa.text("NOT is_deleted"),
    )
    op.create_index("ix_audit_log_module_action", "audit_log", ["module", "action"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_module_action", table_name="audit_log")
    op.drop_index("ix_part_instance_qr_text", table_name="part_instance")
