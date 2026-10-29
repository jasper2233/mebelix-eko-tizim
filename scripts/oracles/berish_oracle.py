"""Barkodli birliklar va sexga berish (EKO TZ §4.4, 2.3) — HAQIQIY servislar HAQIQIY Postgres ustida.

Pozitsiyalar: A (list, `M`), K (kromka, metr, rulon 100 m), C (furnitura, dona — birliksiz).
    1) kirim: A 5 list → 5 barkod; K 250 m → rulonlar 100/100/50; C 20 → birliksiz.
       Xatolar: A 2.5 list (butun emas); rulon uzunligi yo'q kromka.
    2) buyurtma 1: A 3, K 86.5 m, C 4. Direktor ruxsatigacha berilmaydi.
    3) A listi skanerlanadi → sarf 1, qoldiq 4, band 2; shu list qayta — rad.
    4) K rulon 1 (100) → sexga, 86.5 sarf, rulonda 13.5 qoladi (sex). Rulon 2 — «to'liq berilgan».
    5) C katalog kodi bilan 4 dona. A ning qolgan 2 listi → rezerv `sarflandi`, darvoza ochiq.
    6) buyurtma 2: K 20, A 1. Ombordagi rulon 3 skanerlansa — «sexda ochiq rulon bor» ogohlantirishi.
    7) rulon 1 tugadi → 13.5 hisobdan chiqadi; rulon 3 omborga qaytadi.
    8) A dan 1 sotuv → eng eski ombordagi list barkodi yopiladi (birliklar ≤ qoldiq).
    9) yorliqlash: qoldiq +2 tuzatish → 2 yorliqsiz → 2 barkod; ortig'i rad.
   10) buyurtma 2 rezervi qayta qurilsa berilgan K saqlanadi.
   11) K 130: buyurtma 4 100 m band qiladi, buyurtma 3 (120 m) faqat 30 m qoplangan — rulon 2 (100)
       skanerlansa 30 m beriladi (ogohlantirish bilan), qolgan 70 m sexda; bandsiz rulon — rad.
   12) so'rovlar: takror so'rov — o'sha; kromkasi to'liq berilgan post so'rovi o'zi yopiladi,
       arra so'rovi list berilgach yopiladi. Qayta qurilgan rezervda direktor ruxsati saqlanadi.
   13) qoldiq bo'lagi (`ATX-`): qabul → katalogga o'zi bog'lanadi (manba rezervidan), takror qabul — o'sha;
       o'z buyurtmasiga — rad; boshqasiga — ishlatildi; ishlatilganini chiqitga — rad; noma'lum yorliq — rad.
Yurgizish (lokal sinov bazasi, katalog yuklangan, prod EMAS):
    cd backend && uv run python ../scripts/oracles/berish_oracle.py
"""

import asyncio
from datetime import date
from decimal import Decimal as D

from sqlalchemy import func, select

from app.core.db import local_session
from app.models import Client, Order, WasteItem
from app.models.enums import OrderStatus
from app.modules.ombor.models import CatalogItem, MaterialBirlik, RezervLine, StockMovement
from app.modules.ombor.schemas.stock import DocIn, DocLineIn
from app.modules.ombor.services import berish, birlik, bolak, rezerv, sorov
from app.modules.ombor.services.stock import DocError, adjust_quantity, confirm, save_draft

natija: list[bool] = []


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


async def kirim(db, lines: list[DocLineIn]) -> None:
    doc = await save_draft(
        db, DocIn(kind="kirim", doc_date=date.today(), head={"supplier": "Sinov", "rate": "12 800"}, lines=lines), None
    )
    await confirm(db, doc, None)


async def units(db, item_id: int, joy: str | None = None) -> list[MaterialBirlik]:
    q = select(MaterialBirlik).where(MaterialBirlik.item_id == item_id).order_by(MaterialBirlik.id)
    if joy:
        q = q.where(MaterialBirlik.joy == joy)
    return list((await db.execute(q)).scalars())


