"""`part_instance.label_post_id` — chekni qaysi post chiqargan.

Bekor qilish huquqi shu ustunga tayanadi: chekni chiqargan post o'zi
qaytaradi, boshqasi tegolmaydi. Ilgari dalil faqat skanda edi, chek esa
skansiz ham chiqishi mumkin (roverchi arradan keladigan detalning chekini
chiqarsa, `record_scan` E001 bilan rad etadi) — o'shanda boshqa post chekni
tozalab yubora olardi.

Eski qatorlar chop etish YOZGAN skandan to'ldiriladi; skani yo'qlari NULL
bo'lib qoladi (dalil yo'q, taxmin qilinmaydi).

Revision ID: c5e81b3a97d2
Revises: a1c9d4f2b60e
Create Date: 2026-08-21 12:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5e81b3a97d2"
down_revision: str | None = "a1c9d4f2b60e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("part_instance", sa.Column("label_post_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_part_instance_label_post_id_post", "part_instance", "post", ["label_post_id"], ["id"])
    # Chek chiqarilgan, lekin egasi noma'lum qatorlar — chop etish yozgan
    # skandan olinadi (`cutprint-*`). Bir nechta bo'lsa oxirgisi: chek qayta
    # chiqarilgan bo'lsa ham amaldagi egasi o'sha.
    op.execute(
        """
        UPDATE part_instance AS pi
           SET label_post_id = s.post_id
          FROM (
                SELECT DISTINCT ON (instance_id) instance_id, post_id
                  FROM scan
                 WHERE client_event_id LIKE 'cutprint-%'
                   AND NOT is_cancelled
                   AND NOT is_deleted
                 ORDER BY instance_id, created_at DESC
               ) AS s
         WHERE s.instance_id = pi.id
           AND pi.label_printed_at IS NOT NULL
           AND pi.label_post_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_constraint("fk_part_instance_label_post_id_post", "part_instance", type_="foreignkey")
    op.drop_column("part_instance", "label_post_id")
