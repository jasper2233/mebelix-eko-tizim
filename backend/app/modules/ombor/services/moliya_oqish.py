"""Moliya (EKO TZ §8) uchun ombor ma'lumotlari: do'kon sotuvi va FIFO tannarxi, buyurtma tannarxi,
ta'minotchi kirimlari (kreditorlik), ombor qiymati. Faqat o'qiydi."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ombor.models import CatalogItem, StockDoc, StockDocLine, StockLot, StockMovement


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
    """Qolgan partiyalar tannarxda + partiyasi hali yo'q qoldiq xarid narxida (ombor hisoboti uni «Boshlang'ich»
    partiya deb ko'rsatadi: birinchi harakatda shu narx bilan partiya ochiladi — `stock._ensure_initial_lot`)."""
    lots = Decimal(await db.scalar(select(func.coalesce(func.sum(StockLot.qty_left * StockLot.unit_cost), 0))) or 0)
    return lots + await _partiyasiz(db)


async def _partiyasiz(db: AsyncSession) -> Decimal:
    lotli = select(StockLot.item_id)
    return Decimal(
        await db.scalar(
            select(
                func.coalesce(func.sum(CatalogItem.quantity * func.coalesce(CatalogItem.purchase_price, 0)), 0)
            ).where(CatalogItem.quantity > 0, CatalogItem.id.not_in(lotli))
        )
        or 0
    )


@dataclass
class Harakat:
    """Buxgalteriya uchun qiymatli harakat: ombor qiymatiga ta'siri `qiymat` (ishorali)."""

    id: int
    kind: str
    sana: datetime
    qiymat: Decimal
    order_id: int | None
    doc_id: int | None
    #: Hujjat turi; storno uchun — asl hujjat turi (`kirim` / `chiqim` / `sex`)
    doc_kind: str | None
    #: Kirimda — yetkazib beruvchi
    kontragent: str
    note: str


async def harakatlar(db: AsyncSession) -> list[Harakat]:
    """Qiymatli harakatlar (`sexga`, `boshlangich` — qiymatsiz, kirmaydi)."""
    docs = {d.id: d for d in (await db.execute(select(StockDoc).where(StockDoc.status == "confirmed"))).scalars()}
    out = []
    rows = (
        await db.execute(
            select(StockMovement)
            .where(StockMovement.amount.is_not(None), StockMovement.kind.not_in(("sexga", "boshlangich")))
            .order_by(StockMovement.id)
        )
    ).scalars()
    for m in rows:
        d = docs.get(m.doc_id or 0)
        kind = d.kind if d else None
        if d is not None and d.kind == "storno":
            asl = docs.get(int(str(d.head.get("asl_id", 0)) or 0))
            kind = asl.kind if asl else None
            d = asl or d
        sign = Decimal(1) if m.qty > 0 else Decimal(-1)
        out.append(
            Harakat(
                m.id,
                m.kind,
                m.created_at,
                sign * abs(m.amount or Decimal(0)),
                m.order_id,
                m.doc_id,
                kind,
                str((d.head.get("supplier") if d else "") or ""),
                m.note,
            )
        )
    return out


async def boshlangich_qiymat(db: AsyncSession) -> Decimal:
    """Tizimga o'tishdagi ombor qiymati: «Boshlang'ich» partiyalar (dastlabki miqdor) + partiyasiz qoldiq."""
    lots = Decimal(
        await db.scalar(
            select(func.coalesce(func.sum(StockLot.qty * StockLot.unit_cost), 0)).where(
                StockLot.source == "Boshlang'ich"
            )
        )
        or 0
    )
    return lots + await _partiyasiz(db)


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


# ── Soliq (EKO TZ §9) uchun ──
@dataclass
class Pozitsiya:
    id: int
    code: str
    name: str
    unit: str
    mxik: str | None
    birlik_kod: str | None
    qqs_turi: str


@dataclass
class Qator:
    item_id: int | None
    nom: str
    miqdor: Decimal
    narx: Decimal
    #: Chegirmadan keyingi qator summasi, so'm
    summa: Decimal


async def pozitsiyalar(db: AsyncSession, ids: list[int]) -> dict[int, Pozitsiya]:
    rows = (await db.execute(select(CatalogItem).where(CatalogItem.id.in_(ids)))).scalars()
    return {
        i.id: Pozitsiya(i.id, i.code, i.name, i.unit or "", i.mxik, i.birlik_kod, i.qqs_turi or "standart")
        for i in rows
    }


async def hujjat_qatorlari(db: AsyncSession, doc_id: int) -> tuple[StockDoc | None, list[Qator]]:
    doc = await db.get(StockDoc, doc_id)
    if doc is None:
        return None, []
    lines = (
        await db.execute(select(StockDocLine).where(StockDocLine.doc_id == doc_id).order_by(StockDocLine.line_no))
    ).scalars()
    out = []
    for ln in lines:
        g = (ln.qty * ln.price).quantize(Decimal("0.01"))
        out.append(Qator(ln.item_id, ln.name, ln.qty, ln.price, g - min(ln.discount, g)))
    return doc, out


async def sotuv_qatorlari(db: AsyncSession, dan: date, gacha: date) -> list[tuple[Decimal, str]]:
    """[dan, gacha) do'kon sotuvi qatorlari: (summa, QQS turi); storno qilingan hujjat qatorlari — manfiy."""
    out: list[tuple[Decimal, str]] = []
    for h in await hujjatlar(db, "chiqim", dan, gacha):
        asl_id = h.id
        if h.summa < 0:  # storno qatori: asl hujjat qatorlari teskari
            st = await db.get(StockDoc, h.id)
            asl_id = int(str(st.head.get("asl_id"))) if st is not None else h.id
        _, qatorlar = await hujjat_qatorlari(db, asl_id)
        poz = await pozitsiyalar(db, [q.item_id for q in qatorlar if q.item_id])
        for q in qatorlar:
            turi = poz[q.item_id].qqs_turi if q.item_id in poz else "standart"
            out.append((q.summa if h.summa >= 0 else -q.summa, turi))
    return out


async def soliq_saqla(
    db: AsyncSession, item_id: int, mxik: str | None, birlik_kod: str | None, qqs_turi: str
) -> CatalogItem | None:
    it = await db.get(CatalogItem, item_id)
    if it is None:
        return None
    it.mxik, it.birlik_kod, it.qqs_turi = mxik, birlik_kod, qqs_turi
    await db.flush()
    return it
