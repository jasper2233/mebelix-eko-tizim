"""OMBOR posti — tayyor mahsulot ombori.

Marshrutning ENG OXIRGI qadami, har detalda (qadoqlangan ham, qadoqlanmagan ham).
Omborchi qabul qilganda yopiladi: qadoqsiz buyurtmada detal QR'i bilan birma-bir,
qadoqlanganda esa qadoq QR'i bitta skanda ichidagi hamma detalni yopadi.

Nega marshrut qadami: shusiz "tayyor" degani "ishlab chiqarish tugadi" bo'lardi, ya'ni
oxirgi postda qolib ketgan yoki yo'lda yo'qolgan detal ham omborda deb ko'rinardi.
Qadam bilan esa "tayyor, lekin omborga topshirilmagan" holati ro'yxatda ko'rinib turadi.

Birligi `dona`: ombor ishi kvadratura bilan emas, joy soni bilan o'lchanadi.

Revision ID: a3f8d61c9b04
Revises: 7e2e0ae9f7f3
Create Date: 2026-08-10
"""

from alembic import op

revision = "a3f8d61c9b04"
down_revision = "7e2e0ae9f7f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """INSERT INTO post (organization_id, code, name, order_index, unit,
                             requires_assignment_choice, color, icon, is_deleted)
           SELECT 1, 'OMBOR', 'Ombor', 10, 'piece', false, '#7c2d12', 'warehouse', false
           WHERE NOT EXISTS (SELECT 1 FROM post WHERE code = 'OMBOR')"""
    )


def downgrade() -> None:
    # Postga bog'langan marshrut/skan bo'lsa FK to'sadi — avval ular tozalanishi kerak.
    op.execute("DELETE FROM post WHERE code = 'OMBOR'")
