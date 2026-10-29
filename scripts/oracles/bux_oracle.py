"""Buxgalteriya (EKO 7) — avtomatik provodkalar HAQIQIY servislar va HAQIQIY Postgres ustida.

Ssenariy (joriy oy): kassa (smena, avans, xarajat bankdan + komissiya, ta'minotchiga, o'tkazma, storno, kamomad),
ombor (kirim 500 000 va buyurtmaga sarf 100 000 — partiya bilan), buyurtma yetkazildi, QQS rejimi; o'tgan oy —
yetkazilgan buyurtma va yopilgan davr. Tekshiruvlar:
  1) sinxron yozadi, takror sinxron hech narsa yozmaydi
  2) NAZORAT: 5010/5710/5110 = kassa qoldiqlari, 1010 = ombor qiymati (seed ma'lumoti bilan birga),
     4010 = Moliya debitor (qarz − avans), 6010 = Moliya kreditor; aylanma-saldo har ustunda D = K
  3) oy natijasi (9xxx) = Moliya P&L sof foydasi (+ ombor tuzatishlari, ular P&L da yo'q)
  4) buyurtma summasi o'zgardi → tuzatish (daromad va QQS); qoida o'zgardi → qayta tasniflash
  5) yopilgan oydagi manba o'zgardi → tuzatish BUGUNGI sana bilan
  6) qo'lda provodka va uning stornosi (ikki kalit); jurnalni UPDATE — baza rad etadi
    cd backend && uv run python ../scripts/oracles/bux_oracle.py
"""

import asyncio
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal as D

from sqlalchemy import case, func, select, text
from sqlalchemy.exc import DBAPIError

from app.core.config import TASHKENT_TZ
from app.core.db import local_session
from app.models import Client, Order, User
from app.models.enums import OrderStatus, UserRole
from app.modules.buxgalteriya import services as b
from app.modules.buxgalteriya.models import BuxQoida, BuxYozuv
from app.modules.kassa import services as k
from app.modules.moliya import service as moliya_f
from app.modules.moliya import services as moliya
from app.modules.ombor.models import CatalogItem, StockDoc, StockLot, StockMovement
from app.modules.soliq import services as soliq

natija: list[bool] = []


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


async def rad(nom: str, coro, bor: str) -> None:  # type: ignore[no-untyped-def]
    try:
        await coro
        tek(nom, "o'tib ketdi", f"rad: {bor}")
    except b.BuxXato as e:
        tek(nom, bor in str(e), True)


