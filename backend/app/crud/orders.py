from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import BaseCRUD
from app.models import Order


class CRUDOrder(BaseCRUD[Order]):
    async def next_number(self, db: AsyncSession) -> str:
        """B-2026-001 style, sequential within the current year (TZ 6.2.2)."""
        year = datetime.now(UTC).year
        prefix = f"B-{year}-"
        max_number: str | None = (
            await db.execute(select(func.max(Order.number)).where(Order.number.like(f"{prefix}%")))
        ).scalar_one_or_none()
        seq = int(max_number.removeprefix(prefix)) + 1 if max_number else 1
        return f"{prefix}{seq:03d}"


crud_orders = CRUDOrder(Order)
