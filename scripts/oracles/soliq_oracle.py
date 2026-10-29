"""Soliq (EKO TZ §9) — HAQIQIY servislar HAQIQIY Postgres ustida; ESF operatori — lokal sinov operatori.

Rejim tarixi: o'tgan oy — aylanma 4 %, joriy oy — QQS 12 %.
Qo'lda hisob (joriy oy, narxlar QQS bilan):
  buyurtmalar: O1 1 120 000 (yuridik Y) → QQS 120 000; O3 560 000 (jismoniy J, ESF yo'q) → QQS 60 000
  do'kon:      hujjat: A 224 000 (standart) → QQS 24 000; B 100 000 (ozod) → 0
  aylanma 2 004 000; sotuv QQS 204 000; xarid QQS (kiruvchi 336 000) 36 000; to'lanadigan 168 000
  QQS kitobi: sotuv 2 ESF (120 000 + 24 000); ESF siz sotuv QQS 60 000
O'tgan oy: O4 2 000 000 yetkazilgan → aylanma soliq 80 000, QQS 0. P&L: joriy oy sof tushum = sotuv − 204 000,
o'tgan oy xarajatda aylanma soliq 80 000.
    cd backend && uv run python ../scripts/oracles/soliq_oracle.py
"""

import asyncio
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal as D

from sqlalchemy import select

from app.core.db import local_session
from app.models import Client, Order
from app.models.enums import OrderStatus
from app.modules.moliya import services as moliya
from app.modules.ombor.models import CatalogItem, StockDoc, StockDocLine
from app.modules.soliq import operator as op
from app.modules.soliq import services as s
from app.modules.soliq.models import SoliqEsf

natija: list[bool] = []


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


async def rad(nom: str, coro, bor: str) -> None:  # type: ignore[no-untyped-def]
    try:
        await coro
        tek(nom, "o'tib ketdi", f"rad: {bor}")
    except s.SoliqXato as e:
        tek(nom, bor in str(e), True)
        if bor not in str(e):
            print("     xabar:", e)


