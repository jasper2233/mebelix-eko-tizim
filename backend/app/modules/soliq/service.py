"""soliq moduli ochiq interfeysi — tashqaridan faqat shu fayl import qilinadi."""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.soliq import services

OySoliq = services.OySoliq
Ishlov = services.Ishlov


async def oy_soliq(db: AsyncSession, oy: date) -> services.OySoliq:
    """Oyning soliq yuki: QQS rejimida sotuvdagi QQS − xarid QQS, aylanma rejimida aylanma × stavka (P&L uchun)."""
    return await services.oy_soliq(db, oy)


async def ishlov(db: AsyncSession) -> services.Ishlov:
    """Fon ishi: ESF navbatini yuborish, holat so'rash, kiruvchilarni olish."""
    return await services.ishlov(db)
