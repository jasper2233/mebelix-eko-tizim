"""PAZ postini olib tashlash + Bo'yoq postini qo'shish.

Sxema o'zgarmaydi (post.code — VARCHAR), lekin ma'lumot tozalanishi SHART:
`select(Post)` filtrsiz chaqiriladi (seed_defaults prestart'da, orders/reports/
tablo/ingest), va enumda yo'q kod bazada qolsa SQLAlchemy LookupError beradi —
ya'ni konteyner ko'tarilmay qoladi. Shuning uchun soft-delete emas, HARD DELETE.

PAZ ishi yo'qolmaydi: paz frezer stanogida kesiladi, ya'ni ROVER postida.
Prod tekshiruvi (04.08.2026): PAZ da 0 skan, 0 smena, 1 stanok, 4 marshrut —
va o'sha 4 detalning HAMMASIDA ROVER marshruti allaqachon bor, ya'ni ish
rover skanida qamrab olingan. Marshrutlar o'chirilmasa B-2026-003 buyurtmasi
hech qachon "tayyor" bo'lmasdi (skan kutib turaverardi).

Revision ID: b3e9a1d76c42
Revises: a7d3f1c48b26
Create Date: 2026-08-04
"""

from alembic import op

revision = "b3e9a1d76c42"
down_revision = "a7d3f1c48b26"
branch_labels = None
depends_on = None

PAZ = "(SELECT id FROM post WHERE code = 'PAZ')"
PAZ_MACHINES = f"(SELECT id FROM machine WHERE post_id IN {PAZ})"

STATEMENTS = (
    # Pazchi operatorlar roverga o'tadi (prod'da 0 ta, lekin lokal bazalarda bo'lishi mumkin)
    """UPDATE "user" SET role = 'roverchi' WHERE role = 'pazchi'""",
    # Eski "PAZ" kaliti qolsa stanok biriktirish formasi uni qaytadan yuboradi -> 422
    """UPDATE "order" SET machine_assignments = machine_assignments - 'PAZ'
       WHERE machine_assignments ? 'PAZ'""",
    f"DELETE FROM scan WHERE post_id IN {PAZ}",
    f"DELETE FROM part_route WHERE post_id IN {PAZ}",
    f"DELETE FROM work_session WHERE post_id IN {PAZ}",
    # FK sug'urtasi: bitta havola qolsa stanokni o'chirish yiqiladi va deploy yarim yo'lda to'xtaydi
    f"UPDATE part_route SET machine_id = NULL WHERE machine_id IN {PAZ_MACHINES}",
    f"UPDATE scan SET machine_id = NULL WHERE machine_id IN {PAZ_MACHINES}",
    f"""UPDATE "user" SET machine_id = NULL WHERE machine_id IN {PAZ_MACHINES}""",
    f"UPDATE bridge_agent SET machine_id = NULL WHERE machine_id IN {PAZ_MACHINES}",
    f"DELETE FROM machine WHERE post_id IN {PAZ}",
    "DELETE FROM post WHERE code = 'PAZ'",
    # Bo'yoq postini shu yerda ham yaratamiz: seed_defaults prestart'da baribir
    # qo'shadi, lekin migratsiya tugagach baza darhol to'g'ri bo'lsin.
    """INSERT INTO post (organization_id, code, name, order_index, unit,
                         requires_assignment_choice, color, icon, is_deleted)
       SELECT 1, 'BOYOQ', 'Bo''yoq', 8, 'piece', false, '#a16207', 'paint', false
       WHERE NOT EXISTS (SELECT 1 FROM post WHERE code = 'BOYOQ')""",
)


def upgrade() -> None:
    for sql in STATEMENTS:  # asyncpg: bitta execute = bitta statement
        op.execute(sql)


def downgrade() -> None:
    # Qaytarib bo'lmaydi: o'chirilgan post/stanok/marshrutlar tiklanmaydi.
    # Rollback qilinsa seed_defaults PAZ postini bo'sh holda qayta yaratadi.
    op.execute("DELETE FROM post WHERE code = 'BOYOQ'")
