"""`part_instance.cut_meters` — OEE Performance uchun kesim uzunligi.

Arra Performance'i "kesilgan metr x ideal vaqt / RUN" formulasi bilan
hisoblanadi, ya'ni davr ichida qancha metr kesilgani kerak. Manba bor edi —
`order.cutmap` dagi giliotina segmentlari — lekin u JSONB va yuzlab KB:
hisobot har safar o'nlab buyurtmaning xaritasini qayta o'qishi kerak bo'lardi.

Shuning uchun qiymat NUSXAGA yoziladi: arra skani bitta nusxani yopadi, ya'ni
hisobot oddiy SUM ga aylanadi. Bo'linish qoidasi: varaqning kesim uzunligi
undagi DETAL KATAKCHALARI soniga bo'linadi — giliotina kesimi umumiy, qaysi
detalga tegishli ekanini ajratib bo'lmaydi, teng bo'lish esa yig'indida aniq
natija beradi. `mult` ga bo'linmaydi: har varaq takrori uchun alohida nusxa
yaratiladi (`cutmap._place_pattern`), ya'ni ko'paytma nusxalar soni orqali
hisobga olinadi.

Mavjud buyurtmalar SHU YERDA to'ldiriladi — aks holda OEE ishga tushgan
kunning birinchi haftasida eski buyurtmalar nol metr berib, Performance
sun'iy past ko'rinardi.

Revision ID: b2c7e40f9a13
Revises: f3fad5351d8a
"""

from collections.abc import Sequence
from math import hypot

import sqlalchemy as sa
from alembic import op

revision: str = "b2c7e40f9a13"
down_revision: str | None = "f3fad5351d8a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("part_instance", sa.Column("cut_meters", sa.Float(), nullable=True))

    bind = op.get_bind()
    orders = bind.execute(
        sa.text('SELECT id, cutmap FROM "order" WHERE cutmap IS NOT NULL AND NOT is_deleted')
    ).fetchall()
    for order_id, cutmap in orders:
        for material in (cutmap or {}).get("materials", []):
            for sheet in material.get("sheets", []):
                cells = [p for p in sheet.get("parts", []) if not p.get("waste")]
                if not cells:
                    continue
                total_mm = sum(hypot(c["x2"] - c["x1"], c["y2"] - c["y1"]) for c in sheet.get("cuts", []))
                bind.execute(
                    sa.text("UPDATE part_instance SET cut_meters = :m WHERE order_id = :o AND pattern_no = :p"),
                    {"m": total_mm / 1000 / len(cells), "o": order_id, "p": sheet["no"]},
                )


def downgrade() -> None:
    op.drop_column("part_instance", "cut_meters")