async def rad(nom: str, coro, bor: str) -> None:
    try:
        await coro
        tek(nom, "o'tib ketdi", f"rad: {bor}")
    except (berish.BerishError, bolak.BolakError, DocError) as e:
        tek(nom, bor in str(e), True)
        if bor not in str(e):
            print("     xabar:", e)


async def line(db, order_id: int, item_id: int) -> RezervLine:
    rez = await rezerv._tirik(db, order_id)
    assert rez is not None
    return (
        await db.execute(select(RezervLine).where(RezervLine.rezerv_id == rez.id, RezervLine.item_id == item_id))
    ).scalar_one()


async def main() -> None:
    async with local_session() as db:
        q = select(CatalogItem).order_by(CatalogItem.id)
        a = (await db.execute(q.where(CatalogItem.catalog == "M", CatalogItem.unit == "list").limit(1))).scalar_one()
        k, k2 = (
            await db.execute(q.where(CatalogItem.group_code == "KM", CatalogItem.catalog == "F").limit(2))
        ).scalars()
        c = (await db.execute(q.where(CatalogItem.catalog == "F", CatalogItem.unit == "dona").limit(1))).scalar_one()
        for it in (a, k, k2, c):
            it.quantity = D(0)
            it.birlik_hajm = None
        k.birlik_hajm = D(100)
        await db.flush()

        print("1) kirim → barkodlar")
        await kirim(
            db,
            [
                DocLineIn(item_id=a.id, name=a.name, qty=D(5), price=D(10)),
                DocLineIn(item_id=k.id, name=k.name, qty=D(250), price=D("0.1")),
                DocLineIn(item_id=c.id, name=c.name, qty=D(20), price=D(1)),
            ],
        )
        ua, uk = await units(db, a.id), await units(db, k.id)
        tek("A: 5 ta birlik × 1", [u.hajm for u in ua], [D(1)] * 5)
        tek("K: rulonlar", [u.hajm for u in uk], [D(100), D(100), D(50)])
        tek("barkod EK0000NNN", ua[0].barkod, f"EK{ua[0].id:07d}")
        tek("C birliksiz", len(await units(db, c.id)), 0)
        await rad(
            "A 2.5 list", kirim(db, [DocLineIn(item_id=a.id, name=a.name, qty=D("2.5"), price=D(1))]), "butun son"
        )
        await rad("rulon uzunligi yo'q", kirim(db, [DocLineIn(item_id=k2.id, name=k2.name, qty=D(50))]), "necha metr")

        client = Client(full_name="Berish Sinov")
        db.add(client)
        await db.flush()

        def order(n: str, usage: list[dict]) -> Order:
            o = Order(
                number=n, client_id=client.id, status=OrderStatus.TECHNICAL_REVIEW, amount=D(1), material_usage=usage
            )
            db.add(o)
            return o

        o1 = order(
            "BR-1",
            [
                {"name": "List", "code": "LA", "kind": "sheet", "count": 3, "unit": "list"},
                {"name": "Kromka", "code": "KK", "kind": "band", "count": 86.5, "unit": "metr"},
                {"name": "Petlya", "code": "PC", "kind": "hardware", "count": 4, "unit": "dona"},
            ],
        )
        o2 = order(
            "BR-2",
            [
                {"name": "Kromka", "code": "KK", "kind": "band", "count": 20, "unit": "metr"},
                {"name": "List", "code": "LA", "kind": "sheet", "count": 1, "unit": "list"},
            ],
        )
        await db.flush()
        for kind, key, it in (("sheet", "LA", a), ("band", "KK", k), ("hardware", "PC", c)):
            await rezerv.apply_mapping(db, kind, key, it.id, D(1), None)
        await rezerv.reserve_for_order(db, o1)

        print("2) darvoza")
        await rad("ruxsatsiz berilmaydi", berish.skan_birlik(db, o1, ua[0].barkod, None), "Direktor ruxsati")
        await rezerv.approve(db, o1.id, None)

        print("3) list")
        n = await berish.skan_birlik(db, o1, ua[0].barkod, None)
        tek("A sarf 1", n.sarf, D(1))
        tek("A qoldiq 4", a.quantity, D(4))
        tek("A band 2", (await rezerv.reserved_qty(db, [a.id]))[a.id], D(2))
        await rad("qayta skan", berish.skan_birlik(db, o1, ua[0].barkod, None), "allaqachon ishlatilgan")

        print("4) rulon")
        n = await berish.skan_birlik(db, o1, uk[0].barkod, None)
        tek("K sarf 86.5", n.sarf, D("86.5"))
        tek("rulonda 13.5 sexda", (uk[0].qoldiq, uk[0].joy), (D("13.5"), "sex"))
        tek("K qoldiq 163.5 (sexdagi ham hisobda)", k.quantity, D("163.5"))
        await rad("ortiqcha rulon", berish.skan_birlik(db, o1, uk[1].barkod, None), "to'liq berilgan")

        print("5) furnitura va yakun")
        it = await berish.find_item(db, c.code)
        tek("katalog kodi topildi", it.id if it else None, c.id)
        await rad("C ko'p", berish.ber_dona(db, o1, c.id, D(5), None), "yana 4")
        await berish.ber_dona(db, o1, c.id, D(4), None)
        tek("C qoldiq 16", c.quantity, D(16))
        for u in ua[1:3]:
            await berish.skan_birlik(db, o1, u.barkod, None)
        tek("o1 sarflandi", await rezerv._tirik(db, o1.id), None)
        tek("o1 darvoza ochiq", await rezerv.production_block_reason(db, o1), None)
        sarf = (
            await db.execute(
                select(func.count(), func.sum(StockMovement.amount)).where(
                    StockMovement.order_id == o1.id, StockMovement.kind == "sarf"
                )
            )
        ).one()
        tek("o1 sarf harakatlari 5 ta (3 list, rulon, furnitura)", (sarf[0], sarf[1] > 0), (5, True))

        print("6) sexdagi rulon birinchi")
        await rezerv.reserve_for_order(db, o2)
        await rezerv.approve(db, o2.id, None)
        n = await berish.skan_birlik(db, o2, uk[2].barkod, None)
        tek("ogohlantirish: sexda ochiq rulon", bool(n.ogohlantirish) and uk[0].barkod in n.ogohlantirish[0], True)
        tek("rulon 3 sexda 30", (uk[2].joy, uk[2].qoldiq), ("sex", D(30)))

        print("7) rulon tugadi / omborga")
        q_ = await berish.rulon_tugadi(db, uk[0].barkod, None)
        tek("13.5 hisobdan chiqdi", q_, D("13.5"))
        tek("K qoldiq 163.5-20-13.5", k.quantity, D(130))
        await berish.omborga_qaytar(db, uk[2].barkod)
        tek("rulon 3 omborda", uk[2].joy, "ombor")
        tek("K birliklar = qoldiq", await birlik.labeled(db, k.id), k.quantity)

        print("8) sotuv birlikni yopadi")
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
        await confirm(db, doc, None)
        tek("A qoldiq 1, birliklar 1", (a.quantity, await birlik.labeled(db, a.id)), (D(1), D(1)))
        tek("eng eski list yopildi", ua[3].joy, "tugadi")

        print("9) yorliqlash")
        await adjust_quantity(db, a, D(3), None)
        tek("yorliqsiz 2", await birlik.unlabeled(db, a), D(2))
        yangi = await birlik.create(db, a, [D(1)] * 2)
        tek("2 yangi barkod", len([u for u in yangi if u.barkod]), 2)
        tek("yorliqsiz 0", await birlik.unlabeled(db, a), D(0))

        print("10) qayta rezerv berilganni saqlaydi")
        await rezerv.reserve_for_order(db, o2)
        lk = await line(db, o2.id, k.id)
        tek("K berilgan 20, qoplangan 20", (lk.berilgan_qty, lk.qoplangan_qty), (D(20), D(20)))
        tek("K band 0", (await rezerv.reserved_qty(db, [k.id])).get(k.id, D(0)), D(0))

        print("11) rulondan faqat band + erkin qism")
        o4 = order("BR-4", [{"name": "Kromka", "code": "KK", "kind": "band", "count": 100, "unit": "metr"}])
        o3 = order("BR-3", [{"name": "Kromka", "code": "KK", "kind": "band", "count": 120, "unit": "metr"}])
        await db.flush()
        await rezerv.reserve_for_order(db, o4)
        await rezerv.reserve_for_order(db, o3)
        await rezerv.approve(db, o3.id, None)
        tek("o3 qoplangan 30", (await line(db, o3.id, k.id)).qoplangan_qty, D(30))
        n = await berish.skan_birlik(db, o3, uk[1].barkod, None)
        tek("30 m berildi", n.sarf, D(30))
        tek("ogohlantirish: band", any("boshqa buyurtmalarga band" in w for w in n.ogohlantirish), True)
        tek("rulon 2 sexda 70", (uk[1].joy, uk[1].qoldiq), ("sex", D(70)))
        await rad("bandsiz qoldiq yo'q", berish.skan_birlik(db, o3, uk[2].barkod, None), "Ta'minot kerak")

        print("12) so'rovlar")
        s1 = await sorov.sora(db, o2.id, "ARRA", None, "", None)
        s1b = await sorov.sora(db, o2.id, "ARRA", None, "tezroq", None)
        tek("takror so'rov — o'sha", (s1b.id, s1b.izoh), (s1.id, "tezroq"))
        s2 = await sorov.sora(db, o2.id, "KROMKA", None, "", None)
        await sorov.auto_yop(db, o2.id, None)
        tek("kromka so'rovi yopildi, arra ochiq", (s2.holat, s1.holat), ("yetkazildi", "yangi"))
        tek("o2 ruxsati qayta qurishda saqlangan", await rezerv.production_block_reason(db, o2), None)
        await berish.skan_birlik(db, o2, yangi[0].barkod, None)
        await sorov.auto_yop(db, o2.id, None)
        tek("arra so'rovi yopildi", s1.holat, "yetkazildi")

        print("13) qoldiq bo'laklari")
        w1 = WasteItem(
            order_id=o1.id, material_name="List", sheet_no=1, length=1200.0, width=600.0, qr_text="ATX-BR-1-1"
        )
        w2 = WasteItem(
            order_id=o1.id, material_name="List", sheet_no=2, length=800.0, width=400.0, qr_text="ATX-BR-1-2"
        )
        db.add_all([w1, w2])
        await db.flush()
        b1 = await bolak.qabul(db, "ATX-BR-1-1", None)
        tek("bo'lak katalogga bog'landi", (b1.item_id, b1.joy, b1.uzunlik), (a.id, "ombor", D(1200)))
        tek("takror qabul — o'sha", (await bolak.qabul(db, "ATX-BR-1-1", None)).id, b1.id)
        await rad("o'z buyurtmasiga", bolak.ishlat(db, "ATX-BR-1-1", o1, None), "o'z kroyidan")
        b = await bolak.ishlat(db, "ATX-BR-1-1", o2, None)
        tek("o2 ga ishlatildi", (b.joy, b.order_id), ("ishlatildi", o2.id))
        await rad("ishlatilganini chiqitga", bolak.chiqit(db, b1.id), "allaqachon")
        b2 = await bolak.qabul(db, "ATX-BR-1-2", None)
        tek("chiqitga", (await bolak.chiqit(db, b2.id)).joy, "chiqit")
        await rad("noma'lum yorliq", bolak.qabul(db, "ATX-YOQ-1", None), "yo'q")

        await db.rollback()  # sinov ma'lumoti bazada qolmaydi
    print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")


asyncio.run(main())
