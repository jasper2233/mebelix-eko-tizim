"""Mahsulotlar ombori 2-bosqich — hujjatlar, FIFO, tasdiqlash qoidalari (docs/14 §9).

HAQIQIY route handlerlari HAQIQIY Postgres ustida, `scripts/catalog.csv` + `ombor_seed.py` yuklangan
katalog bilan. Kutilgan raqamlar QO'LDA hisoblangan (dizayndagi `confirmDoc` / `consume` / `lotsOf`):

    F-RC-001-01: boshlang'ich 107 dona × 3 660 (xarid), Ruchkalar ustamasi 40%
    1) sotuv 10 × 5 100 − 1 000 chegirma = 50 000; tannarx 10 × 3 660 = 36 600; qoldiq 97
    2) kirim 20 × $0.30, kurs 12 800 → partiya 3 840; xarid 3 840, sotuv 3 840 × 1.4 = 5 376 → 5 400;
       qoldiq 117; jami 76 800
    3) sotuv 100: FIFO 97 × 3 660 + 3 × 3 840 = 366 540; qoldiq 17
    4) sotuv 50 > 17 — rad, hech narsa o'zgarmaydi

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . <test.env> && set +a \\
      && uv run python ../scripts/oracles/ombor_hujjat_oracle.py
"""

import asyncio
import types
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select, text

from app.api.routes.catalog import update_catalog_item, update_warehouse_pricing
from app.api.routes.stock import (
    confirm_stock_doc,
    delete_stock_doc,
    read_stock_docs,
    read_stock_item_history,
    save_stock_doc,
)
from app.core.db import local_session
from app.models import CatalogItem, StockLot, StockMovement
from app.schemas.catalog import CatalogItemUpdate, WarehousePricing
from app.schemas.stock import DocIn, DocLineIn

D = Decimal
natija: list[tuple[str, object, object]] = []
user = types.SimpleNamespace(id=None)
req = types.SimpleNamespace(headers={}, client=types.SimpleNamespace(host="127.0.0.1"))
BUGUN = date(2026, 10, 16)


