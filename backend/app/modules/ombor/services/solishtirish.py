"""Ombor solishtirishi (EKO 2.4, prototipdagi `reconcile_stock` qoidasi): hisob o'z-o'ziga mosmi.

Tekshiriladi:
1. Qoldiq = jurnal: `catalog_item.quantity` = shu pozitsiya harakatlari yig'indisi.
2. Partiyalar: pozitsiyada partiya bo'lsa — qolgan partiyalar yig'indisi = qoldiq (FIFO tannarxi to'g'ri).
3. Barkodli birliklar (ombor + sex) yig'indisi qoldiqdan oshmaydi.
4. Buyurtmaga berilgan (rezerv `berilgan_qty`) = shu buyurtmaning sarf harakatlari − qaytganlari.
5. Manfiy qiymatlar (baza cheklovi «tasdiqlanmagan» qolgan eski qatorlar).

Hech narsani tuzatmaydi — faqat aytadi. Farq bo'lsa sababi topilib, teskari harakat bilan tuzatiladi.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ombor.models import CatalogItem, MaterialBirlik, Rezerv, RezervLine, StockLot, StockMovement
from app.modules.ombor.models.birlik import OMBOR, SEX
from app.modules.ombor.services import rezerv


@dataclass
class Farq:
    tur: str
    kalit: str
    hisobda: Decimal
    kerak: Decimal
    izoh: str


async def solishtir(db: AsyncSession) -> list[Farq]:
    out: list[Farq] = []
    jurnal = (
        select(StockMovement.item_id, func.sum(StockMovement.qty).label("s")).group_by(StockMovement.item_id).subquery()
    )
    for code, q, s in (
        await db.execute(
            select(CatalogItem.code, CatalogItem.quantity, func.coalesce(jurnal.c.s, 0))
            .outerjoin(jurnal, jurnal.c.item_id == CatalogItem.id)
            .where(CatalogItem.catalog != "X", CatalogItem.quantity != func.coalesce(jurnal.c.s, 0))
        )
    ).all():
        out.append(Farq("jurnal", code, q, Decimal(s), "qoldiq harakatlar yig'indisiga teng emas"))

    lots = (
        select(StockLot.item_id, func.sum(StockLot.qty_left).label("s"))
        .where(StockLot.is_deleted == False)  # noqa: E712
        .group_by(StockLot.item_id)
        .subquery()
    )
    for code, q, s in (
        await db.execute(
            select(CatalogItem.code, CatalogItem.quantity, lots.c.s)
            .join(lots, lots.c.item_id == CatalogItem.id)
            .where(CatalogItem.quantity != lots.c.s)
        )
    ).all():
        out.append(Farq("partiya", code, q, Decimal(s), "qolgan partiyalar qoldiqqa teng emas (FIFO tannarxi)"))

    units = (
        select(MaterialBirlik.item_id, func.sum(MaterialBirlik.qoldiq).label("s"))
        .where(MaterialBirlik.joy.in_((OMBOR, SEX)), MaterialBirlik.is_deleted == False)  # noqa: E712
        .group_by(MaterialBirlik.item_id)
        .subquery()
    )
    for code, q, s in (
        await db.execute(
            select(CatalogItem.code, CatalogItem.quantity, units.c.s)
            .join(units, units.c.item_id == CatalogItem.id)
            .where(units.c.s > CatalogItem.quantity)
        )
    ).all():
        out.append(Farq("barkod", code, q, Decimal(s), "barkodli birliklar qoldiqdan ko'p"))

    # Buyurtmaning oxirgi (bekor bo'lmagan) rezervi: berilgani qayta qurishda shunga ko'chadi
    oxirgi = (
        select(Rezerv.order_id, func.max(Rezerv.id).label("rid"))
        .where(Rezerv.holat != rezerv.BEKOR, Rezerv.is_deleted == False)  # noqa: E712
        .group_by(Rezerv.order_id)
        .subquery()
    )
    berilgan = (
        select(oxirgi.c.order_id, RezervLine.item_id, func.sum(RezervLine.berilgan_qty).label("b"))
        .join(RezervLine, RezervLine.rezerv_id == oxirgi.c.rid)
        .where(RezervLine.item_id.is_not(None), RezervLine.is_deleted == False)  # noqa: E712
        .group_by(oxirgi.c.order_id, RezervLine.item_id)
        .subquery()
    )
    sarf = (
        select(StockMovement.order_id, StockMovement.item_id, (-func.sum(StockMovement.qty)).label("s"))
        .where(StockMovement.kind.in_(("sarf", "qaytish")), StockMovement.order_id.is_not(None))
        .group_by(StockMovement.order_id, StockMovement.item_id)
        .subquery()
    )
    for oid, iid, b, s in (
        await db.execute(
            select(
                func.coalesce(berilgan.c.order_id, sarf.c.order_id),
                func.coalesce(berilgan.c.item_id, sarf.c.item_id),
                func.coalesce(berilgan.c.b, 0),
                func.coalesce(sarf.c.s, 0),
            )
            .select_from(berilgan)
            .join(
                sarf,
                (sarf.c.order_id == berilgan.c.order_id) & (sarf.c.item_id == berilgan.c.item_id),
                full=True,
            )
            .where(func.coalesce(berilgan.c.b, 0) != func.coalesce(sarf.c.s, 0))
        )
    ).all():
        out.append(Farq("sarf", f"buyurtma {oid} / pozitsiya {iid}", Decimal(b), Decimal(s), "berilgan ≠ sarf jurnali"))

    for table, cond in (
        ("catalog_item", "quantity < 0"),
        ("stock_lot", "qty_left < 0 OR qty_left > qty"),
        ("material_birlik", "qoldiq < 0 OR qoldiq > hajm"),
        ("rezerv_line", "qoplangan_qty < 0 OR berilgan_qty < 0"),
    ):
        n = int(await db.scalar(text(f"SELECT count(*) FROM {table} WHERE {cond}")) or 0)  # noqa: S608
        if n:
            out.append(Farq("manfiy", table, Decimal(n), Decimal(0), f"{n} ta qator: {cond}"))
    return out
