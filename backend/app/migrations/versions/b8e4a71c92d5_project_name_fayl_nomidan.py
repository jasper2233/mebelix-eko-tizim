"""`order.project_name` bo'sh qolganlarni yuklangan fayl nomidan to'ldirish.

Ilgari nom fayl ICHIDAGI `<root name=...>` atributidan olinardi (`parser.py`),
GibLab eksportlarining bir qismida esa u umuman yo'q. Natijada `.project` fayli
yuklangan buyurtmada ham nom BO'SH qolardi va reestrda ham, TABLOda ham
ko'rinmasdi (prodda 39 buyurtmadan 20 tasi shunday edi).

Kod endi nomni fayl nomidan oladi (`ingest.py`). Shu migratsiya esa MAVJUD
yozuvlarni o'sha qoida bo'yicha to'ldiradi: `order_file` dagi `kind='project'`
yo'lining oxirgi bo'lagi, `.project` kengaytmasisiz.

Faqat BO'SH nomlar to'ldiriladi — qo'lda yozilgan yoki fayldan kelgan nomga
tegilmaydi. `downgrade` bo'sh qaytarmaydi: qaysi nom ilgari bo'sh bo'lganini
bilib bo'lmaydi, va bo'sh nom baribir foydali ma'lumot emas.

Revision ID: b8e4a71c92d5
Revises: a7c419e0b3d5
Create Date: 2026-08-26 09:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8e4a71c92d5"
down_revision: str | None = "a7c419e0b3d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE "order" o
           SET project_name = regexp_replace(regexp_replace(f.path, '^.*/', ''), '\\.project$', '', 'i')
        FROM order_file f
        WHERE f.order_id = o.id
          AND f.kind = 'project'
          AND f.is_deleted = false
          AND (o.project_name IS NULL OR o.project_name = '')
        """
    )


def downgrade() -> None:
    # Qaysi nom ilgari bo'sh bo'lganini tiklab bo'lmaydi — qaytarish yo'q.
    pass
