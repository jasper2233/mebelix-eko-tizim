"""soliq moduli ochiq interfeysi — tashqaridan faqat shu fayl import qilinadi."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.soliq import models, services

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


@dataclass
class EsfQisqa:
    id: int
    no: str
    sana: date
    holat: str
    jami: Decimal


async def buyurtma_esflari(db: AsyncSession, order_id: int) -> list[EsfQisqa]:
    """Buyurtmaga yozilgan ESF lar (bekor qilinganlari ham — tarix), eskisi birinchi."""
    q = select(models.SoliqEsf).where(models.SoliqEsf.order_id == order_id).order_by(models.SoliqEsf.id)
    return [EsfQisqa(e.id, e.no, e.sana, e.holat, e.jami) for e in (await db.execute(q)).scalars()]
