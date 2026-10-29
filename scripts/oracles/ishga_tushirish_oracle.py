"""Ishga tushirish (EKO 8) — ochilish qoldiqlari, qo'lda avans qulfi, tayyorlik tekshiruvi.
HAQIQIY servislar va yo'l funksiyalari HAQIQIY Postgres ustida.

  1) kassa boshlanguncha buyurtmada qo'lda avans yoziladi; birinchi kassa orderidan keyin — rad
  2) mijozning ochilish qarzi 1 000 000 (40 kun oldin): Moliya debitorida qarz va muddati o'tgan; akt debetida
  3) qarz to'lovi 1 200 000: avval ochilish qarzi (1 000 000), qolgani eng eski buyurtmaga (200 000);
     undan ko'pi — rad; storno — taqsimot teskari
  4) kamaytirish (manfiy qator) to'langan qismdan pastga tushmaydi; rezerv kredit limiti ochilish qarzini ko'radi
  5) ta'minotchi ochilish qarzi 500 000 − to'lov 200 000 = kreditor 300 000
  6) buxgalteriya nazorati 4010 / 6010 / 5010 — farq yo'q
  7) tayyorlik: soliq rejimi yo'q — xato; ikki kalit uchun 2 xodim — ok
    cd backend && uv run python ../scripts/oracles/ishga_tushirish_oracle.py
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

from starlette.requests import Request

from app.api.routes.orders.lifecycle import update_order
from app.api.routes.tayyorlik import tayyorlik
from app.core.db import local_session
from app.core.exceptions import ForbiddenException
from app.models import Client, Order, User
from app.models.enums import OrderStatus, UserRole
from app.modules.buxgalteriya import services as bux
from app.modules.kassa import services as k
from app.modules.moliya import services as m
from app.modules.ombor.services import rezerv
from app.schemas.orders import OrderUpdate

natija: list[bool] = []
REQ = Request({"type": "http", "headers": [], "client": ("127.0.0.1", 0)})


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


async def rad(nom: str, coro, bor: str, exc: type[Exception] = k.KassaXato) -> None:  # type: ignore[no-untyped-def]
    try:
        await coro
        tek(nom, "o'tib ketdi", f"rad: {bor}")
    except exc as e:
        tek(nom, bor in str(e), True)
        if bor not in str(e):
            print("     xabar:", e)


async def main() -> None:
    today = m.bugun()
    now = datetime.now(UTC)
    async with local_session() as db:
        u1 = User(username="it1", name="Kassir", phone="+998900008101", hashed_password="x", role=UserRole.KASSIR)
        u2 = User(username="it2", name="Moliyachi", phone="+998900008102", hashed_password="x", role=UserRole.MOLIYACHI)
        u3 = User(username="it3", name="Direktor", phone="+998900008103", hashed_password="x", role=UserRole.DIRECTOR)
        cl = Client(full_name="Eski Mijoz", phone="+998900008104")
        db.add_all([u1, u2, u3, cl])
        await db.flush()
        o1 = Order(
            number="IT-1",
            client_id=cl.id,
            status=OrderStatus.DELIVERED,
            amount=D(400_000),
            delivered_at=now - timedelta(days=5),
        )
        o2 = Order(number="IT-2", client_id=cl.id, status=OrderStatus.PRODUCTION, amount=D(900_000))
        db.add_all([o1, o2])
        await db.flush()

        print("1) qo'lda avans qulfi")
        await update_order(db, u3, o2.id, OrderUpdate(advance_payment=D(100_000)), REQ)
        tek("kassagacha: avans yoziladi", o2.advance_payment, D(100_000))
        await k.smena_och(db, {"100000": 5}, u1.id)
        await k.kirim(db, maqsad="boshqa", tolovlar=[k.Tolov("naqd", D(1))], user_id=u1.id, kontragent="sinov")
        await rad(
            "kassa boshlangach: rad",
            update_order(db, u3, o2.id, OrderUpdate(advance_payment=D(200_000)), REQ),
            "Kassa orqali",
            ForbiddenException,
        )

        print("2) mijoz ochilish qarzi")
        await k.ochilish_qosh(
            db, "mijoz", D(1_000_000), today - timedelta(days=40), u2.id, client_id=cl.id, izoh="1C dan"
        )
        d = [x for x in await m.debitorlar(db) if x.client_id == cl.id][0]
        tek(
            "qarz 1 400 000, muddati o'tgan 1 000 000 (40 > 10 kun)",
            (d.qarz, d.muddati_otgan_summa, d.kun),
            (D(1_400_000), D(1_000_000), 40),
        )
        a = await m.akt(db, cl.id, today - timedelta(days=60), today)
        tek(
            "akt: ochilish debetda, yakuniy 1 300 000 (avans 100 000 ayirilgan)",
            (a.qatorlar[0].hujjat, a.yakuniy),
            ("OCHILISH", D(1_300_000)),
        )

        print("3) qarz to'lovi — avval ochilish qarzi")
        await rad(
            "qarzdan ko'p (jami 2 200 000: ochilish + IT-1 + IT-2 qolgani)",
            k.kirim(db, maqsad="qarz", tolovlar=[k.Tolov("naqd", D(3_000_000))], user_id=u1.id, client_id=cl.id),
            "qarzi",
        )
        n = await k.kirim(db, maqsad="qarz", tolovlar=[k.Tolov("naqd", D(1_200_000))], user_id=u1.id, client_id=cl.id)
        tek(
            "ochilish qarzi yopildi, IT-1 ga 200 000",
            (await k.ochilish_qoldigi(db, cl.id), (await k.tolangan(db, [o1.id]))[o1.id]),
            (D(0), D(200_000)),
        )
        await k.storno(db, n.orderlar[0].id, u2.id, "xato summa")
        tek(
            "storno: ochilish qarzi qaytdi",
            (await k.ochilish_qoldigi(db, cl.id), (await k.tolangan(db, [o1.id])).get(o1.id)),
            (D(1_000_000), D(0)),
        )
        await k.kirim(db, maqsad="qarz", tolovlar=[k.Tolov("naqd", D(300_000))], user_id=u1.id, client_id=cl.id)

        print("4) tuzatish va kredit limiti")
        await rad(
            "to'langandan pastga kamaytirish",
            k.ochilish_qosh(db, "mijoz", D(-800_000), today, u2.id, client_id=cl.id),
            "to'lagan qismdan",
        )
        await k.ochilish_qosh(db, "mijoz", D(-100_000), today, u2.id, client_id=cl.id, izoh="hisob-kitobda xato")
        tek("ochilish qoldig'i 600 000", await k.ochilish_qoldigi(db, cl.id), D(600_000))
        tek("rezerv: mijoz qarzi = ochilish 600 000 + IT-1 400 000 + IT-2 qolgani 800 000", await rezerv.client_debt(db, cl.id), D(1_800_000))

        print("5) ta'minotchi ochilish qarzi")
        await k.ochilish_qosh(
            db, "taminotchi", D(500_000), today - timedelta(days=20), u2.id, kontragent="Eski Ta'minotchi"
        )
        await k.chiqim(
            db, maqsad="taminotchi", hisob_kod="naqd", summa=D(200_000), user_id=u1.id, kontragent="eski ta'minotchi"
        )
        kr = [x for x in await m.kreditorlar(db) if x.nom.casefold().startswith("eski")]
        tek(
            "kreditor: 500 000 − 200 000",
            [(x.faktura, x.tolangan, x.qarz) for x in kr],
            [(D(500_000), D(200_000), D(300_000))],
        )
        kal = [r for r in await m.kalendar(db, 45) if "ochilish" in r.nom]
        tek(
            "kalendar: mijoz ochilish qarzi muddati o'tgan",
            [(r.summa, r.muddati_otgan) for r in kal],
            [(D(600_000), True)],
        )

        print("6) buxgalteriya nazorati")
        await bux.sinxron(db)
        tek(
            "4010 / 6010 / 5010 farqsiz",
            [
                x.nom
                for x in await bux.nazorat(db)
                if abs(x.farq) >= D("0.01") and x.nom[:4] in ("4010", "6010", "5010")
            ],
            [],
        )

        print("7) tayyorlik")
        t = {x.nom: x.holat for x in await tayyorlik(db, u3)}
        tek("soliq rejimi yo'q — xato", t.get("Soliq rejimi (QQS / aylanma)"), "xato")
        tek("ikki kalit uchun 2 xodim — ok", t.get("Ikki kalit uchun kamida 2 xodim"), "ok")
        tek("ochilish qoldiqlari — ok", t.get("Ochilish qoldiqlari (eski qarzlar)"), "ok")
        await db.rollback()
    print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")


asyncio.run(main())
