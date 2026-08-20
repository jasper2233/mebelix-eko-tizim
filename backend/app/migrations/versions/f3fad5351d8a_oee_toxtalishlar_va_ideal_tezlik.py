"""OEE poydevori: to'xtalishlar, rejalashtirilgan vaqt, ideal tezlik.

Availability = RUN TIME / PLANNED TIME uchun uch narsa kerak edi va uchalasi
ham bazada yo'q edi:

  stop_reason   to'xtash sabablari ro'yxati. `excludes_planned` bayrog'i har
                sabab uchun HISOBNI hal qiladi: True bo'lsa vaqt PLANNED dan
                ayriladi (tushlik, tanaffus — OEE tushmaydi), False bo'lsa
                RUN dan chiqadi va PLANNED joyida qoladi, ya'ni Availability
                yo'qotishi (sozlash, nosozlik, material yo'q).
  machine_stop  bitta to'xtash oralig'i; `ended_at IS NULL` = hozir to'xtab
                turibdi. Ish markaziga yoziladi, smenaga emas — stanok
                operatorsiz ham to'xtaydi ("operator yo'q", "zakaz yo'q").
  machine       + `planned_minutes_per_day` (kuniga reja, 8 soat = 480)
                + `ideal_rate` (Performance uchun ideal tezlik; ma'nosi
                  postdan keladi — ARRA sek/m, KROMKA m/daq, PRISADKA
                  sek/teshik. HAR STANOKDA O'ZINIKI: bir postdagi ikki
                  stanokning konfiguratsiyasi bir xil bo'lmaydi. NULL =
                  Performance hisoblanmaydi, faqat Availability ko'rinadi)

Sabablar ro'yxati bu yerda EMAS, `seed_defaults` da to'ldiriladi — u har
deployda ishlaydi va idempotent, ya'ni ro'yxat kod bilan birga o'sadi.

Revision ID: f3fad5351d8a
Revises: e7a35c19d840
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3fad5351d8a"
down_revision: str | None = "e7a35c19d840"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stop_reason",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column(
            "kind", sa.Enum("planned", "unplanned", name="stopkind", native_enum=False, length=30), nullable=False
        ),
        sa.Column("excludes_planned", sa.Boolean(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stop_reason_is_deleted"), "stop_reason", ["is_deleted"], unique=False)
    op.create_index(
        "ix_stop_reason_name", "stop_reason", ["name"], unique=True, postgresql_where=sa.text("NOT is_deleted")
    )
    op.create_table(
        "machine_stop",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("machine_id", sa.Integer(), nullable=False),
        sa.Column("reason_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
        sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
        sa.ForeignKeyConstraint(["reason_id"], ["stop_reason.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_machine_stop_is_deleted"), "machine_stop", ["is_deleted"], unique=False)
    op.create_index("ix_machine_stop_machine_started", "machine_stop", ["machine_id", "started_at"], unique=False)
    op.add_column(
        "machine", sa.Column("planned_minutes_per_day", sa.Integer(), server_default=sa.text("480"), nullable=False)
    )
    op.add_column("machine", sa.Column("ideal_rate", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("machine", "ideal_rate")
    op.drop_column("machine", "planned_minutes_per_day")
    op.drop_index("ix_machine_stop_machine_started", table_name="machine_stop")
    op.drop_index(op.f("ix_machine_stop_is_deleted"), table_name="machine_stop")
    op.drop_table("machine_stop")
    op.drop_index("ix_stop_reason_name", table_name="stop_reason", postgresql_where=sa.text("NOT is_deleted"))
    op.drop_index(op.f("ix_stop_reason_is_deleted"), table_name="stop_reason")
    op.drop_table("stop_reason")
