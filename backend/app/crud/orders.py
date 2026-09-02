from datetime import datetime

from sqlalchemy import Integer, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import TASHKENT_TZ
from app.crud.base import BaseCRUD
from app.models import Order


class CRUDOrder(BaseCRUD[Order]):
    async def next_number(self, db: AsyncSession) -> str:
        """B-2026-001 style, sequential within the current year (TZ 6.2.2).

        Yil — Asia/Tashkent bo'yicha: UTC yili 1-yanvar 00:00-05:00 mahalliy
        oralig'ida hali o'tgan yilni ko'rsatib, raqamga eski prefiks berardi.

        Suffiks SQLda SON sifatida max qilinadi — satr (leksikografik) max
        999 dan keyin "B-2026-999" > "B-2026-1000" bo'lib raqamlashni sindirardi.
        """
        year = datetime.now(TASHKENT_TZ).year
        prefix = f"B-{year}-"
        max_seq: int | None = (
            await db.execute(
                select(func.max(func.cast(func.split_part(Order.number, "-", 3), Integer))).where(
                    Order.number.like(f"{prefix}%")
                )
            )
        ).scalar_one_or_none()
        return f"{prefix}{(max_seq or 0) + 1:03d}"


crud_orders = CRUDOrder(Order)
