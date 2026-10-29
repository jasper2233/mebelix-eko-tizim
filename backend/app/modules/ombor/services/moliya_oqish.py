"""Moliya (EKO TZ §8) uchun ombor ma'lumotlari: do'kon sotuvi va FIFO tannarxi, buyurtma tannarxi,
ta'minotchi kirimlari (kreditorlik), ombor qiymati. Faqat o'qiydi."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ombor.models import StockDoc, StockLot, StockMovement


@dataclass
class Hujjat:
    id: int
    no: str
    sana: date
    #: Chiqimda — mijoz, kirimda — yetkazib beruvchi
    kontragent: str
    #: Kirimda to'lov muddati (`head.due`), bo'lmasa None
    muddat: date | None
    #: So'm; storno qatori manfiy
    summa: Decimal
    #: Chiqimning FIFO tannarxi (kirimda 0); storno qatori manfiy
    tannarx: Decimal


def _sana(v: object) -> date | None:
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


async def hujjatlar(db: AsyncSession, kind: str, dan: date | None = None, gacha: date | None = None) -> list[Hujjat]:
    """Tasdiqlangan `kirim`/`chiqim` hujjatlari va ularning stornosi (asl summasining teskarisi, storno sanasida)."""
    q = select(StockDoc).where(StockDoc.status == "confirmed", StockDoc.kind.in_((kind, "storno")))
    if dan is not None:
        q = q.where(StockDoc.doc_date >= dan)
    if gacha is not None:
        q = q.where(StockDoc.doc_date < gacha)
    docs = list((await db.execute(q.order_by(StockDoc.doc_date, StockDoc.id))).scalars())
    asl_ids = [
        int(str(d.head.get("asl_id"))) for d in docs if d.kind == "storno" and str(d.head.get("asl_id", "")).isdigit()
    ]
    asllar = {
        a.id: a
        for a in (await db.execute(select(StockDoc).where(StockDoc.id.in_(asl_ids), StockDoc.kind == kind))).scalars()
    }
    key = "supplier" if kind == "kirim" else "client"
    out = []
    for d in docs:
        if d.kind == kind:
            out.append(
                Hujjat(
                    d.id,
                    d.no,
                    d.doc_date,
                    str(d.head.get(key) or ""),
                    _sana(d.head.get("due")),
                    d.total,
                    d.cogs or Decimal(0),
                )
            )
        elif (a := asllar.get(int(d.head.get("asl_id", 0) or 0))) is not None:
            out.append(
                Hujjat(d.id, d.no, d.doc_date, str(a.head.get(key) or ""), None, -a.total, -(a.cogs or Decimal(0)))
            )
    return out


async def buyurtma_tannarxi(db: AsyncSession, order_ids: list[int]) -> dict[int, Decimal]:
    """Buyurtmaga berilgan material FIFO tannarxi: sarf − omborga qaytgani."""
    if not order_ids:
        return {}
    signed = case((StockMovement.kind == "qaytish", -StockMovement.amount), else_=StockMovement.amount)
    rows = (
        await db.execute(
            select(StockMovement.order_id, func.coalesce(func.sum(signed), 0))
            .where(StockMovement.order_id.in_(order_ids), StockMovement.kind.in_(("sarf", "qaytish")))
            .group_by(StockMovement.order_id)
        )
    ).all()
    return {oid: Decimal(s) for oid, s in rows if oid is not None}


async def ombor_qiymati(db: AsyncSession) -> Decimal:
    """Qolgan partiyalar tannarxda."""
    return Decimal(await db.scalar(select(func.coalesce(func.sum(StockLot.qty_left * StockLot.unit_cost), 0))) or 0)


async def qoralamalar(db: AsyncSession, dan: date, gacha: date) -> list[str]:
    """Shu oraliqdagi tasdiqlanmagan hujjatlar raqami (davr yopishdan oldin)."""
    return list(
        (
            await db.execute(
                select(StockDoc.no).where(
                    StockDoc.status == "draft", StockDoc.doc_date >= dan, StockDoc.doc_date < gacha
                )
            )
        ).scalars()
    )
