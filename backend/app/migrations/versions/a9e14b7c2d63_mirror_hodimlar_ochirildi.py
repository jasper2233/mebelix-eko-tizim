"""Mirror hodim yozuvlari butunlay o'chirildi.

Mirror — tizim o'zi yaratgan SOXTA hodim: ilgari operator o'z hisobi bilan
(parol bilan) kirib smena ochsa, `scanning.operator_employee` avtomat hodim
yozuvi yasardi, ismi rol nomi bo'lardi ("Arrachi", "Kromkachi"). Ular odam emas
va kim ishlaganini bildirmaydi — bir postdagi HAMMA smena bitta yozuvga tushardi.

Tsexda parol bilan kirish yopilgach funksiya olib tashlandi, yozuvlar esa
`c7e2b4f81d39` da NOFAOL qilinib arxivlangan edi. Egasi 2026-08-19 da ularni
butunlay o'chirishga qaror qildi: proddagi ma'lumot sinov ma'lumoti.

O'chiriladigan bog'lamlar (o'lchangan):
  8 hodim, 410 smena, 120 skan, 34 audit yozuvi.

Skanlar o'chgach `part_route.total_done` eskirib qoladi — u denormalizatsiya
qilingan hisoblagich (`count × per_instance` ga qarshi turadi). Shuning uchun
ta'sirlangan 40 marshrut qatori QOLGAN skanlar bo'yicha qayta sanaladi, aks
holda tablo va terminal bajarilmagan ishni bajarilgan deb ko'rsatardi.

Audit yozuvlari O'CHIRILMAYDI: `employee_id` NULL ga tushiriladi, xabar matni
("Hodim qo'shildi: ...") tarixda qoladi.

Buyurtma HOLATI qayta hisoblanmaydi: skanlar `B-2026-001` (1 skan) va
`TEST-QADOQ` (119 skan) buyurtmalarini `production` ga surgan bo'lishi mumkin,
lekin holat qo'lda ham o'zgartiriladi va uni avtomat orqaga qaytarish
menejerning qaroriga aralashish bo'lardi.

Revision ID: a9e14b7c2d63
Revises: c3d97a1e5b02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a9e14b7c2d63"
down_revision: str | None = "c3d97a1e5b02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Post rollari — mirror yozuvi AYNAN shu rollardagi hisobga bog'langan bo'ladi
POST_ROLES_SQL = (
    "'arrachi', 'kromkachi', 'ovalchi', 'prisadkachi', 'roverchi', 'stolyar', 'boyoqchi', 'upakovkachi', 'omborchi'"
)
MIRROR = f"""
    SELECT e.id FROM employee e
    JOIN "user" u ON u.id = e.user_id
    WHERE u.role IN ({POST_ROLES_SQL})
"""


def upgrade() -> None:
    # Qaysi marshrutlar tegiladi — skanlar o'chishidan OLDIN yozib olamiz
    op.execute(f"""
        CREATE TEMP TABLE _touched_routes AS
        SELECT DISTINCT route_id FROM scan WHERE employee_id IN ({MIRROR}) AND route_id IS NOT NULL
    """)

    op.execute(f"UPDATE audit_log SET employee_id = NULL WHERE employee_id IN ({MIRROR})")
    op.execute(f"DELETE FROM scan WHERE employee_id IN ({MIRROR})")
    op.execute(f"DELETE FROM work_session WHERE employee_id IN ({MIRROR})")
    op.execute(f"DELETE FROM employee WHERE id IN ({MIRROR})")

    # Denormalizatsiyani qolgan skanlar bo'yicha tenglashtiramiz
    op.execute("""
        UPDATE part_route pr
        SET total_done = COALESCE((
            SELECT count(*) FROM scan s
            WHERE s.route_id = pr.id AND s.is_deleted = false
        ), 0)
        WHERE pr.id IN (SELECT route_id FROM _touched_routes)
    """)
    op.execute("DROP TABLE _touched_routes")


def downgrade() -> None:
    # Qaytarilmaydi: o'chirilgan skan va smenalarni tiklashning yo'li yo'q.
    # Mirror yozuvlari allaqachon nofaol arxiv edi va yangi mirror yaratilmaydi
    # (`scanning.operator_employee` olib tashlangan).
    pass