async def main() -> None:
    today = b.bugun()
    oy = today.replace(day=1)
    otgan = (oy - timedelta(days=1)).replace(day=1)
    now = datetime.now(UTC)
    async with local_session() as db:
        u1 = User(username="bux1", name="Kassir", phone="+998900007101", hashed_password="x", role=UserRole.KASSIR)
        u2 = User(
            username="bux2", name="Buxgalter", phone="+998900007102", hashed_password="x", role=UserRole.MOLIYACHI
        )
        cl = Client(full_name="Bux Mijoz", phone="+998900007103")
        db.add_all([u1, u2, cl])
        await db.flush()
        o1 = Order(number="BX-1", client_id=cl.id, status=OrderStatus.PRODUCTION, amount=D(2_000_000))
        o2 = Order(
            number="BX-2",
            client_id=cl.id,
            status=OrderStatus.DELIVERED,
            amount=D(1_000_000),
            delivered_at=datetime.combine(otgan.replace(day=15), time(12), TASHKENT_TZ),
        )
        db.add_all([o1, o2])
        await db.flush()
        # Ombor: kirim 10 × 50 000 partiya bilan, keyin buyurtmaga 2 dona sarf (FIFO 100 000)
        it = (await db.execute(select(CatalogItem).where(CatalogItem.catalog == "M").limit(1))).scalar_one()
        kd = StockDoc(
            no="BX-KIR",
            kind="kirim",
            status="confirmed",
            doc_date=today,
            head={"supplier": "Supplier X"},
            total=D(500_000),
        )
        db.add(kd)
        await db.flush()
        lot = StockLot(item_id=it.id, doc_id=kd.id, received_on=today, qty=D(10), qty_left=D(8), unit_cost=D(50_000))
        db.add(lot)
        it.quantity += 8
        db.add(
            StockMovement(
                item_id=it.id, doc_id=kd.id, kind="kirim", qty=D(10), balance=it.quantity + 2, amount=D(500_000)
            )
        )
        db.add(
            StockMovement(item_id=it.id, kind="sarf", qty=D(-2), balance=it.quantity, amount=D(100_000), order_id=o1.id)
        )
        await soliq.rejim_qosh(db, oy, "qqs", D(12), D(4), None)
        await k.hisob_sozla(db, "bank", D(5_000_000), D("0.5"))
        N = k.Tolov
        await k.smena_och(db, {"100000": 10}, u1.id)
        await k.kirim(db, maqsad="avans", tolovlar=[N("naqd", D(800_000))], user_id=u1.id, order_id=o1.id)
        await k.chiqim(db, maqsad="xarajat", hisob_kod="bank", summa=D(1_000_000), user_id=u1.id, turkum="Ijara")
        kom = await k.chiqim(db, maqsad="xarajat", hisob_kod="naqd", summa=D(50_000), user_id=u1.id, turkum="Kommunal")
        await k.chiqim(
            db, maqsad="taminotchi", hisob_kod="naqd", summa=D(300_000), user_id=u1.id, kontragent="supplier x"
        )
        await k.otkazma(db, "naqd", "bank", D(200_000), u1.id)
        await k.storno(db, kom.orderlar[0].id, u2.id, "xato")
        await k.smena_yop(
            db, {"100000": 12, "50000": 1, "10000": 4}, None, u1.id
        )  # kutilgan 1 300 000, sanaldi 1 290 000
        o1.status, o1.delivered_at = OrderStatus.DELIVERED, now
        await db.flush()

        print("1) sinxron")
        n = await b.sinxron(db)
        tek("provodkalar yozildi", n.yozildi > 0, True)
        n = await b.sinxron(db)
        tek("takror sinxron — hech narsa", (n.yozildi, n.tuzatish), (0, 0))

        print("2) nazorat: buxgalteriya = modullar")
        for x in await b.nazorat(db):
            tek(f"{x.nom} (bux {x.buxgalteriya} / manba {x.manba})", x.farq.quantize(D("0.01")), D("0.00"))
        rows = await b.aylanma_saldo(db, oy, today)
        for col in ("bosh", "ayl", "yak"):
            sd = sum(getattr(r, f"{col}_d") for r in rows)
            sk = sum(getattr(r, f"{col}_k") for r in rows)
            tek(f"aylanma-saldo «{col}»: D = K", sd - sk, D(0))

        print("3) oy natijasi = Moliya P&L")
        bux = await b.oy_natija(db, today)
        adj = D(
            await db.scalar(
                select(
                    func.coalesce(
                        func.sum(
                            case((BuxYozuv.kredit.in_(("9390", "9430")), BuxYozuv.summa), else_=-BuxYozuv.summa)
                        ),
                        0,
                    )
                ).where(
                    BuxYozuv.guruh.like("sm:%"),
                    BuxYozuv.sana >= oy,
                    (BuxYozuv.debet.in_(("9390", "9430"))) | (BuxYozuv.kredit.in_(("9390", "9430"))),
                )
            )
            or 0
        )
        pnl = await moliya_f.pnl_sof(db, today)
        tek("9xxx natija − ombor tuzatishlari = P&L sof", (bux - adj).quantize(D("0.01")), pnl.quantize(D("0.01")))

        print("4) tuzatish va qayta tasniflash")
        s9010 = -await b.saldo(db, "9010")
        o1.amount = D(2_200_000)
        await db.flush()
        n = await b.sinxron(db)
        tek("summa +200 000: daromad va QQS tuzatildi", (n.yozildi, n.tuzatish), (2, 2))
        tek(
            "9010 o'sdi 200 000 − QQS (235 714.29 − 214 285.71 = 21 428.58)",
            (-await b.saldo(db, "9010") - s9010).quantize(D("0.01")),
            D("178571.42"),
        )
        db.add(BuxQoida(kalit="xarajat:Ijara", schyot="9410"))
        await db.flush()
        s9420 = await b.saldo(db, "9420")
        n = await b.sinxron(db)
        tek(
            "qoida Ijara → 9410: eski teskari + yangi",
            (n.yozildi, await b.saldo(db, "9420") - s9420, await b.saldo(db, "9410") >= D(1_000_000)),
            (2, D(-1_000_000), True),
        )

        print("5) yopilgan oy")
        await moliya.davr_yop(db, otgan, u2.id)
        o2.amount = D(1_100_000)
        await db.flush()
        await b.sinxron(db)
        oxirgi = (
            await db.execute(
                select(BuxYozuv).where(BuxYozuv.guruh == f"order:{o2.id}").order_by(BuxYozuv.id.desc()).limit(1)
            )
        ).scalar_one()
        tek(
            "o'tgan oy tuzatishi bugungi sana bilan",
            (oxirgi.sana, oxirgi.summa, oxirgi.izoh.startswith("Tuzatish")),
            (today, D(100_000), True),
        )

        print("6) qo'lda provodka")
        await rad(
            "noma'lum schyot",
            b.qolda(db, sana=today, debet="1234", kredit="6710", summa=D(1), izoh="x", user_id=u1.id),
            "schyoti yo'q",
        )
        y = await b.qolda(
            db, sana=today, debet="9420", kredit="6710", summa=D(3_000_000), izoh="Ish haqi hisoblandi", user_id=u1.id
        )
        await rad("o'zi storno — ikki kalit", b.storno(db, y.id, u1.id, "xato"), "Ikki kalit")
        await b.storno(db, y.id, u2.id, "noto'g'ri oy")
        tek("storno: 6710 saldo 0", await b.saldo(db, "6710"), D(0))
        avto = (await db.execute(select(BuxYozuv).where(BuxYozuv.guruh.is_not(None)).limit(1))).scalar_one()
        await rad("avtomatik provodka storno qilinmaydi", b.storno(db, avto.id, u2.id, "x"), "manba hujjatida")
        try:
            async with db.begin_nested():
                await db.execute(text("UPDATE bux_yozuv SET summa = 1"))
            tek("jurnal UPDATE rad", False, True)
        except DBAPIError as e:
            tek("jurnal UPDATE rad", "jurnal faqat qo'shiladi" in str(e), True)
        print("7) yakuniy nazorat")
        await b.sinxron(db)
        tek("hamma nazorat 0", [x.nom for x in await b.nazorat(db) if x.farq.quantize(D("0.01")) != 0], [])
        await db.rollback()
    print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")


asyncio.run(main())
