"""kassa moduli ochiq interfeysi — tashqaridan faqat shu fayl import qilinadi."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order
from app.modules.kassa import models, services


async def jami_tolangan(db: AsyncSession, order: Order) -> Decimal:
    """Buyurtma bo'yicha to'langan: kassa orderlari + kassagacha qo'lda yozilgan (rezerv chegarasi shundan)."""
    return await services.jami_tolangan(db, order)


async def mijoz_qarzlari(db: AsyncSession, client_id: int) -> list[tuple[Order, Decimal]]:
    """Mijozning to'lanmagan buyurtmalari (eng eskisi birinchi) va har birida qolgan summa."""
    return await services.mijoz_qarzlari(db, client_id)


async def tolangan(db: AsyncSession, order_ids: list[int]) -> dict[int, Decimal]:
    """Buyurtmalar bo'yicha faqat kassadan to'langan (qaytarish va storno ayirilgan)."""
    return await services.tolangan(db, order_ids)


# ── Moliya (EKO TZ §8) uchun: o'qish, moddalar, hisob sozlamasi, storno ──
KassaXato = services.KassaXato
OrderQator = services.OrderQator
KassaModda = models.KassaModda
KassaHisob = models.KassaHisob


async def orderlar_davr(
    db: AsyncSession, dan: datetime | None = None, gacha: datetime | None = None, client_id: int | None = None
) -> list[services.OrderQator]:
    """[dan, gacha) oralig'idagi orderlar (storno ham), eskisi birinchi."""
    return await services.orderlar_davr(db, dan, gacha, client_id)


async def hisoblar(db: AsyncSession) -> list[tuple[models.KassaHisob, Decimal]]:
    """Faol hisoblar va joriy qoldig'i."""
    out = []
    for h in (await db.execute(select(models.KassaHisob).where(models.KassaHisob.faol == True))).scalars():  # noqa: E712
        out.append((h, await services.qoldiq(db, h)))
    return sorted(out, key=lambda x: x[0].id)


async def ochiq_smenalar(db: AsyncSession) -> list[models.KassaSmena]:
    return await services.ochiq_smenalar(db)


async def moddalar(db: AsyncSession, faqat_faol: bool = True) -> list[models.KassaModda]:
    return await services.moddalar(db, faqat_faol)


async def modda_saqla(
    db: AsyncSession, nom: str, oylik_limit: Decimal | None, faol: bool, modda_id: int | None = None
) -> models.KassaModda:
    return await services.modda_saqla(db, nom, oylik_limit, faol, modda_id)


async def hisob_sozla(
    db: AsyncSession, kod: str, boshlangich: Decimal | None, komissiya_foiz: Decimal | None
) -> models.KassaHisob:
    return await services.hisob_sozla(db, kod, boshlangich, komissiya_foiz)


async def storno(db: AsyncSession, kassa_order_id: int, user_id: int | None, sabab: str) -> services.Natija:
    """Xato orderni teskari order bilan bekor qilish (ikki kalit)."""
    return await services.storno(db, kassa_order_id, user_id, sabab)


# ── Ishga tushirish: ochilish qoldiqlari va qo'lda avans qulfi ──
KassaOchilish = models.KassaOchilish


async def boshlangan(db: AsyncSession) -> bool:
    """Kassada order yozilganmi (shundan keyin buyurtmadagi qo'lda avans yopiladi)."""
    return await services.boshlangan(db)


async def ochilish_qoldigi(db: AsyncSession, client_id: int) -> Decimal:
    """Mijozning ochilish qarzidan to'lanmagani (manfiy — avans)."""
    return await services.ochilish_qoldigi(db, client_id)


async def ochilishlar(db: AsyncSession) -> list[models.KassaOchilish]:
    return await services.ochilishlar(db)


async def ochilish_tolangan(db: AsyncSession) -> dict[int, Decimal]:
    return await services.ochilish_tolangan(db)


async def ochilish_qosh(
    db: AsyncSession,
    tur: str,
    summa: Decimal,
    sana: date,
    user_id: int | None,
    *,
    client_id: int | None = None,
    kontragent: str = "",
    izoh: str = "",
) -> models.KassaOchilish:
    return await services.ochilish_qosh(
        db, tur, summa, sana, user_id, client_id=client_id, kontragent=kontragent, izoh=izoh
    )


async def pnl_emas_moddalar(db: AsyncSession) -> set[str]:
    """P&L xarajati bo'lmagan moddalar (ishbay ish haqi to'lovi — 6710 ni yopadi)."""
    rows = await db.execute(select(models.KassaModda.nom).where(models.KassaModda.pnl_emas == True))  # noqa: E712
    return set(rows.scalars())
