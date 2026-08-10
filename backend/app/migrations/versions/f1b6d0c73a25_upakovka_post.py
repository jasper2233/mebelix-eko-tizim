"""UPAKOVKA posti — qadoqlash bosqichi.

Bo'yoqdan keyingi oxirgi post. Birligi `m2`: ish haqi qadoqlangan detallar
kvadraturasi bo'yicha hisoblanadi (post `unit` i hajm hisobini boshqaradi).

Marshrutga anketadagi "Upakovka qilish" (`order.survey.packaging`) bayrog'i
bo'yicha qo'shiladi: buyurtma qadoqlansa — HAMMA detalga oxirgi qadam.
Qisman qadoqlash yo'q.

`seed_defaults` prestart'da baribir qo'shadi, lekin migratsiya tugagach baza
darhol to'g'ri bo'lsin (b3e9a1d76c42 dagi BOYOQ bilan bir xil uslub).

Revision ID: f1b6d0c73a25
Revises: e7c4b208af13
Create Date: 2026-08-10
"""

from alembic import op

revision = "f1b6d0c73a25"
down_revision = "e7c4b208af13"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """INSERT INTO post (organization_id, code, name, order_index, unit,
                             requires_assignment_choice, color, icon, is_deleted)
           SELECT 1, 'UPAKOVKA', 'Qadoqlash', 9, 'm2', false, '#0369a1', 'package', false
           WHERE NOT EXISTS (SELECT 1 FROM post WHERE code = 'UPAKOVKA')"""
    )


def downgrade() -> None:
    # Postga bog'langan marshrut/skan bo'lsa FK to'sadi — avval ular tozalanishi kerak.
    op.execute("DELETE FROM post WHERE code = 'UPAKOVKA'")
