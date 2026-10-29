"""kassa moduli ochiq interfeysi — tashqaridan faqat shu fayl import qilinadi."""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order
from app.modules.kassa import services


async def jami_tolangan(db: AsyncSession, order: Order) -> Decimal:
    """Buyurtma bo'yicha to'langan: kassa orderlari + kassagacha qo'lda yozilgan (rezerv chegarasi shundan)."""
    return await services.jami_tolangan(db, order)


async def mijoz_qarzlari(db: AsyncSession, client_id: int) -> list[tuple[Order, Decimal]]:
    """Mijozning to'lanmagan buyurtmalari (eng eskisi birinchi) va har birida qolgan summa."""
    return await services.mijoz_qarzlari(db, client_id)


async def tolangan(db: AsyncSession, order_ids: list[int]) -> dict[int, Decimal]:
    """Buyurtmalar bo'yicha faqat kassadan to'langan (qaytarish va storno ayirilgan)."""
    return await services.tolangan(db, order_ids)
