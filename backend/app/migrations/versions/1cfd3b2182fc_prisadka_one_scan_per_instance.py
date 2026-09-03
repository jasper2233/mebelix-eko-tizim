"""prisadka one scan per instance

Ikki yuzli detal (old + orqa `_2` XNC) PRISADKA qadamida per_instance=2 bilan yozilardi —
prisadkachi bitta detalni «0/2» deb ko'rar va bir xil QR'ni ikki marta skanlashi kerak edi.
SCX ikkala yuzni bitta faylga birlashtiradi (Face="6"), stanok bir yurgizishda ishlaydi —
skan ham bitta. Yangi ingest 1 yozadi (`ParsedPart.prisadka_passes`), bu migratsiya mavjud
qadamlarni tushiradi: per_instance=1, total_required=part.count (total_done tegilmaydi —
bir marta skanlangan nusxa shu zahoti tugagan hisoblanadi). Downgrade `xnc_summary.sides=2`
bo'yicha qaytaradi.

Revision ID: 1cfd3b2182fc
Revises: 6a5051b7b420
Create Date: 2026-09-03 07:56:36.972157

"""

from collections.abc import Sequence
from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1cfd3b2182fc"
down_revision: Union[str, None] = "6a5051b7b420"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE part_route pr SET per_instance = 1, total_required = p.count
        FROM part p, post po
        WHERE pr.part_id = p.id AND pr.post_id = po.id AND po.code = 'PRISADKA'
          AND pr.per_instance > 1 AND NOT pr.is_deleted
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE part_route pr SET per_instance = 2, total_required = p.count * 2
        FROM part p, post po
        WHERE pr.part_id = p.id AND pr.post_id = po.id AND po.code = 'PRISADKA'
          AND NOT pr.is_deleted AND (p.xnc_summary->>'sides')::int = 2
        """
    )
