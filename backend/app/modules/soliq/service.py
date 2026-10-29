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


async def rejim_boshi(db: AsyncSession) -> date | None:
    """Birinchi soliq rejimi sanasi (rejim yozilmagan bo'lsa None)."""
    return await services.rejim_boshi(db)


async def korxona_tayyor(db: AsyncSession) -> bool:
    """Korxona nomi va STIR i kiritilganmi (ESF va hujjatlar uchun)."""
    k = await services.korxona(db)
    return bool(k.nomi.strip()) and len(k.stir) == 9