async def main() -> None:
    async with local_session() as db:
        for t in ("stock_movement", "stock_lot", "stock_doc_line", "stock_doc"):
            await db.execute(text(f"TRUNCATE {t} RESTART IDENTITY CASCADE"))
        await db.commit()
        await update_warehouse_pricing(  # type: ignore[arg-type]
            db, user, WarehousePricing(usd_rate=D(12800), markup_groups={"F-RC": D(40)}), req
        )

        async def item(code: str) -> CatalogItem:
            it = await db.scalar(select(CatalogItem).where(CatalogItem.code == code))
            assert it is not None
            await db.refresh(it)
            return it

        r = await item("F-RC-001-01")
        await update_catalog_item(db, user, req, r.id, CatalogItemUpdate(purchase_price=D(3660), quantity=D(107)))  # type: ignore[arg-type]
        # boshlang'ich qoldiq qo'lda berilgan — tozalab, «partiyasiz qoldiq» holatini yaratamiz
        await db.execute(text("TRUNCATE stock_movement, stock_lot RESTART IDENTITY CASCADE"))
        await db.commit()
        r = await item("F-RC-001-01")
        xz = await item("X-PR-001-01")
        # Oddiy qiymatlar: endpoint rad etganda rollback qiladi va ORM obyektlari eskiradi
        RID, RN, XID, XN = r.id, r.name, xz.id, xz.name

        h = await read_stock_item_history(db, user, RID)  # type: ignore[arg-type]
        natija.append(("partiyasiz qoldiq kartochkada «Boshlang'ich» 107 × 3 660",
                       [(x.source, x.qty_left, x.unit_cost) for x in h.lots], [("Boshlang'ich", D(107), D(3660))]))

        # --- 1. Qoralama qoldiqqa ta'sir qilmaydi
        sale = DocIn(kind="chiqim", doc_date=BUGUN, head={"client": "Jahongir Rustamov", "seller": "Jahongir Abdullayev"},
                     lines=[DocLineIn(item_id=RID, name=RN, qty=D(10), price=D(5100), discount=D(1000)),
                            DocLineIn(item_id=XID, name=XN, qty=D(2), price=D(3000))])
        d1 = await save_stock_doc(db, user, sale)  # type: ignore[arg-type]
        natija.append(("qoralama: raqam CHQ-2026-0001, qoldiq o'zgarmadi", (d1.no, d1.status, (await item("F-RC-001-01")).quantity), ("CHQ-2026-0001", "draft", D(107))))

        # --- 2. Tasdiq: summa, FIFO tannarx, qoldiq, harakat; xizmat summaga kiradi, omborga emas
        c1 = await confirm_stock_doc(db, user, sale.model_copy(update={"id": d1.id}), req)  # type: ignore[arg-type]
        natija.append(("sotuv: jami 50 000 + xizmat 6 000, tannarx 36 600", (c1.total, c1.cogs), (D(56000), D(36600))))
        natija.append(("qoldiq 97, xizmatda harakat yo'q", ((await item("F-RC-001-01")).quantity, await db.scalar(select(StockMovement.id).where(StockMovement.item_id == XID))), (D(97), None)))

        # --- 3. Kirim: partiya, xarid va ustamali sotuv yangilanadi
        kir = DocIn(kind="kirim", doc_date=BUGUN, head={"supplier": "Ningbo Haitian", "rate": "12 800"},
                    lines=[DocLineIn(item_id=RID, name=RN, qty=D(20), price=D("0.30"))])
        k1 = await confirm_stock_doc(db, user, kir, req)  # type: ignore[arg-type]
        x = await item("F-RC-001-01")
        natija.append(("kirim KIR-2026-0001: jami 76 800", (k1.no, k1.total), ("KIR-2026-0001", D(76800))))
        natija.append(("xarid 3 840 ($0.30), sotuv 5 400 (40%), qoldiq 117",
                       (x.purchase_price, x.purchase_usd, x.sale_price, x.quantity), (D(3840), D("0.30"), D(5400), D(117))))

        # --- 4. FIFO: eski partiya avval
        s2 = await confirm_stock_doc(db, user, DocIn(kind="chiqim", doc_date=BUGUN, head={"client": "Mijoz 2"},  # type: ignore[arg-type]
                                     lines=[DocLineIn(item_id=RID, name=RN, qty=D(100), price=D(5400))]), req)
        natija.append(("FIFO: 97 × 3 660 + 3 × 3 840 = 366 540", s2.cogs, D(366540)))
        h = await read_stock_item_history(db, user, RID)  # type: ignore[arg-type]
        natija.append(("qolgan partiya: 17 × 3 840 (kirimdan)", [(x.source, x.qty_left, x.unit_cost) for x in h.lots], [("KIR-2026-0001", D(17), D(3840))]))
        natija.append(("harakatlar: −10, +20, −100; oxirgi qoldiq 17",
                       ([m.qty for m in reversed(h.moves)], h.moves[0].balance), ([D(-10), D(20), D(-100)], D(17))))

        # --- 5. Rad etishlar
        async def rad(body: DocIn) -> str:
            try:
                await confirm_stock_doc(db, user, body, req)  # type: ignore[arg-type]
                return "qabul qilindi"
            except HTTPException as e:
                return str(e.detail)

        e = await rad(DocIn(kind="chiqim", doc_date=BUGUN, head={"client": "X"}, lines=[DocLineIn(item_id=RID, name=RN, qty=D(50))]))
        natija.append(("qoldiqdan ko'p sotilmaydi", "50 dona kerak, omborda 17 bor" in e, True))
        natija.append(("rad etilganda qoldiq o'zgarmadi", (await item("F-RC-001-01")).quantity, D(17)))
        e = await rad(DocIn(kind="chiqim", doc_date=BUGUN, head={}, lines=[DocLineIn(name="Noma'lum tovar", qty=D(1))]))
        natija.append(("mijozsiz va nomenklaturada yo'q qator", ("Mijoz F.I.Sh. kiritilmagan" in e, "nomenklaturada yo'q" in e), (True, True)))
        e = await rad(DocIn(kind="kirim", doc_date=BUGUN, head={"supplier": "S"}, lines=[DocLineIn(item_id=XID, name=XN, qty=D(1))]))
        natija.append(("xizmat kirim qilinmaydi", "xizmat kirim qilinmaydi" in e, True))
        e = await rad(DocIn(kind="chiqim", doc_date=BUGUN, head={"client": "Y"}, lines=[DocLineIn(item_id=RID, name=RN)]))
        natija.append(("soni kiritilmagan", "soni kiritilmagan" in e, True))
        # bir pozitsiya ikki qatorda: jami bo'yicha tekshiriladi
        e = await rad(DocIn(kind="chiqim", doc_date=BUGUN, head={"client": "Z"},
                            lines=[DocLineIn(item_id=RID, name=RN, qty=D(10)), DocLineIn(item_id=RID, name=RN, qty=D(10))]))
        natija.append(("ikki qator jami 20 > 17 — rad", "20 dona kerak" in e, True))

        # --- 6. Tasdiqlangan hujjat qulflangan
        try:
            await save_stock_doc(db, user, sale.model_copy(update={"id": d1.id}))  # type: ignore[arg-type]
            natija.append(("tasdiqlangan hujjat o'zgarmaydi", "o'zgardi", 409))
        except HTTPException as ex:
            natija.append(("tasdiqlangan hujjat o'zgarmaydi", ex.status_code, 409))
        try:
            await delete_stock_doc(db, user, d1.id)  # type: ignore[arg-type]
            natija.append(("tasdiqlangan hujjat o'chmaydi", "o'chdi", 409))
        except HTTPException as ex:
            natija.append(("tasdiqlangan hujjat o'chmaydi", ex.status_code, 409))
        d3 = await save_stock_doc(db, user, DocIn(kind="chiqim", doc_date=BUGUN, head={"client": "Q"}, lines=[DocLineIn(item_id=RID, name=RN, qty=D(1))]))  # type: ignore[arg-type]
        await delete_stock_doc(db, user, d3.id)  # type: ignore[arg-type]
        docs = await read_stock_docs(db, user)  # type: ignore[arg-type]
        natija.append(("qoralama o'chirildi, ro'yxatda 3 ta tasdiqlangan", sorted(d.no for d in docs), ["CHQ-2026-0001", "CHQ-2026-0002", "KIR-2026-0001"]))

        # --- 7. Qo'lda tuzatish ham partiya va harakat bilan
        await update_catalog_item(db, user, req, RID, CatalogItemUpdate(quantity=D(20)))  # type: ignore[arg-type]
        await update_catalog_item(db, user, req, RID, CatalogItemUpdate(quantity=D(15)))  # type: ignore[arg-type]
        h = await read_stock_item_history(db, user, RID)  # type: ignore[arg-type]
        natija.append(("tuzatish +3 (3 840 da) va −5 (FIFO)", ([m.qty for m in h.moves[:2]], h.moves[0].kind), ([D(-5), D(3)], "tuzatish")))
        left = sum((x.qty_left for x in h.lots), D(0))
        natija.append(("partiyalar yig'indisi = qoldiq", left, (await item("F-RC-001-01")).quantity))
        lots = (await db.execute(select(StockLot).where(StockLot.item_id == RID))).scalars().all()
        natija.append(("boshlang'ich partiya bazaga yozildi (107)", [x.qty for x in lots if x.source == "Boshlang'ich"], [D(107)]))


asyncio.run(main())
xato = sum(1 for _, a, b in natija if a != b)
for nom, a, b in natija:
    print(f"  {'OK ' if a == b else 'XATO'} {nom}: olingan={a} kutilgan={b}")
print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")
