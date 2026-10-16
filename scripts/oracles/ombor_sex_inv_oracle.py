"""Mahsulotlar ombori 3-bosqich — Sex xo'jaligi va Inventarizatsiya (docs/14 §10).

HAQIQIY route handlerlari HAQIQIY Postgres ustida (`catalog_import --apply` + `ombor_seed --apply`
yuklangan katalog). Kutilgan raqamlar QO'LDA (dizayndagi `confirmDoc` sex shoxi va `confirmInv`):

    S-ZP «Pila diski» yangi: kirim 4 dona × $35, kurs 12 800 → partiya 448 000
    sexga 1 dona → tannarx 448 000 = hujjat summasi; qoldiq 3
    sotuvga S — rad («sex xo'jaligiga tegishli — sotilmaydi»); sexga xizmat — rad; usta yo'q — rad
    inventarizatsiya: Pila 3 → 5 (+2 × 448 000 = 896 000), F-RC-001-01 107 → 100 (−7 × 3 660 = −25 620)
    → INV-2026-0001, jami 870 380; qoldiqlar 5 va 100; partiyalar yig'indisi = qoldiq

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . <test.env> && set +a \\
      && uv run python ../scripts/oracles/ombor_sex_inv_oracle.py
"""

import asyncio
import types
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select, text

from app.api.routes.catalog import create_catalog_item, update_catalog_item
from app.api.routes.stock import (
    confirm_stock_doc,
    confirm_stock_inventory,
    read_stock_item_history,
    read_stock_sex_log,
)
from app.core.db import local_session
from app.models import CatalogItem
from app.schemas.catalog import CatalogItemCreate, CatalogItemUpdate
from app.schemas.stock import DocIn, DocLineIn, InventoryCount, InventoryIn

D = Decimal
natija: list[tuple[str, object, object]] = []
user = types.SimpleNamespace(id=None)
req = types.SimpleNamespace(headers={}, client=types.SimpleNamespace(host="127.0.0.1"))
BUGUN = date(2026, 10, 16)


