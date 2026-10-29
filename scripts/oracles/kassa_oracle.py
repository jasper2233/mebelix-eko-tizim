"""Kassa (EKO TZ §7, prototip `kassa-core.js`) — HAQIQIY servislar HAQIQIY Postgres ustida, bitta kassa kuni.

    1) smenasiz naqd — rad; birinchi smena: sanalgan naqd = boshlang'ich (500 000)
    2) avans 400 000 naqd, mijoz 500 000 berdi — qaytim 100 000; rezerv: «chegaraga yana 100 000 so'm kerak»
    3) aralash to'lov: naqd 50 000 + karta 100 000 — bitta guruh, rezerv «material biriktirildi»
    4) buyurtma qolganidan ko'p — rad
    5) xarajat turkumsiz — rad; 50 000 xarajat; kassadagidan ko'p — rad
    6) qarz 500 000: eng eski buyurtmadan (B1 450 000, B2 50 000)
    7) qaytarish 100 000 (B1) — to'langan kamayadi; to'langanidan ko'p — rad
    8) naqd → bank o'tkazma 100 000; bankdan ta'minotchiga 50 000, komissiya 1 % alohida order
    9) storno: o'zi — rad (ikki kalit); boshqa xodim — teskari order, komissiya bilan birga; takror — rad
   10) jurnalni UPDATE — baza rad etadi
   11) smena yopish: kutilgan 1 200 000, sanaldi 1 190 000 → farq −10 000 orderi; karta tushumi 100 000
Lokal sinov bazasi (katalog yuklangan), prod EMAS:
    cd backend && uv run python ../scripts/oracles/kassa_oracle.py
"""

import asyncio
from decimal import Decimal as D

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.db import local_session
from app.models import Client, Order, User
from app.models.enums import OrderStatus, UserRole
from app.modules.kassa import services as k
from app.modules.kassa.models import KassaHisob, KassaOrder
from app.modules.ombor.models import CatalogItem
from app.modules.ombor.services import rezerv

natija: list[bool] = []


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


async def rad(nom: str, coro, bor: str) -> None:  # type: ignore[no-untyped-def]
    try:
        await coro
        tek(nom, "o'tib ketdi", f"rad: {bor}")
    except k.KassaXato as e:
        tek(nom, bor in str(e), True)
        if bor not in str(e):
            print("     xabar:", e)


