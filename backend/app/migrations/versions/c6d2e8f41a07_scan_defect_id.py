"""scan.defect_id: brak tasdig'i bekor qilgan skan (OEE uni ish sifatida sanaydi)

Brak tasdiqlanganda nusxa tanlangan qadamdan qayta ochiladi va o'sha qadamdan keyingi
HAMMA skanlar bekor qilinadi — boshqa postlarniki ham (`services/defects.reopen_from_step`).
Hisobot esa faqat brakning O'Z skanini «ish qilingan» deb sanardi: Kromka'da topilgan brak
Prisadka'dan qayta boshlansa, Prisadka'ning Performance'i tushib ketardi, «brak emas» deb
qayta rad etilsa — detal hisobdan abadiy chiqardi. Endi tasdiq bekor qilgan har skanga
belgi qo'yiladi va hisobot uni sanaydi (docs/12 §4.17).

Mavjud ma'lumot: tasdiq skanlarni bitta tranzaksiyada, `reviewed_at` dan millisoniyalar
keyin bekor qiladi — shu nusxaning qayta boshlash qadamidan keyingi, tasdiqdan 5 soniya
ichida bekor qilingan skanlari o'sha brakniki. Taxmin emas — o'sha tranzaksiyaning izi.

Revision ID: c6d2e8f41a07
Revises: b3e7c5a90d14
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

revision = "c6d2e8f41a07"
down_revision = "b3e7c5a90d14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scan", sa.Column("defect_id", sa.Integer(), nullable=True))
    op.create_foreign_key("scan_defect_id_fkey", "scan", "part_defect", ["defect_id"], ["id"])
    op.execute(
        """
        UPDATE scan s
        SET defect_id = d.id
        FROM part_defect d
        JOIN part_route restart ON restart.id = d.restart_route_id
        JOIN part_route r ON r.part_id = restart.part_id AND r.seq >= restart.seq
        WHERE d.status = 'confirmed'
          AND NOT d.is_deleted
          AND d.reviewed_at IS NOT NULL
          AND s.instance_id = d.instance_id
          AND s.route_id = r.id
          AND s.is_cancelled
          AND s.defect_id IS NULL
          AND s.cancelled_at BETWEEN d.reviewed_at AND d.reviewed_at + interval '5 seconds'
        """
    )
    # Hosila skanlar (yig'ma buyumning mayda detallari) — asosiy skan bilan birga bekor qilingan
    op.execute(
        """
        UPDATE scan c
        SET defect_id = p.defect_id
        FROM scan p
        WHERE c.parent_scan_id = p.id
          AND p.defect_id IS NOT NULL
          AND c.defect_id IS NULL
          AND c.is_cancelled
          AND c.cancelled_at = p.cancelled_at
        """
    )


def downgrade() -> None:
    op.drop_constraint("scan_defect_id_fkey", "scan", type_="foreignkey")
    op.drop_column("scan", "defect_id")
