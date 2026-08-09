"""Marshrut qadamlari: PartRoute ga `seq` va `process_code`.

Ilgari marshrut tartibsiz to'plam edi — `(part_id, post_id)` yagona indeksi bitta postni
marshrutda faqat BIR MARTA ko'rsatishga majbur qilardi. Sexda esa detal kromkadan
prisadkaga o'tib yana kromkaga qaytishi mumkin, ya'ni takror qadam kerak. Ustiga skan
tartibi postlarning global tartibidan o'qilardi — nostandart marshrut (roverdan
boshlanadigan) uni buzardi.

Endi qadam = qator: `seq` marshrutdagi o'rni, `process_code` esa aynan qaysi amal
(STOLYARKA da 6 xil, KROMKA da 2 xil bor — post nomining o'zi yetarli emas).

Backfill: mavjud qatorlar postlarning tartibi bo'yicha raqamlanadi, `process_code` esa
post uchun odatdagi koddan olinadi (PROCESS_POSTS dagi birinchi kod).

Revision ID: d5a1c93b70e2
Revises: c7f2d84a91b3
Create Date: 2026-08-09
"""

import sqlalchemy as sa
from alembic import op

revision = "d5a1c93b70e2"
down_revision = "c7f2d84a91b3"
branch_labels = None
depends_on = None

# post.code -> odatdagi jarayon kodi (app/services/giblab/models.py DEFAULT_PROCESS_CODE)
_DEFAULT_CODE = {
    "ARRA": 1,
    "KROMKA": 3,
    "OVAL": 5,
    "PRISADKA": 6,
    "ROVER": 7,
    "BOYOQ": 8,
    "STOLYARKA": 9,
}


def upgrade() -> None:
    op.add_column("part_route", sa.Column("seq", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("part_route", sa.Column("process_code", sa.Integer(), nullable=False, server_default="1"))

    # seq — har detal ichida postlarning ishlab chiqarish tartibi bo'yicha
    op.execute(
        """
        UPDATE part_route AS pr
        SET seq = num.rn
        FROM (
            SELECT r.id, row_number() OVER (PARTITION BY r.part_id ORDER BY p.order_index, r.id) AS rn
            FROM part_route r
            JOIN post p ON p.id = r.post_id
        ) AS num
        WHERE num.id = pr.id
        """
    )
    for post_code, code in _DEFAULT_CODE.items():
        op.execute(
            f"""
            UPDATE part_route AS pr SET process_code = {code}
            FROM post p WHERE p.id = pr.post_id AND p.code = '{post_code}'
            """
        )

    op.alter_column("part_route", "seq", server_default=None)
    op.alter_column("part_route", "process_code", server_default=None)

    # Yagonalik post bo'yicha emas, qadam bo'yicha. Post indeksi qidiruv uchun qoladi.
    op.drop_index("ix_part_route_part_post", table_name="part_route")
    op.create_index(
        "ix_part_route_part_seq",
        "part_route",
        ["part_id", "seq"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted"),
    )
    op.create_index("ix_part_route_part_post", "part_route", ["part_id", "post_id"])
    # Skan hisobi endi qadam bo'yicha sanaladi (scanning._scans_done)
    op.create_index("ix_scan_instance_route", "scan", ["instance_id", "route_id"])


def downgrade() -> None:
    op.drop_index("ix_scan_instance_route", table_name="scan")
    op.drop_index("ix_part_route_part_post", table_name="part_route")
    op.drop_index("ix_part_route_part_seq", table_name="part_route")
    op.create_index(
        "ix_part_route_part_post",
        "part_route",
        ["part_id", "post_id"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted"),
    )
    op.drop_column("part_route", "process_code")
    op.drop_column("part_route", "seq")
