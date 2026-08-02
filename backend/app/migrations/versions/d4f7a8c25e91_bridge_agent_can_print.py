"""bridge_agent.can_print — printersiz agent (skan-forvard stansiyasi) chek
navbatidan ish olmasin.

Revision ID: d4f7a8c25e91
Revises: c9e5b2a41d78
Create Date: 2026-08-02
"""

import sqlalchemy as sa
from alembic import op

revision = "d4f7a8c25e91"
down_revision = "c9e5b2a41d78"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bridge_agent",
        sa.Column("can_print", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("bridge_agent", "can_print")
