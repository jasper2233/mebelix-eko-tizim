"""moliya moduli ochiq interfeysi — tashqaridan faqat shu fayl import qilinadi."""

from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.moliya import services


async def davr_yopiq(db: AsyncSession, d: date) -> bool:
    """`d` sanasi yopilgan oyga tushadimi (o'sha sana bilan hujjat yozilmaydi)."""
    return await services.davr_yopiq(db, d)


async def debitorlik_net(db: AsyncSession) -> Decimal:
    """Mijozlar qarzi − olingan avans (buyurtma bo'yicha) — buxgalteriya 4010 nazorati uchun."""
    rows = await services.debitorlar(db)
    return sum((d.qarz - d.avans for d in rows), Decimal(0))


async def kreditorlik_net(db: AsyncSession) -> Decimal:
    """Ta'minotchilarga qarz − berilgan avans — buxgalteriya 6010 nazorati uchun."""
    rows = await services.kreditorlar(db)
    return sum((k.qarz - k.avans for k in rows), Decimal(0))


async def pnl_sof(db: AsyncSession, oy: date) -> Decimal:
    """Oyning sof foydasi (Moliya P&L, jonli) — buxgalteriya natijasi bilan solishtirish uchun."""
    return (await services.pnl(db, oy, qotgan=False)).sof
