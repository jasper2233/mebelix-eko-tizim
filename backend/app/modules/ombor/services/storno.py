"""Storno — tasdiqlangan ombor hujjatini bekor qilish (EKO 2.4, prototip qoidasi).

Tasdiqlangan hujjat o'chirilmaydi va tahrirlanmaydi. Xato bo'lsa — STORNO hujjati (`STR-2026-0001`):
asl hujjat ta'sirini teskari harakatlar bilan qaytaradi, asl hujjat `storno` holatiga o'tadi va
ikkalasi bir-biriga havola qiladi. Jurnalda ikkala yo'nalish ham qoladi.

- Kirim stornosi: shu kirim partiyalari TEGILMAGAN bo'lishi shart (sotilmagan, sarflanmagan), barkodli
  birliklari omborda butun turishi va material boshqa buyurtmaga band bo'lmasligi kerak — aks holda
  rad etiladi (o'rniga qaytarish chiqimi qilinadi).
- Chiqim / sexga kirim stornosi: material omborga qaytadi, asl FIFO tannarxi bilan yangi partiya
  ochiladi; barkodli material yorliqsiz qaytadi — kartochkada qayta yorliqlanadi.
- Inventarizatsiya storno qilinmaydi: yangi inventarizatsiya o'tkaziladi.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ombor.models import CatalogItem, MaterialBirlik, StockDoc, StockDocLine, StockLot, StockMovement
from app.modules.ombor.models.birlik import OMBOR, TUGADI
from app.modules.ombor.services import rezerv
from app.modules.ombor.services.stock import KIND_NAME, DocError, _so_m, add_lot, fmt, next_no

STORNO = "storno"


async def storno(db: AsyncSession, doc: StockDoc, user_id: int | None, sabab: str) -> StockDoc:
    if doc.status != "confirmed":
        raise DocError([f"{doc.no}: faqat tasdiqlangan hujjat storno qilinadi"])
    if doc.kind not in ("kirim", "chiqim", "sex"):
        raise DocError([f"{doc.no}: {KIND_NAME.get(doc.kind, doc.kind)} storno qilinmaydi"])
    if not sabab.strip():
        raise DocError(["Storno sababini yozing"])
    lines = list(
        (
            await db.execute(select(StockDocLine).where(StockDocLine.doc_id == doc.id).order_by(StockDocLine.line_no))
        ).scalars()
    )
    ids = sorted({ln.item_id for ln in lines if ln.item_id is not None})
    items = {
        i.id: i
        for i in (
            await db.execute(
                select(CatalogItem).where(CatalogItem.id.in_(ids)).order_by(CatalogItem.id).with_for_update()
            )
        ).scalars()
    }
    is_k = doc.kind == "kirim"
    errors: list[str] = []
    lots: list[StockLot] = []
    units: list[MaterialBirlik] = []
    if is_k:
        lots = list((await db.execute(select(StockLot).where(StockLot.doc_id == doc.id).with_for_update())).scalars())
        for lot in lots:
            if lot.qty_left != lot.qty:
                errors.append(
                    f"«{items[lot.item_id].name}»: shu kirimdan {fmt(lot.qty - lot.qty_left)} allaqachon "
                    "sotilgan yoki sarflangan — storno o'rniga qaytarish chiqimini qiling"
                )
        units = list(
            (
                await db.execute(select(MaterialBirlik).where(MaterialBirlik.doc_id == doc.id).with_for_update())
            ).scalars()
        )
        for u in units:
            if u.joy != OMBOR or u.qoldiq != u.hajm:
                errors.append(f"{u.barkod}: birlik omborda butun emas (sexga berilgan yoki ishlatilgan)")
        need: dict[int, Decimal] = {}
        for ln in lines:
            if ln.item_id in items and items[ln.item_id].catalog != "X":
                need[ln.item_id] = need.get(ln.item_id, Decimal(0)) + ln.qty
        band = await rezerv.reserved_qty(db, need)
        for iid, q in need.items():
            ci = items[iid]
            if ci.quantity - band.get(iid, Decimal(0)) < q:
                errors.append(f"«{ci.name}»: bu material buyurtmalarga band — avval rezervni bo'shating")
    if errors:
        raise DocError(errors)

    now = datetime.now(UTC)
    st = StockDoc(
        no=await next_no(db, STORNO, now.date().year),
        kind=STORNO,
        status="confirmed",
        doc_date=now.date(),
        head={"asl": doc.no, "asl_id": str(doc.id), "sabab": sabab.strip()[:200]},
        created_by_id=user_id,
        confirmed_at=now,
        confirmed_by_id=user_id,
    )
    db.add(st)
    await db.flush()
    total = Decimal(0)
    lot_cost = {lot.item_id: lot.unit_cost for lot in lots}
    for n, ln in enumerate(lines, start=1):
        it = items.get(ln.item_id) if ln.item_id is not None else None
        if it is None or it.catalog == "X":
            continue
        if is_k:
            delta = -ln.qty
            amount = _so_m(ln.qty * lot_cost.get(it.id, Decimal(0)))
        else:
            delta = ln.qty
            unit_cost = (ln.cost or Decimal(0)) / ln.qty if ln.qty else Decimal(0)
            add_lot(db, it, ln.qty, _so_m(unit_cost), now.date(), st.no, st.id)
            amount = _so_m(ln.cost or Decimal(0))
        it.quantity += delta
        total += amount
        db.add(StockDocLine(doc_id=st.id, line_no=n, item_id=it.id, name=ln.name, qty=ln.qty, cost=amount))
        db.add(
            StockMovement(
                item_id=it.id,
                doc_id=st.id,
                kind=STORNO,
                qty=delta,
                balance=it.quantity,
                amount=amount,
                note=f"Storno · {doc.no} · {sabab.strip()}"[:200],
                user_id=user_id,
            )
        )
    for lot in lots:
        lot.qty_left = Decimal(0)
    for u in units:
        u.qoldiq = Decimal(0)
        u.joy = TUGADI
    st.total = total
    doc.status = STORNO
    doc.head = {**doc.head, "storno": st.no}
    await db.flush()
    if not is_k:
        await rezerv.recover_shortages(db, items)
    return st
