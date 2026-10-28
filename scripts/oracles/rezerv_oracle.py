"""Rezerv va to'lov muddati (EKO TZ §4.3, Q12–Q14, Q22–Q24) — HAQIQIY servislar HAQIQIY Postgres ustida.

Katalogdan uchta pozitsiya olinadi: A (list), B (kromka), C (furnitura). Qoldiq: A=6, B=300, C=0.
Buyurtma 1 (1 000 000 so'm): L16 × 10 list (→A), kromka 120 m (moslanmagan → B), P1 × 8 (→C).
    1) rezerv: A qoplangan 6/10, C 0/8, kromka moslanmagan; holat faol
    2) A dan 1 dona sotuv — rad (bo'sh 0, 6 band)
    3) kromka → B moslash: 120/120 qoplanadi
    4) A ga 10 kirim → A 10/10; A bo'sh qoldiq 16 − 10 = 6
    5) to'lov 400 000 (< 50%) — faol, darvoza yopiq; 500 000 — yechildi, darvoza ochiq
    6) buyurtma 2 (shu materiallar): muddati o'tkaziladi → muddati_otdi, A band yana 10
    7) doimiy mijoz, limit 2 000 000: qarz 500 000 + 1 000 000 ≤ limit → ochiq; limit 1 000 000 → yopiq;
       direktor ruxsati → ochiq
    8) buyurtma 2 bekor → holat bekor
Yurgizish (lokal sinov bazasi, katalog yuklangan — `catalog_oracle.py` dagi kabi, prod EMAS):
    cd backend && uv run python ../scripts/oracles/rezerv_oracle.py
"""

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal as D

from sqlalchemy import select

from app.core.db import local_session
from app.models import Client, Order
from app.models.enums import OrderStatus
from app.modules.ombor.models import CatalogItem, Rezerv, RezervLine
from app.modules.ombor.schemas.stock import DocIn, DocLineIn
from app.modules.ombor.services import rezerv
from app.modules.ombor.services.stock import DocError, confirm, save_draft

natija: list[bool] = []


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


USAGE = [
    {"name": "LDSP Oq 16", "code": "L16", "kind": "sheet", "count": 10, "unit": "list"},
    {"name": "Kromka  Oq 0.4", "code": None, "kind": "band", "count": 120, "unit": "metr"},
    {"name": "Petlya", "code": "P1", "kind": "hardware", "count": 8, "unit": "dona"},
]


async def lines_of(db, order_id: int) -> dict[str, tuple[D, D, int | None]]:
    rez = await rezerv._tirik(db, order_id)
    assert rez is not None
    rows = (await db.execute(select(RezervLine).where(RezervLine.rezerv_id == rez.id))).scalars()
    return {r.tashqi_kalit: (r.qoplangan_qty, r.kerak_qty, r.item_id) for r in rows}


