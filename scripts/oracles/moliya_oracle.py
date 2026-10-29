"""Moliya (EKO TZ §8) — qabul mezoni: «sintetik oy: P&L va pul oqimi qo'lda hisob bilan mos».
HAQIQIY servislar HAQIQIY Postgres ustida; joriy oy (Toshkent vaqti) — sintetik oy.

Qo'lda hisob (joriy oy):
  buyurtmalar: B1 1 000 000 (yetkazildi, sarf 300 000 − qaytish 50 000), B2 600 000 (yetkazildi 15 kun oldin),
               B3 2 000 000 (yetkazilmagan)
  do'kon:      chiqim 400 000 (tannarx 260 000) + chiqim 100 000 (70 000) va uning stornosi
  kassa:       smena 1 000 000; B1 to'lov naqd 1 000 000; B2 avans karta 200 000; B3 avans naqd 500 000;
               Ijara 300 000; Kommunal 50 000 → storno; ta'minotchi naqd 400 000; naqd→bank 500 000;
               bankdan ta'minotchiga 100 000 + komissiya 1 % = 1 000; yopishda 5 000 kam sanaldi
  P&L:   sotuv 1 600 000 + 400 000 = 2 000 000; tannarx 250 000 + 260 000 = 510 000; yalpi 1 490 000;
         xarajat Ijara 300 000 + komissiya 1 000 + kamomad 5 000 = 306 000; sof 1 184 000
  oqim:  kirim 1 700 000; chiqim 300 000 + 0 + 400 000 + 100 000 + 1 000 + 5 000 = 806 000; saldo 894 000
  qoldiq: naqd 1 295 000, karta 200 000, bank 399 000
  debitor: qarz 400 000 (B2, muddati o'tgan 15 > 10), avans 500 000 (B3); akt yakuniy −100 000
  kreditor: Ningbo faktura 300 000 + 900 000, to'langan 500 000 → qarz 700 000 (eski hujjat yopilgan)
Davr: joriy oy yopilmaydi; o'tgan oy yopiladi → natija qotadi, o'sha sanali hujjat rad, qayta ochish ikki kalit.
    cd backend && uv run python ../scripts/oracles/moliya_oracle.py
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

from sqlalchemy import select

from app.core.db import local_session
from app.models import Client, Order, User
from app.models.enums import OrderStatus, UserRole
from app.modules.kassa import services as k
from app.modules.kassa.models import KassaOrder
from app.modules.moliya import services as m
from app.modules.moliya.models import MoliyaReja
from app.modules.ombor.models import CatalogItem, StockDoc, StockMovement
from app.modules.ombor.services.stock import DocError, confirm

natija: list[bool] = []


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


async def rad(nom: str, coro, bor: str, exc: type[Exception] = Exception) -> None:  # type: ignore[no-untyped-def]
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
        u1 = User(username="kassir5", name="Kassir", phone="+998900000501", hashed_password="x", role=UserRole.KASSIR)
        u2 = User(
            username="moliyachi5", name="Moliyachi", phone="+998900000502", hashed_password="x", role=UserRole.MOLIYACHI
        )
        db.add_all([u1, u2])
        cl = Client(full_name="Moliya Sinov", phone="+998901115566")
        db.add(cl)
        await db.flush()

        def order(no: str, summa: int, delivered: datetime | None) -> Order:
            return Order(
                number=no,
                client_id=cl.id,
                status=OrderStatus.DELIVERED if delivered else OrderStatus.PRODUCTION,
                amount=D(summa),
                delivered_at=delivered,
            )

        b1, b2, b3 = (
            order("MS-1", 1_000_000, now),
            order("MS-2", 600_000, now - timedelta(days=15)),
            order("MS-3", 2_000_000, None),
        )
        db.add_all([b1, b2, b3])
        await db.flush()
        item = (await db.execute(select(CatalogItem).where(CatalogItem.catalog == "M").limit(1))).scalar_one()
        for kind, q, s in (("sarf", -2, 300_000), ("qaytish", 1, 50_000)):
            db.add(
                StockMovement(item_id=item.id, kind=kind, qty=D(q), balance=item.quantity, amount=D(s), order_id=b1.id)
            )

        def doc(no: str, kind: str, total: int, cogs: int | None, head: dict, sana=today) -> StockDoc:  # type: ignore[no-untyped-def,type-arg]
            return StockDoc(
                no=no,
                kind=kind,
                status="confirmed",
                doc_date=sana,
                head=head,
                total=D(total),
                cogs=D(cogs) if cogs is not None else None,
            )

        d1 = doc("MCHQ-1", "chiqim", 400_000, 260_000, {"client": "Do'kon mijozi"})
        d2 = doc("MCHQ-2", "chiqim", 100_000, 70_000, {"client": "Do'kon mijozi"})
        db.add_all([d1, d2])
        await db.flush()
        db.add(doc("MSTR-1", "storno", 0, None, {"asl": d2.no, "asl_id": str(d2.id)}))
        d2.status = "storno"  # storno servisi asl hujjatni shunday belgilaydi (regressiya: Moliya uni o'qishi kerak)
        db.add(
            doc(
                "MKIR-1",
                "kirim",
                300_000,
                None,
                {"supplier": "Ningbo MCHJ", "due": str(today - timedelta(days=2))},
                today - timedelta(days=20),
            )
        )
        db.add(
            doc(
                "MKIR-2",
                "kirim",
                900_000,
                None,
                {"supplier": "ningbo  mchj", "due": str(today + timedelta(days=10))},
                today - timedelta(days=5),
            )
        )
        await db.flush()
        N = k.Tolov

        print("1) kassa kuni")
        sm, _ = await k.smena_och(db, {"100000": 10}, u1.id)
        await k.kirim(db, maqsad="tolov", tolovlar=[N("naqd", D(1_000_000))], user_id=u1.id, order_id=b1.id)
        await k.kirim(db, maqsad="avans", tolovlar=[N("karta", D(200_000))], user_id=u1.id, order_id=b2.id)
        await k.kirim(db, maqsad="avans", tolovlar=[N("naqd", D(500_000))], user_id=u1.id, order_id=b3.id)
        await k.chiqim(db, maqsad="xarajat", hisob_kod="naqd", summa=D(300_000), user_id=u1.id, turkum="Ijara")
        kom = await k.chiqim(db, maqsad="xarajat", hisob_kod="naqd", summa=D(50_000), user_id=u1.id, turkum="Kommunal")
        await rad(
            "noma'lum modda rad",
            k.chiqim(db, maqsad="xarajat", hisob_kod="naqd", summa=D(1), user_id=u1.id, turkum="Kosmos"),
            "moddasi yo'q",
        )
        await k.chiqim(
            db, maqsad="taminotchi", hisob_kod="naqd", summa=D(400_000), user_id=u1.id, kontragent="Ningbo MCHJ"
        )
        await k.otkazma(db, "naqd", "bank", D(500_000), u1.id)
        await k.hisob_sozla(db, "bank", None, D(1))
        await rad("bank boshlang'ichi o'zgarmaydi", k.hisob_sozla(db, "bank", D(5), None), "boshlang'ich qoldiq endi")
        await k.chiqim(
            db, maqsad="taminotchi", hisob_kod="bank", summa=D(100_000), user_id=u1.id, kontragent="NINGBO mchj"
        )
        await k.storno(db, kom.orderlar[0].id, u2.id, "xato yozildi")
        await k.smena_yop(db, {"100000": 12, "50000": 1, "10000": 4, "5000": 1}, None, u1.id)

        print("2) foyda va zarar (qo'lda hisob bilan)")
        p = await m.pnl(db, today)
        tek(
            "sotuv: buyurtma / do'kon / jami",
            (p.sotuv_buyurtma, p.sotuv_ombor, p.sotuv),
            (D(1_600_000), D(400_000), D(2_000_000)),
        )
        tek(
            "tannarx: buyurtma / do'kon / jami",
            (p.tannarx_buyurtma, p.tannarx_ombor, p.tannarx),
            (D(250_000), D(260_000), D(510_000)),
        )
        tek("yalpi foyda", p.yalpi, D(1_490_000))
        tek(
            "xarajatlar (storno qilingan Kommunal yo'q)",
            [(q.nom, q.summa) for q in p.xarajatlar],
            [("Ijara", D(300_000)), ("Bank komissiyasi", D(1_000))],
        )
        tek("kassa kamomadi", p.kassa_farqi, D(5_000))
        tek("xarajat jami / sof foyda", (p.xarajat_jami, p.sof), (D(306_000), D(1_184_000)))
        tek(
            "B1 rentabelligi",
            [(r.number, r.foyda) for r in p.buyurtmalar if r.number == "MS-1"],
            [("MS-1", D(750_000))],
        )

        print("3) pul oqimi")
        o = await m.pul_oqimi(db, m.oy_boshi(today), today)
        tek("kirim / chiqim / saldo", (o.kirim, o.chiqim, o.saldo), (D(1_700_000), D(806_000), D(894_000)))
        tek(
            "hisob qoldiqlari",
            {h.kod: h.qoldiq for h in o.hisoblar},
            {"naqd": D(1_295_000), "karta": D(200_000), "bank": D(399_000)},
        )
        tek(
            "naqd: kirim / chiqim (o'tkazmasiz)",
            [(h.kirim, h.chiqim) for h in o.hisoblar if h.kod == "naqd"],
            [(D(1_500_000), D(705_000))],
        )
        tek(
            "joriy oy qatori = jami",
            [(x.kirim, x.chiqim) for x in o.oylar if x.oy == f"{today:%Y-%m}"],
            [(D(1_700_000), D(806_000))],
        )

        print("4) debitorlik va akt sverki")
        deb = [d for d in await m.debitorlar(db) if d.client_id == cl.id]
        tek(
            "qarz / avans / muddati o'tgan",
            [(d.qarz, d.avans, d.kun, d.muddati_otgan, d.muddati_otgan_summa) for d in deb],
            [(D(400_000), D(500_000), 15, True, D(400_000))],
        )
        await m.mijoz_shart_saqla(db, cl.id, "SH-7", 30, D(300_000))
        d = [d for d in await m.debitorlar(db) if d.client_id == cl.id][0]
        tek(
            "shartnoma 30 kun: muddat ichida, limitdan oshgan",
            (d.muddati_otgan, d.limitdan_oshgan, d.shartnoma_no),
            (False, True, "SH-7"),
        )
        a = await m.akt(db, cl.id, m.oy_boshi(today) - timedelta(days=40), today)
        tek("akt: debet / kredit / yakuniy", (a.debet, a.kredit, a.yakuniy), (D(1_600_000), D(1_700_000), D(-100_000)))

        print("5) kreditorlik va kalendar")
        kr = [x for x in await m.kreditorlar(db) if x.nom.casefold().startswith("ningbo")]
        tek(
            "Ningbo: faktura / to'langan / qarz / muddat",
            [(x.faktura, x.tolangan, x.qarz, x.muddat) for x in kr],
            [(D(1_200_000), D(500_000), D(700_000), today + timedelta(days=10))],
        )
        db.add(MoliyaReja(nom="Ijara", tur="chiqim", summa=D(300_000), turkum="Ijara", takror="oylik", sana=today))
        db.add(
            MoliyaReja(nom="Kredit", tur="chiqim", summa=D(1_000_000), takror="bir", sana=today + timedelta(days=20))
        )
        await db.flush()
        kal = await m.kalendar(db, 45)
        tek(
            "B2 qarzi kalendarda (shartnoma 30 kun)",
            [(r.sana, r.summa) for r in kal if "MS-2" in r.nom],
            [(today - timedelta(days=15) + timedelta(days=30), D(400_000))],
        )
        tek(
            "Ningbo 700 000 muddatida",
            [(r.sana, r.summa) for r in kal if r.manba == "taminotchi"],
            [(today + timedelta(days=10), D(700_000))],
        )
        tek(
            "rejali: Ijara 2 marta, Kredit 1 marta",
            sorted(r.nom for r in kal if r.manba == "reja"),
            ["Ijara", "Ijara", "Kredit"],
        )

        print("6) byudjet va balans")
        ijara = (await k.moddalar(db))[0]
        await k.modda_saqla(db, ijara.nom, D(250_000), True, ijara.id)
        b = {x.nom: (x.fakt, x.foiz) for x in await m.byudjet(db, today)}
        tek("Ijara 300 000 / limit 250 000 = 120 %", b["Ijara"], (D(300_000), 120))
        bos = await m.bosh(db)
        tek("bosh: byudjet vazifasi", any("Ijara" in v.matn and v.bolim == "byudjet" for v in bos.vazifalar), True)
        bl = await m.balans(db)
        tek("balans: aktiv − passiv = sof", bl.aktiv - bl.passiv, bl.sof)
        tek("balans: pul 1 894 000 ichida", bl.pul >= D(1_894_000), True)

        print("7) davr yopish")
        await rad("joriy oy yopilmaydi", m.davr_yop(db, today, u2.id), "tugagan oy")
        otgan = m.oy_boshi(m.oy_boshi(today) - timedelta(days=1))
        b4 = order("MS-4", 700_000, datetime.combine(otgan.replace(day=15), datetime.min.time(), m.TASHKENT_TZ))
        db.add(b4)
        dr = StockDoc(no="MCHQ-D", kind="chiqim", status="draft", doc_date=otgan.replace(day=20), head={"client": "x"})
        db.add(dr)
        await db.flush()
        await rad("qoralama bor — yopilmaydi", m.davr_yop(db, otgan, u2.id), "MCHQ-D")
        dr.doc_date = today
        await db.flush()
        await m.davr_yop(db, otgan, u2.id)
        b4.amount = D(800_000)
        await db.flush()
        tek(
            "yopilgan oy natijasi qotgan",
            (await m.pnl(db, otgan)).sotuv_buyurtma >= D(700_000) and (await m.pnl(db, otgan)).yopiq,
            True,
        )
        qotgan, jonli = (await m.pnl(db, otgan)).sotuv_buyurtma, (await m.pnl(db, otgan, qotgan=False)).sotuv_buyurtma
        tek("qotgan vs jonli farqi 100 000", jonli - qotgan, D(100_000))
        dr.doc_date = otgan.replace(day=20)
        await db.flush()
        await rad("yopiq oyga hujjat tasdiqlanmaydi", confirm(db, dr, u2.id), "oyi yopilgan", DocError)
        await m.davr_ochish_sorov(db, otgan, u1.id, "kirim kech kiritildi")
        await rad("so'ragan o'zi tasdiqlamaydi", m.davr_ochish_tasdiq(db, otgan, u1.id), "Ikki kalit")
        await m.davr_ochish_tasdiq(db, otgan, u2.id)
        tek(
            "qayta ochildi, natija jonli",
            ((await m.pnl(db, otgan)).yopiq, await m.davr_yopiq(db, otgan)),
            (False, False),
        )

        print("8) jurnal butun")
        tek(
            "kassa orderi o'chirilmagan (storno yangi qator)",
            await db.scalar(select(KassaOrder.id).where(KassaOrder.storno_of_id == kom.orderlar[0].id)) is not None,
            True,
        )
        _ = sm
        await db.rollback()
    print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")


asyncio.run(main())
