"""moliya moduli ochiq interfeysi — tashqaridan faqat shu fayl import qilinadi."""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.moliya import services


async def davr_yopiq(db: AsyncSession, d: date) -> bool:
    """`d` sanasi yopilgan oyga tushadimi (o'sha sana bilan hujjat yozilmaydi)."""
    return await services.davr_yopiq(db, d)
