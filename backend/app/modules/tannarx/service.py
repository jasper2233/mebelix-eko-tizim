"""tannarx moduli ochiq interfeysi — tashqaridan faqat shu fayl import qilinadi."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tannarx import services
from app.modules.tannarx.models import IshHaqiQator


async def buyurtma_mehnati(db: AsyncSession, order_ids: list[int]) -> dict[int, Decimal]:
    """Buyurtmalarning mehnat (ishbay ish haqi) tannarxi — tasdiqlangan vedomost davrlaridan."""
    return await services.buyurtma_mehnati(db, order_ids)


@dataclass
class Hisoblangan:
    """Tasdiqlangan vedomost qatori — buxgalteriya uchun (D 2010 — K 6710)."""

    vedomost_id: int
    no: str
    sana: date
    hodim: str
    summa: Decimal


async def hisoblangan(db: AsyncSession) -> list[Hisoblangan]:
    out: list[Hisoblangan] = []
    vlar = await services.tasdiqlanganlar(db)
    if not vlar:
        return out
    qatorlar = list(
        (await db.execute(select(IshHaqiQator).where(IshHaqiQator.vedomost_id.in_([v.id for v in vlar])))).scalars()
    )
    nom = await services.hodim_nomlari(db, {q.employee_id for q in qatorlar})
    by = {v.id: v for v in vlar}
    for q in qatorlar:
        v = by[q.vedomost_id]
        out.append(Hisoblangan(v.id, v.no, v.gacha, nom.get(q.employee_id, f"hodim {q.employee_id}"), q.summa))
    return out