async def main() -> None:
    today = s.bugun()
    oy = today.replace(day=1)
    otgan = (oy - timedelta(days=1)).replace(day=1)
    now = datetime.now(UTC)
    async with local_session() as db:
        y = Client(full_name="Yuridik Mebel", phone="+998901110001")
        j = Client(full_name="Jismoniy Mijoz", phone="+998901110002")
        db.add_all([y, j])
        await db.flush()

        def order(no: str, c: Client, summa: int, delivered: datetime | None) -> Order:
            st = OrderStatus.DELIVERED if delivered else OrderStatus.PRODUCTION
            return Order(number=no, client_id=c.id, status=st, amount=D(summa), delivered_at=delivered)

        o1, o2, o3 = order("SL-1", y, 1_120_000, now), order("SL-2", y, 900_000, None), order("SL-3", j, 560_000, now)
        o4 = order("SL-4", y, 2_000_000, datetime.combine(otgan.replace(day=15), time(12), s.TASHKENT_TZ))
        db.add_all([o1, o2, o3, o4])
        items = list((await db.execute(select(CatalogItem).where(CatalogItem.catalog == "F").limit(2))).scalars())
        a, b = items
        doc = StockDoc(
            no="SL-CHQ-1",
            kind="chiqim",
            status="confirmed",
            doc_date=today,
            head={"client": "Yuridik Mebel"},
            total=D(324_000),
        )
        kirim = StockDoc(
            no="SL-KIR-1",
            kind="kirim",
            status="confirmed",
            doc_date=today,
            head={"supplier": "Ningbo MCHJ"},
            total=D(336_000),
        )
        db.add_all([doc, kirim])
        await db.flush()
        db.add(StockDocLine(doc_id=doc.id, line_no=1, item_id=a.id, name=a.name, qty=D(2), price=D(112_000)))
        db.add(StockDocLine(doc_id=doc.id, line_no=2, item_id=b.id, name=b.name, qty=D(1), price=D(100_000)))
        await db.flush()

        print("1) sozlama va rekvizitlar")
        await rad("rejimsiz/korxonasiz ESF", s.esf_buyurtmadan(db, o1.id, None), "rejimi sozlanmagan")
        k = await s.korxona(db)
        k.nomi, k.stir, k.buyurtma_mxik, k.buyurtma_birlik = "EKO Mebel MCHJ", "301234567", "94031000001000000", "796"
        await s.rejim_qosh(db, otgan, "aylanma", D(12), D(4), None)
        await s.rejim_qosh(db, oy, "qqs", D(12), D(4), None)
        tek(
            "rejim tarixi: o'tgan oy / joriy oy",
            ((await s.rejim_on(db, otgan)).rejim, (await s.rejim_on(db, today)).rejim),
            ("aylanma", "qqs"),
        )  # type: ignore[union-attr]
        await rad(
            "JShShIR 13 raqam", s.mijoz_saqla(db, j.id, {"yuridik": False, "jshshir": "1234567890123"}), "JShShIR 14"
        )
        await s.mijoz_saqla(db, j.id, {"yuridik": False, "jshshir": "31234567890123"})
        await rad("yuridiksiz ESF", s.esf_buyurtmadan(db, o1.id, None), "faqat yuridik")
        await s.mijoz_saqla(db, y.id, {"yuridik": True, "nomi": "Yuridik Mebel MCHJ", "stir": "207654321"})
        await rad("MXIK 16 raqam", s.mxik_saqla(db, a.id, "1234567890123456", "796", "standart"), "MXIK 17")

        print("2) ESF buyurtmadan")
        e1 = await s.esf_buyurtmadan(db, o1.id, None)
        tek("O1: summa / QQS / jami", (e1.summa, e1.qqs, e1.jami), (D(1_000_000), D(120_000), D(1_120_000)))
        await rad("takror ESF", s.esf_buyurtmadan(db, o1.id, None), "allaqachon")
        await rad("yetkazilmagan", s.esf_buyurtmadan(db, o2.id, None), "yetkazilmagan")
        await rad("jismoniy shaxsga ESF", s.esf_buyurtmadan(db, o3.id, None), "faqat yuridik")
        o4e = await s.esf_buyurtmadan(db, o4.id, None)
        tek(
            "o'tgan oy (aylanma) ESF: QQS yo'q",
            (o4e.rejim, o4e.qqs, o4e.qatorlar[0]["qqs_foiz"]),
            ("aylanma", D(0), None),
        )

        print("3) ESF ombor sotuvidan")
        await s.mxik_saqla(db, a.id, "11111111111111111", "796", "standart")
        await rad("MXIK siz pozitsiya", s.esf_hujjatdan(db, doc.id, y.id, None), "MXIK yo'q")
        await s.mxik_saqla(db, b.id, "22222222222222222", "796", "ozod")
        e2 = await s.esf_hujjatdan(db, doc.id, y.id, None)
        tek(
            "qatorlar: A QQS 24 000, B ozod 0",
            [(q["qqs"], q["ozod"]) for q in e2.qatorlar],
            [("24000.00", False), ("0", True)],
        )

        print("4) navbat, operator uzilishi, qabul")
        await s.navbatga(db, e1.id)
        await s.navbatga(db, e2.id)
        asl = op.SinovOperator.yubor

        async def ishlamaydi(self, db, hujjat):  # type: ignore[no-untyped-def]
            raise op.OperatorXato("operator javob bermadi")

        op.SinovOperator.yubor = ishlamaydi  # type: ignore[method-assign]
        n = await s.ishlov(db)
        tek(
            "uzilishda: navbatda qoladi, keyingi urinish 1 daqiqadan",
            (n.xato, e1.holat, e1.urinish, e1.keyingi_urinish is not None),
            (2, "navbatda", 1, True),
        )
        op.SinovOperator.yubor = asl  # type: ignore[method-assign]
        n = await s.ishlov(db)
        tek("vaqti kelmagan — yuborilmaydi", n.yuborildi, 0)
        e1.keyingi_urinish = e2.keyingi_urinish = now - timedelta(seconds=1)
        n = await s.ishlov(db)
        tek(
            "operator tiklandi: yuborildi → qabul",
            (n.yuborildi, e1.holat, e2.holat),
            (2, "qabul_qilindi", "qabul_qilindi"),
        )
        tek("operator id berildi", e1.operator_id is not None and e1.operator_id.startswith("SINOV-"), True)

        print("5) kiruvchi ESF")
        await s.sinov_kiruvchi(
            db,
            {
                "raqam": "NB-77",
                "sana": str(today),
                "sotuvchi": {"nomi": "ningbo  mchj", "stir": "200000001"},
                "xaridor": {"stir": k.stir},
                "qatorlar": [],
                "summa": "300000",
                "qqs": "36000",
                "jami": "336000",
            },
        )
        n = await s.ishlov(db)
        ki = (await db.execute(select(SoliqEsf).where(SoliqEsf.tur == "kiruvchi"))).scalar_one()
        tek(
            "kiruvchi olindi va kirim bilan bog'landi",
            (n.kiruvchi, ki.holat, ki.stock_doc_id),
            (1, "kutilmoqda", kirim.id),
        )
        await rad("sababsiz rad", s.kiruvchi_javob(db, ki.id, False, ""), "sababini")
        await s.kiruvchi_javob(db, ki.id, True, "")
        tek("qabul qilindi", ki.holat, "qabul_qilindi")
        await rad(
            "rejimni orqaga o'zgartirish", s.rejim_qosh(db, today, "aylanma", D(12), D(4), None), "yuborilgan ESF bor"
        )

        print("6) oylik soliq va QQS kitobi (qo'lda hisob)")
        t = await s.oy_soliq(db, today)
        tek(
            "aylanma: buyurtma / do'kon / jami",
            (t.buyurtma, t.dokon, t.aylanma),
            (D(1_680_000), D(324_000), D(2_004_000)),
        )
        tek(
            "QQS: sotuv / xarid / to'lanadigan",
            (t.sotuv_qqs, t.xarid_qqs, t.tolanadigan_qqs),
            (D(204_000), D(36_000), D(168_000)),
        )
        sotuv = await s.kitob(db, today, "chiquvchi")
        tek("sotuv kitobi: 2 ESF, QQS 144 000", (len(sotuv), sum(e.qqs for e in sotuv)), (2, D(144_000)))
        tek("ESF siz QQS (jismoniy) 60 000", t.sotuv_qqs - sum(e.qqs for e in sotuv), D(60_000))
        t0 = await s.oy_soliq(db, otgan)
        tek(
            "o'tgan oy: aylanma soliq 80 000, QQS 0",
            (t0.rejim, t0.aylanma_soliq, t0.sotuv_qqs),
            ("aylanma", D(80_000), D(0)),
        )

        print("7) P&L bilan bog'lanish")
        p = await moliya.pnl(db, today)
        tek("joriy oy: sotuvdagi QQS ayirildi", (p.sotuv_qqs, p.sof_tushum), (D(204_000), p.sotuv - D(204_000)))
        p0 = await moliya.pnl(db, otgan, qotgan=False)
        tek("o'tgan oy: aylanma soliq xarajatda", (p0.aylanma_soliq, p0.xarajat_jami >= D(80_000)), (D(80_000), True))

        print("8) bekor va qayta yozish")
        await s.bekor(db, e1.id)
        e1b = await s.esf_buyurtmadan(db, o1.id, None)
        tek("bekordan keyin yangi ESF", (e1.holat, e1b.holat, e1b.no != e1.no), ("bekor", "qoralama", True))
        await db.rollback()
    print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")


asyncio.run(main())