async def main() -> None:
    async with local_session() as db:
        u1 = User(
            username="kassir1", name="Kassir Bir", phone="+998900000101", hashed_password="x", role=UserRole.KASSIR
        )
        u2 = User(
            username="direktor2", name="Direktor", phone="+998900000102", hashed_password="x", role=UserRole.DIRECTOR
        )
        db.add_all([u1, u2])
        a = (await db.execute(select(CatalogItem).where(CatalogItem.catalog == "M").limit(1))).scalar_one()
        a.quantity = D(10)
        cl = Client(full_name="Kassa Sinov", phone="+998901112233")
        db.add(cl)
        await db.flush()
        b1 = Order(
            number="KS-1",
            client_id=cl.id,
            status=OrderStatus.TECHNICAL_REVIEW,
            amount=D(1_000_000),
            material_usage=[{"name": "L", "code": "KSL", "kind": "sheet", "count": 1, "unit": "list"}],
        )
        db.add(b1)
        await db.flush()
        b2 = Order(number="KS-2", client_id=cl.id, status=OrderStatus.TECHNICAL_REVIEW, amount=D(300_000))
        db.add(b2)
        await db.flush()
        await rezerv.apply_mapping(db, "sheet", "KSL", a.id, D(1), None)
        await rezerv.reserve_for_order(db, b1)
        N = k.Tolov

        print("1) smena")
        await rad(
            "smenasiz naqd",
            k.kirim(db, maqsad="avans", tolovlar=[N("naqd", D(1000))], user_id=u1.id, order_id=b1.id),
            "smenani oching",
        )
        sm, farq = await k.smena_och(db, {"100000": 5}, u1.id)
        naqd = (await db.execute(select(KassaHisob).where(KassaHisob.kod == "naqd"))).scalar_one()
        tek("birinchi smena: boshlang'ich 500 000, farq 0", (naqd.boshlangich, farq), (D(500_000), D(0)))

        print("2) avans va qaytim")
        n = await k.kirim(
            db, maqsad="avans", tolovlar=[N("naqd", D(400_000))], user_id=u1.id, order_id=b1.id, mijoz_berdi=D(500_000)
        )
        tek("qaytim 100 000", n.qaytim, D(100_000))
        tek("rezerv xabari", n.rezerv, ["KS-1: chegaraga yana 100 000 so'm kerak"])
        tek("PKO raqami", n.orderlar[0].no.startswith("PKO-"), True)

        print("3) aralash to'lov")
        n = await k.kirim(
            db, maqsad="tolov", tolovlar=[N("naqd", D(50_000)), N("karta", D(100_000))], user_id=u1.id, order_id=b1.id
        )
        tek(
            "ikki order bitta guruh",
            (len(n.orderlar), n.orderlar[0].guruh == n.orderlar[1].guruh is not None),
            (2, True),
        )
        tek("material biriktirildi", n.rezerv, ["KS-1: material biriktirildi"])
        tek("to'langan 550 000", await k.jami_tolangan(db, b1), D(550_000))

        print("4) ortiqcha to'lov")
        await rad(
            "qolganidan ko'p",
            k.kirim(db, maqsad="tolov", tolovlar=[N("naqd", D(600_000))], user_id=u1.id, order_id=b1.id),
            "undan ko'p olib bo'lmaydi",
        )

        print("5) xarajat")
        await rad(
            "turkumsiz", k.chiqim(db, maqsad="xarajat", hisob_kod="naqd", summa=D(50_000), user_id=u1.id), "turkumini"
        )
        await k.chiqim(
            db, maqsad="xarajat", hisob_kod="naqd", summa=D(50_000), user_id=u1.id, turkum="Xo'jalik mollari"
        )
        await rad(
            "kassadagidan ko'p",
            k.chiqim(db, maqsad="xarajat", hisob_kod="naqd", summa=D(10_000_000), user_id=u1.id, turkum="Ijara"),
            "yetarli mablag'",
        )

        print("6) qarz — eng eskisidan")
        n = await k.kirim(db, maqsad="qarz", tolovlar=[N("naqd", D(500_000))], user_id=u1.id, client_id=cl.id)
        p = await k.tolangan(db, [b1.id, b2.id])
        tek("B1 to'liq (1 000 000), B2 50 000", (p[b1.id], p[b2.id]), (D(1_000_000), D(50_000)))
        await rad(
            "qarzdan ko'p",
            k.kirim(db, maqsad="qarz", tolovlar=[N("naqd", D(500_000))], user_id=u1.id, client_id=cl.id),
            "qarzi 250 000",
        )

        print("7) qaytarish")
        await k.chiqim(db, maqsad="qaytarish", hisob_kod="naqd", summa=D(100_000), user_id=u1.id, order_id=b1.id)
        tek("B1 to'langan 900 000", (await k.tolangan(db, [b1.id]))[b1.id], D(900_000))
        await rad(
            "to'langanidan ko'p",
            k.chiqim(db, maqsad="qaytarish", hisob_kod="naqd", summa=D(950_000), user_id=u1.id, order_id=b1.id),
            "undan ko'p qaytmaydi",
        )

        print("8) o'tkazma va komissiya")
        await k.otkazma(db, "naqd", "bank", D(100_000), u1.id)
        bank = (await db.execute(select(KassaHisob).where(KassaHisob.kod == "bank"))).scalar_one()
        bank.komissiya_foiz = D(1)
        n = await k.chiqim(
            db, maqsad="taminotchi", hisob_kod="bank", summa=D(50_000), user_id=u1.id, kontragent="Ta'minotchi MCHJ"
        )
        tek(
            "komissiya 500 alohida order",
            [(o.maqsad, o.summa) for o in n.orderlar],
            [("taminotchi", D(50_000)), ("komissiya", D(500))],
        )
        tek("bank qoldig'i 49 500", await k.qoldiq(db, bank), D(49_500))
        taminot = n.orderlar[0]

        print("9) storno")
        await rad("o'zi storno — ikki kalit", k.storno(db, taminot.id, u1.id, "xato"), "Ikki kalit")
        n = await k.storno(db, taminot.id, u2.id, "noto'g'ri summa")
        tek("komissiya bilan birga, manfiy summa", sorted(o.summa for o in n.orderlar), [D(-50_000), D(-500)])
        tek("bank qoldig'i 100 000", await k.qoldiq(db, bank), D(100_000))
        await rad("takror storno", k.storno(db, taminot.id, u2.id, "yana"), "allaqachon")

        print("10) jurnal o'zgarmaydi")
        try:
            async with db.begin_nested():
                await db.execute(text("UPDATE kassa_order SET summa = 1"))
            tek("UPDATE rad", False, True)
        except DBAPIError as e:
            tek("UPDATE rad", "jurnal faqat qo'shiladi" in str(e), True)

        print("11) smena yopish")
        st = await k.smena_hisobi(db, sm)
        tek("kutilgan naqd 1 200 000", st["kutilgan"], D(1_200_000))
        yop = await k.smena_yop(db, {"200000": 5, "100000": 1, "10000": 9}, D(100_000), u1.id)
        tek("farq −10 000, karta 100 000", (yop.farq, yop.karta_tushum), (D(-10_000), D(100_000)))
        farq_o = (await db.execute(select(KassaOrder).where(KassaOrder.maqsad == "farq"))).scalar_one()
        tek("kamomad orderi RKO 10 000", (farq_o.tur, farq_o.summa), ("chiqim", D(10_000)))
        tek("naqd kitob = sanalgan", await k.qoldiq(db, naqd), D(1_190_000))
        await rad(
            "yopiq smenada naqd",
            k.kirim(db, maqsad="boshqa", tolovlar=[N("naqd", D(1000))], user_id=u1.id, kontragent="x"),
            "smenani oching",
        )

        await db.rollback()  # sinov ma'lumoti bazada qolmaydi
    print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")


asyncio.run(main())
