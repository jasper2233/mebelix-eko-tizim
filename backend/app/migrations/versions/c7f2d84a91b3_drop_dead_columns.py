"""O'lik (faqat yoziladigan, hech qayerda o'qilmaydigan) ustunlarni olib tashlash.

2026-08-05 to'liq audit: quyidagi ustunlarga hech bir so'rov, biznes-logika yoki
frontend murojaat qilmaydi — faqat ingest/seed yozardi yoki umuman yozilmasdi:
  part.saw_length/saw_width (jl/jw — parser l/dl/cl zanjirida baribir ishlatadi),
  product.import_source, "order".project_generation (upload yangi parse'dagi
  project.generation'ni ishlatadi), organization profil maydonlari (route/sxema yo'q),
  machine/employee/client anketa maydonlari (formalarda ham yo'q edi).
client_type va project_generation native_enum=False (VARCHAR + CHECK) — ustun bilan
birga CHECK constraint ham avtomatik o'chadi, alohida enum tip qolmaydi.

Revision ID: c7f2d84a91b3
Revises: b3e9a1d76c42
Create Date: 2026-08-05
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c7f2d84a91b3"
down_revision = "b3e9a1d76c42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("part", "saw_length")
    op.drop_column("part", "saw_width")
    op.drop_column("product", "import_source")
    op.drop_column("order", "project_generation")
    op.drop_column("organization", "logo_url")
    op.drop_column("organization", "address")
    op.drop_column("organization", "phones")
    op.drop_column("organization", "currency")
    op.drop_column("organization", "timezone")
    op.drop_column("organization", "settings")
    op.drop_column("machine", "mac_address")
    op.drop_column("machine", "icon_url")
    op.drop_column("machine", "serial_number")
    op.drop_column("machine", "installed_date")
    op.drop_column("employee", "passport_id")
    op.drop_column("employee", "photo_url")
    op.drop_column("employee", "hired_date")
    op.drop_column("client", "client_type")
    op.drop_column("client", "inn")


def downgrade() -> None:
    # Tiplar 1393a241b793 dan aynan ko'chirildi. NOT NULL ustunlarga server_default
    # qo'shildi (model'dagi Python defaultlariga mos) — aks holda bo'sh bo'lmagan
    # jadvalda add_column yiqiladi; qiymatlar baribir hech qayerda o'qilmaydi.
    op.add_column(
        "client",
        sa.Column(
            "client_type",
            sa.Enum("individual", "legal", name="clienttype", native_enum=False, length=30),
            nullable=False,
            server_default="individual",
        ),
    )
    op.add_column("client", sa.Column("inn", sa.String(length=20), nullable=True))
    op.add_column("employee", sa.Column("passport_id", sa.String(length=20), nullable=True))
    op.add_column("employee", sa.Column("photo_url", sa.String(length=500), nullable=True))
    op.add_column("employee", sa.Column("hired_date", sa.Date(), nullable=True))
    op.add_column("machine", sa.Column("mac_address", sa.String(length=17), nullable=True))
    op.add_column("machine", sa.Column("icon_url", sa.String(length=500), nullable=True))
    op.add_column("machine", sa.Column("serial_number", sa.String(length=100), nullable=True))
    op.add_column("machine", sa.Column("installed_date", sa.Date(), nullable=True))
    op.add_column("organization", sa.Column("logo_url", sa.String(length=500), nullable=True))
    op.add_column("organization", sa.Column("address", sa.String(length=255), nullable=True))
    op.add_column(
        "organization",
        sa.Column(
            "phones",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column("organization", sa.Column("currency", sa.String(length=10), nullable=False, server_default="UZS"))
    op.add_column(
        "organization", sa.Column("timezone", sa.String(length=50), nullable=False, server_default="Asia/Tashkent")
    )
    op.add_column(
        "organization",
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "order",
        sa.Column(
            "project_generation",
            sa.Enum("processed", "template", name="projectgeneration", native_enum=False, length=30),
            nullable=True,
        ),
    )
    op.add_column("product", sa.Column("import_source", sa.String(length=50), nullable=True))
    op.add_column("part", sa.Column("saw_width", sa.Float(), nullable=True))
    op.add_column("part", sa.Column("saw_length", sa.Float(), nullable=True))
