"""eko 2.4 jurnal va cheklovlar: qoldiq manfiy emas, jurnal/audit faqat qo'shiladi, jurnal = qoldiq

Revision ID: e24a0c1b7f31
Revises: d5f2d32fb705
Create Date: 2026-10-29 12:00:00

1. Boshlang'ich qoldiqlar (import/seed bilan HARAKATSIZ yozilganlar) jurnalga o'tkaziladi: har pozitsiyada
   `quantity − Σ harakat` farqi bitta `boshlangich` harakat bo'lib, eng birinchi harakatdan oldingi vaqt
   bilan yoziladi. Shundan keyin qoida: qoldiq = harakatlar yig'indisi.
2. CHECK cheklovlari `NOT VALID` qo'shiladi (yangi yozuvlarga darhol amal qiladi), keyin eski qatorlar
   tekshiriladi. Prodda eski buzuq qator bo'lsa deploy yiqilmaydi — WARNING beradi va cheklov
   «tasdiqlanmagan» qoladi; `ombor_solishtirish` buyrug'i o'sha qatorlarni ko'rsatadi.
3. `stock_movement` va `audit_log` ga UPDATE/DELETE taqiqlovchi trigger (TRUNCATE ga tegmaydi).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e24a0c1b7f31"
down_revision: str | None = "d5f2d32fb705"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHECKS = [
    ("catalog_item", "ck_catalog_item_quantity_nonneg", "quantity >= 0"),
    ("stock_lot", "ck_stock_lot_qty_left", "qty_left >= 0 AND qty_left <= qty"),
    ("material_birlik", "ck_material_birlik_qoldiq", "qoldiq >= 0 AND qoldiq <= hajm"),
    ("rezerv_line", "ck_rezerv_line_qty", "qoplangan_qty >= 0 AND berilgan_qty >= 0 AND kerak_qty >= 0"),
]
JOURNALS = ["stock_movement", "audit_log"]


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO stock_movement (item_id, kind, qty, balance, note, created_at, is_deleted)
        SELECT c.id, 'boshlangich', c.quantity - COALESCE(m.s, 0), c.quantity - COALESCE(m.s, 0),
               'Boshlang''ich qoldiq (jurnalga o''tkazildi)',
               LEAST(c.created_at, COALESCE(m.first_at, c.created_at)) - interval '1 second', false
        FROM catalog_item c
        LEFT JOIN (
            SELECT item_id, SUM(qty) AS s, MIN(created_at) AS first_at FROM stock_movement GROUP BY item_id
        ) m ON m.item_id = c.id
        WHERE c.catalog <> 'X' AND c.quantity - COALESCE(m.s, 0) <> 0
        """
    )
    for table, name, cond in CHECKS:
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({cond}) NOT VALID")
        op.execute(
            f"""
            DO $$ BEGIN
                ALTER TABLE {table} VALIDATE CONSTRAINT {name};
            EXCEPTION WHEN check_violation THEN
                RAISE WARNING '{name}: eski qatorlar qoidani buzadi — ombor_solishtirish ni yurgizing';
            END $$;
            """
        )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION eko_jurnal_ozgarmaydi() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '%: jurnal faqat qo''shiladi — tuzatish teskari yozuv bilan', TG_TABLE_NAME
                USING ERRCODE = 'restrict_violation';
        END $$;
        """
    )
    for t in JOURNALS:
        op.execute(
            f"CREATE TRIGGER {t}_faqat_qoshiladi BEFORE UPDATE OR DELETE ON {t} "
            "FOR EACH ROW EXECUTE FUNCTION eko_jurnal_ozgarmaydi()"
        )


def downgrade() -> None:
    for t in JOURNALS:
        op.execute(f"DROP TRIGGER IF EXISTS {t}_faqat_qoshiladi ON {t}")
    op.execute("DROP FUNCTION IF EXISTS eko_jurnal_ozgarmaydi()")
    for table, name, _ in CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}")
    # Boshlang'ich harakatlar qoldiriladi: ular qoldiqni o'zgartirmagan, faqat jurnalni to'ldirgan
