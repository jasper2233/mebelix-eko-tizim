"""paz/freza bor detalga PRISADKA qadami (mavjud buyurtmalarga ham)

Marshrutga CNC qadami faqat TESHIK bo'lganda qo'shilardi. Paz yoki freza bor,
teshigi yo'q detal marshrutsiz qolardi: SCX fayli yaratilar, lekin uni
bajaradigan post yo'q edi — detal ishlov KO'RMASDAN o'tib ketardi.

Parser tuzatildi (`giblab/models.py: stage_sides`), lekin u faqat YANGI
yuklamaga ta'sir qiladi. Bu migratsiya allaqachon yuklangan buyurtmalarni ham
tuzatadi — ular hali PRISADKA postiga yetib kelmagan.

Qamrov ATAYLAB tor:

  · `is_custom` detal TEGILMAYDI — uning marshrutini texnolog o'zi chizgan
    (masalan ARRA -> ROVER -> BOYOQ -> TMO: paz roverda qilinadi). Avtomatik
    qadam qo'shish uning qarorini buzardi.
  · PRISADKA qadami allaqachon bor detal ham tegilmaydi.
  · Bekor qilingan buyurtma tegilmaydi.
  · Qadam ingest bilan BIR XIL joyga qo'yiladi: KROMKA'dan keyin,
    UPAKOVKA/TMO dan oldin.

`(part_id, seq)` yagona indeks bo'lgani uchun surish IKKI bosqichda: avval
katta ofsetga, keyin joyiga. Bitta `UPDATE` da vaqtincha to'qnashuv bo'lardi.

Revision ID: a7c419e0b3d5
Revises: c5e81b3a97d2
"""

import sqlalchemy as sa
from alembic import op

revision = "a7c419e0b3d5"
down_revision = "c5e81b3a97d2"
branch_labels = None
depends_on = None

#: Nishon detallar: ishlov bor (paz yoki freza), teshik yo'q, texnolog tegmagan
#: va CNC qadami hali yo'q. `joy` — qadam qo'yiladigan `seq`.
NISHON = sa.text("""
    SELECT p.id AS part_id,
           p.count AS cnt,
           p.order_id,
           COALESCE((SELECT MIN(r.seq) FROM part_route r
                     WHERE r.part_id = p.id AND NOT r.is_deleted
                       AND r.process_code IN (15, 16)),
                    (SELECT COALESCE(MAX(r.seq), 0) + 1 FROM part_route r
                     WHERE r.part_id = p.id AND NOT r.is_deleted)) AS joy
    FROM part p
    JOIN "order" o ON o.id = p.order_id
    WHERE NOT p.is_deleted
      AND NOT p.is_custom
      AND NOT o.is_deleted
      AND o.status <> 'cancelled'
      AND COALESCE((p.xnc_summary->>'bores')::int, 0) = 0
      AND COALESCE((p.xnc_summary->>'edge_bores')::int, 0) = 0
      AND (COALESCE((p.xnc_summary->>'grooves')::int, 0) > 0
           OR COALESCE((p.xnc_summary->>'mills')::int, 0) > 0)
      AND NOT EXISTS (SELECT 1 FROM part_route r
                      JOIN post po ON po.id = r.post_id
                      WHERE r.part_id = p.id AND NOT r.is_deleted AND po.code = 'PRISADKA')
""")

SURISH = sa.text("UPDATE part_route SET seq = seq + 1000 WHERE part_id = :part_id AND NOT is_deleted AND seq >= :joy")

#: `per_instance` = 1: bu detallarda ishlov bitta tomonda (teshik yo'q, ya'ni
#: ikkinchi tomon dasturi ham yo'q). `total_required` = nusxalar soni.
QOSHISH = sa.text(
    "INSERT INTO part_route "
    "(order_id, part_id, post_id, seq, process_code, source, per_instance, "
    " total_required, total_done, is_enabled, is_deleted) "
    "VALUES (:order_id, :part_id, :post_id, :joy, 6, 'auto', 1, :cnt, 0, true, false)"
)

QAYTARISH = sa.text("UPDATE part_route SET seq = seq - 999 WHERE part_id = :part_id AND NOT is_deleted AND seq >= 1000")


def upgrade() -> None:
    conn = op.get_bind()
    prisadka = conn.execute(sa.text("SELECT id FROM post WHERE code = 'PRISADKA'")).scalar()
    if prisadka is None:  # post sozlanmagan baza (bo'sh/test) — qiladigan ish yo'q
        return
    for row in conn.execute(NISHON).mappings().all():
        p = {"part_id": row["part_id"], "joy": row["joy"]}
        conn.execute(SURISH, p)
        conn.execute(QOSHISH, {**p, "order_id": row["order_id"], "post_id": prisadka, "cnt": row["cnt"]})
        conn.execute(QAYTARISH, {"part_id": row["part_id"]})


def downgrade() -> None:
    # FAQAT skani yo'q qadamlar qaytariladi: skan yozilgan bo'lsa qadam haqiqiy
    # ishga aylangan va uni olib tashlash hisobni buzardi. `seq` qayta
    # zichlanmaydi — bo'shliq zararsiz, tartib saqlanadi.
    op.get_bind().execute(
        sa.text("""
        DELETE FROM part_route r
        USING post po, part p
        WHERE po.id = r.post_id AND p.id = r.part_id
          AND po.code = 'PRISADKA' AND r.source = 'auto' AND r.total_done = 0
          AND NOT p.is_custom
          AND COALESCE((p.xnc_summary->>'bores')::int, 0) = 0
          AND COALESCE((p.xnc_summary->>'edge_bores')::int, 0) = 0
          AND (COALESCE((p.xnc_summary->>'grooves')::int, 0) > 0
               OR COALESCE((p.xnc_summary->>'mills')::int, 0) > 0)
          AND NOT EXISTS (SELECT 1 FROM scan s WHERE s.route_id = r.id)
        """)
    )