async def main() -> None:
    async with local_session() as db:
        items = list(
            (
                await db.execute(
                    select(CatalogItem).where(CatalogItem.catalog.in_(["M", "F"])).order_by(CatalogItem.id).limit(3)
                )
            ).scalars()
        )
        a, b, c = items
        a.quantity, b.quantity, c.quantity = D(6), D(300), D(0)
        client = Client(full_name="Rezerv Sinov")
        db.add(client)
        await db.flush()
        orders = []
        for i in (1, 2):
            o = Order(
                number=f"R-{i}",
                client_id=client.id,
                status=OrderStatus.TECHNICAL_REVIEW,
                amount=D(1_000_000),
                material_usage=USAGE,
            )
            db.add(o)
            orders.append(o)
        await db.flush()
        o1, o2 = orders
        await rezerv.apply_mapping(db, "sheet", "L16", a.id, D(1), None)
        await rezerv.apply_mapping(db, "hardware", "P1", c.id, D(1), None)

        print("1) rezerv")
        await rezerv.reserve_for_order(db, o1)
        ln = await lines_of(db, o1.id)
        tek("A qoplangan/kerak", ln["L16"][:2], (D(6), D(10)))
        tek("C qoplangan/kerak", ln["P1"][:2], (D(0), D(8)))
        tek("kromka moslanmagan", ln["kromka oq 0.4"][2], None)
        tek("holat", (await rezerv._tirik(db, o1.id)).holat, "faol")  # type: ignore[union-attr]

        print("2) band qoldiq sotilmaydi")
        doc = await save_draft(
            db,
            DocIn(
                kind="chiqim",
                doc_date=date.today(),
                head={"client": "Boshqa"},
                lines=[DocLineIn(item_id=a.id, name=a.name, qty=D(1), price=D(1))],
            ),
            None,
        )
        try:
            await confirm(db, doc, None)
            tek("sotuv rad etildi", False, True)
        except DocError as e:
            tek("sotuv rad etildi", "buyurtmalarga band" in str(e), True)

        print("3) moslash")
        await rezerv.apply_mapping(db, "band", "kromka oq 0.4", b.id, D(1), None)
        tek("kromka qoplangan/kerak", (await lines_of(db, o1.id))["kromka oq 0.4"][:2], (D(120), D(120)))

        print("4) kirim yetmaganni qoplaydi")
        kir = await save_draft(
            db,
            DocIn(
                kind="kirim",
                doc_date=date.today(),
                head={"supplier": "Sinov", "rate": "12 800"},
                lines=[DocLineIn(item_id=a.id, name=a.name, qty=D(10), price=D(1))],
            ),
            None,
        )
        await confirm(db, kir, None)
        tek("A qoplangan", (await lines_of(db, o1.id))["L16"][0], D(10))
        tek("A band", (await rezerv.reserved_qty(db, [a.id]))[a.id], D(10))

        print("5) to'lov chegarasi")
        o1.advance_payment = D(400_000)
        await rezerv.check_payment(db, o1)
        tek("400 000 — faol", (await rezerv._tirik(db, o1.id)).holat, "faol")  # type: ignore[union-attr]
        tek("darvoza yopiq", (await rezerv.production_block_reason(db, o1)) is not None, True)
        o1.advance_payment = D(500_000)
        await rezerv.check_payment(db, o1)
        tek("500 000 — yechildi", (await rezerv._tirik(db, o1.id)).holat, "yechildi")  # type: ignore[union-attr]
        tek("darvoza ochiq", await rezerv.production_block_reason(db, o1), None)

        print("6) muddat o'tdi")
        await rezerv.reserve_for_order(db, o2)
        tek("o2 A qoplangan (bo'sh 6)", (await lines_of(db, o2.id))["L16"][0], D(6))
        r2 = await rezerv._tirik(db, o2.id)
        assert r2 is not None
        r2.muddat = datetime.now(UTC) - timedelta(minutes=1)
        await db.flush()
        tek("expire_due", await rezerv.expire_due(db), 1)
        await db.refresh(r2)  # UPDATE sessiyadagi obyektni yangilamaydi
        tek("o2 holat", r2.holat, "muddati_otdi")
        tek("A band (faqat o1)", (await rezerv.reserved_qty(db, [a.id]))[a.id], D(10))

        print("7) kredit limiti va direktor")
        client.doimiy, client.kredit_limit = True, D(2_000_000)
        await db.flush()
        tek("qarz", await rezerv.client_debt(db, client.id), D(1_500_000))
        tek("limit ichida — ochiq", await rezerv.production_block_reason(db, o2), None)
        client.kredit_limit = D(1_000_000)
        await db.flush()
        tek("limitdan oshdi — yopiq", (await rezerv.production_block_reason(db, o2)) is not None, True)
        await rezerv.approve(db, o2.id, 1)
        tek("direktor ruxsati — ochiq", await rezerv.production_block_reason(db, o2), None)

        print("8) bekor")
        await rezerv.cancel_for_order(db, o2.id)
        last = (await db.execute(select(Rezerv).where(Rezerv.order_id == o2.id).order_by(Rezerv.id.desc()))).scalars()
        tek("o2 holat", next(iter(last)).holat, "bekor")

        print("9) ta'minot ro'yxati")
        sh = {s.item_id: (s.kerak - s.qoplangan) for s in await rezerv.shortages(db)}
        tek("C yetmaydi 8", sh.get(c.id), D(8))
        tek("A yetishmovchiligi yo'q", a.id in sh, False)

        await db.rollback()  # sinov ma'lumoti bazada qolmaydi
    print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")


asyncio.run(main())