async def main() -> None:
    async with local_session() as db:
        for t in ("stock_movement", "stock_lot", "stock_doc_line", "stock_doc"):
            await db.execute(text(f"TRUNCATE {t} RESTART IDENTITY CASCADE"))
        await db.execute(text("DELETE FROM catalog_item WHERE catalog = 'S'"))
        await db.commit()

        async def qty(iid: int) -> Decimal:
            it = await db.get(CatalogItem, iid)
            assert it is not None
            await db.refresh(it)
            return it.quantity

        async def rad(fn, *a) -> str:  # noqa: ANN001
            try:
                await fn(db, user, *a, req)
                return "qabul qilindi"
            except HTTPException as e:
                return str(e.detail)

        # --- 1. Sex xo'jaligi guruhi bo'sh — birinchi pozitsiya nomi koddan
        pila = await create_catalog_item(  # type: ignore[arg-type]
            db, user, CatalogItemCreate(catalog="S", group_code="ZP", name="Pila diski 300×3,2×30 Z96", unit="dona"), req
        )
        natija.append(("S-ZP birinchi pozitsiya: kod va guruh nomi", (pila.code, pila.group_name), ("S-ZP-001-01", "Uskuna zapchastlari")))
        PID = pila.id
        r = await db.scalar(select(CatalogItem).where(CatalogItem.code == "F-RC-001-01"))
        xz = await db.scalar(select(CatalogItem).where(CatalogItem.code == "X-PR-001-01"))
        assert r and xz
        RID, RN, XID, XN = r.id, r.name, xz.id, xz.name
        await update_catalog_item(db, user, req, RID, CatalogItemUpdate(purchase_price=D(3660), quantity=D(107)))  # type: ignore[arg-type]
        await db.execute(text("TRUNCATE stock_movement, stock_lot RESTART IDENTITY CASCADE"))
        await db.commit()

        # --- 2. Kirim: S kirim qilinadi
        await confirm_stock_doc(db, user, DocIn(kind="kirim", doc_date=BUGUN, head={"supplier": "Asbob savdo", "rate": "12800"},  # type: ignore[arg-type]
                                lines=[DocLineIn(item_id=PID, name="Pila", qty=D(4), price=D(35))]), req)
        natija.append(("S kirim: qoldiq 4", await qty(PID), D(4)))

        # --- 3. Sexga kirim: FIFO tannarx = summa
        s1 = await confirm_stock_doc(db, user, DocIn(kind="sex", doc_date=BUGUN,  # type: ignore[arg-type]
                                     head={"taker": "Bobur usta", "equip": "Raspil stanogi", "giver": "Qudrat"},
                                     lines=[DocLineIn(item_id=PID, name="Pila", qty=D(1))]), req)
        natija.append(("SEX-2026-0001: summa = tannarx 448 000", (s1.no, s1.total, s1.cogs), ("SEX-2026-0001", D(448000), D(448000))))
        natija.append(("sexdan keyin qoldiq 3", await qty(PID), D(3)))
        log = await read_stock_sex_log(db, user)  # type: ignore[arg-type]
        natija.append(("Sex sarfi jurnalida: kim, uskuna, summa",
                       [(x.taker, x.equip, x.code, x.qty, x.amount) for x in log],
                       [("Bobur usta", "Raspil stanogi", "S-ZP-001-01", D(1), D(448000))]))

        # --- 4. Rad etishlar
        e = await rad(confirm_stock_doc, DocIn(kind="chiqim", doc_date=BUGUN, head={"client": "M"}, lines=[DocLineIn(item_id=PID, name="Pila", qty=D(1))]))
        natija.append(("sex mahsuloti sotilmaydi", "sex xo'jaligiga tegishli — sotilmaydi" in e, True))
        e = await rad(confirm_stock_doc, DocIn(kind="sex", doc_date=BUGUN, head={"taker": "U"}, lines=[DocLineIn(item_id=XID, name=XN, qty=D(1))]))
        natija.append(("xizmat sexga berilmaydi", "xizmat sexga berilmaydi" in e, True))
        e = await rad(confirm_stock_doc, DocIn(kind="sex", doc_date=BUGUN, head={}, lines=[DocLineIn(item_id=PID, name="Pila", qty=D(1))]))
        natija.append(("usta kiritilmagan", "Kim olgani kiritilmagan" in e, True))
        e = await rad(confirm_stock_doc, DocIn(kind="sex", doc_date=BUGUN, head={"taker": "U"}, lines=[DocLineIn(item_id=PID, name="Pila", qty=D(9))]))
        natija.append(("sexga ham qoldiqdan ko'p berilmaydi", "9 dona kerak, omborda 3 bor" in e, True))
        natija.append(("rad etilganda qoldiq o'zgarmadi", await qty(PID), D(3)))

        # --- 5. Inventarizatsiya
        inv = await confirm_stock_inventory(db, user, InventoryIn(doc_date=BUGUN, head={"group": "F-RC"},  # type: ignore[arg-type]
                                            counts=[InventoryCount(item_id=PID, qty=D(5)), InventoryCount(item_id=RID, qty=D(100))]), req)
        natija.append(("INV-2026-0001: farq +896 000 − 25 620 = 870 380", (inv.no, inv.status, inv.total), ("INV-2026-0001", "confirmed", D(870380))))
        natija.append(("qoldiqlar 5 va 100", (await qty(PID), await qty(RID)), (D(5), D(100))))
        natija.append(("qatorlarda hisobdagi va haqiqiy", [(l.book_qty, l.qty) for l in inv.lines], [(D(3), D(5)), (D(107), D(100))]))
        h = await read_stock_item_history(db, user, RID)  # type: ignore[arg-type]
        natija.append(("F-RC-001-01: −7 inventarizatsiya, partiyalar = qoldiq",
                       (h.moves[0].kind, h.moves[0].qty, sum((x.qty_left for x in h.lots), D(0))), ("inv", D(-7), D(100))))
        h = await read_stock_item_history(db, user, PID)  # type: ignore[arg-type]
        natija.append(("Pila: ortiqcha +2 yangi partiya (INV), jami 5", (sum((x.qty_left for x in h.lots), D(0)), h.lots[-1].source), (D(5), "INV-2026-0001")))
        e = await rad(confirm_stock_inventory, InventoryIn(doc_date=BUGUN, counts=[InventoryCount(item_id=XID, qty=D(1))]))
        natija.append(("xizmat sanalmaydi", "xizmat sanalmaydi" in e, True))
        _ = RN


asyncio.run(main())
xato = sum(1 for _, a, b in natija if a != b)
for nom, a, b in natija:
    print(f"  {'OK ' if a == b else 'XATO'} {nom}: olingan={a} kutilgan={b}")
print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")
