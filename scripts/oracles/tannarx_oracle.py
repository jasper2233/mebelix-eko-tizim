"""Ishbay ish haqi (EKO 10a) — HAQIQIY servislar va HAQIQIY Postgres ustida.

Ssenariy: detal 600×400, 2 dona, kromka 3 tomonda (l, r, t). Arra (m²), kromka (metr), prisadka (dona) skanlari
uch kun oldin va ikki kun oldin; kromka stavkasi o'rtada o'zgaradi. Tekshiruvlar:
  1) hajm × stavka: arra 0.48 m², kromka 2.8 m (ikki stavkada), prisadka 1 dona (bekor skan sanalmaydi)
  2) stavkasi yo'q post — vedomost yaratilmaydi; bugungi kun, ustma-ust davr — rad
  3) ikki kalit; yozilgandan keyin skan bekor qilinsa — tasdiq rad, bekor + qayta
  4) tasdiqlangan davrga orqaga stavka — rad
  5) buyurtma mehnat tannarxi = vedomost jami; buxgalteriya D 2010 — K 6710, nazorat 6710 = vedomost − to'lov
  6) kassadan «Ish haqi (ishbay)» to'lovi P&L xarajatiga kirmaydi; P&L tannarxida mehnat bor
    cd backend && uv run python ../scripts/oracles/tannarx_oracle.py
"""

import asyncio
from datetime import datetime, time, timedelta
from decimal import Decimal as D
from uuid import uuid4

from sqlalchemy import select

from app.core.config import TASHKENT_TZ
from app.core.db import local_session
from app.models import (
    Client,
    Employee,
    Machine,
    Order,
    Part,
    PartInstance,
    PartRoute,
    Post,
    Product,
    Scan,
    User,
    WorkSession,
)
from app.models.enums import OrderStatus, PostCode, PostUnit, UserRole
from app.modules.buxgalteriya import services as b
from app.modules.kassa import services as k
from app.modules.moliya import services as moliya
from app.modules.tannarx import norma
from app.modules.tannarx import service as tf
from app.modules.tannarx import services as t

natija: list[bool] = []


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


async def rad(nom: str, coro, bor: str) -> None:  # type: ignore[no-untyped-def]
    try:
        await coro
        tek(nom, "o'tib ketdi", f"rad: {bor}")
    except t.TannarxXato as e:
        ok = bor in str(e)
        tek(nom, ok if ok else str(e), True)


async def main() -> None:
    today = t.bugun()
    d3, d2 = today - timedelta(days=3), today - timedelta(days=2)

    def vaqt(d, soat: int) -> datetime:  # type: ignore[no-untyped-def]
        return datetime.combine(d, time(soat), TASHKENT_TZ)

    async with local_session() as db:
        u1 = User(username="th1", name="Moliyachi", phone="+998900008101", hashed_password="x", role=UserRole.MOLIYACHI)
        u2 = User(username="th2", name="Direktor", phone="+998900008102", hashed_password="x", role=UserRole.DIRECTOR)
        cl = Client(full_name="Tannarx Mijoz", phone="+998900008103")
        db.add_all([u1, u2, cl])
        await db.flush()

        async def post(code: PostCode, nom: str, unit: PostUnit, i: int) -> Post:
            p = (await db.execute(select(Post).where(Post.code == code))).scalars().first()
            if p is None:
                p = Post(code=code, name=nom, order_index=i, unit=unit)
                db.add(p)
                await db.flush()
            return p

        arra = await post(PostCode.ARRA, "Arra", PostUnit.M2, 1)
        krom = await post(PostCode.KROMKA, "Kromka", PostUnit.METER, 2)
        pris = await post(PostCode.PRISADKA, "Prisadka", PostUnit.PIECE, 7)
        h1 = Employee(full_name="Aliyev Arra", badge_id=uuid4().hex, assigned_post_ids=[])
        h2 = Employee(full_name="Boboyev Kromka", badge_id=uuid4().hex, assigned_post_ids=[])
        pris_m = Machine(name="Prisadka-T", post_id=pris.id)
        db.add_all([h1, h2, pris_m])
        await db.flush()
        o = Order(number="TN-1", client_id=cl.id, status=OrderStatus.PRODUCTION, amount=D(5_000_000))
        db.add(o)
        await db.flush()
        pr = Product(order_id=o.id, code="01", name="Shkaf", count=1)
        db.add(pr)
        await db.flush()
        p = Part(
            order_id=o.id, product_id=pr.id, code="01_001", name="Yon", count=2, length=600, width=400,
            thickness=16, edges={"l": {}, "r": {}, "t": {}}, xnc_summary={"bores": 6, "grooves": 1},
        )
        db.add(p)
        await db.flush()
        ins = [PartInstance(order_id=o.id, part_id=p.id, instance_no=i, qr_text=f"TN-1_01_001_{i}") for i in (1, 2)]
        r_a = PartRoute(order_id=o.id, part_id=p.id, post_id=arra.id, seq=1, process_code=1, total_required=2)
        r_k = PartRoute(
            order_id=o.id, part_id=p.id, post_id=krom.id, seq=2, process_code=3, per_instance=3, total_required=6
        )
        r_p = PartRoute(order_id=o.id, part_id=p.id, post_id=pris.id, seq=3, process_code=6, total_required=2)
        db.add_all([*ins, r_a, r_k, r_p])
        await db.flush()
        ses = {}
        for h, po in ((h1, arra), (h2, krom), (h1, pris)):
            s = WorkSession(employee_id=h.id, post_id=po.id)
            db.add(s)
            await db.flush()
            ses[po.id] = s

        def skan(h: Employee, r: PartRoute, n: int, kun, bekor: bool = False) -> Scan:  # type: ignore[no-untyped-def]
            s = Scan(
                order_id=o.id, part_id=p.id, instance_id=ins[n % 2].id, route_id=r.id, post_id=r.post_id,
                employee_id=h.id, session_id=ses[r.post_id].id, client_event_id=uuid4().hex,
                machine_id=pris_m.id if r is r_p else None,
                created_at=vaqt(kun, 10) + timedelta(minutes=n), is_cancelled=bekor,
            )
            db.add(s)
            return s

        arra_skan = [skan(h1, r_a, i, d3) for i in range(2)]
        for i in range(3):
            skan(h2, r_k, i, d3)
            skan(h2, r_k, 10 + i, d2)
        skan(h1, r_p, 0, d2)
        skan(h1, r_p, 1, d2, bekor=True)
        await db.flush()

        print("1) stavkalar va hisob")
        await t.stavka_qosh(db, arra.id, None, D(10_000), today - timedelta(days=10), u1.id)
        await t.stavka_qosh(db, krom.id, None, D(2_000), today - timedelta(days=10), u1.id)
        await t.stavka_qosh(db, krom.id, None, D(3_000), d2, u1.id)
        await rad("o'sha sanaga takror stavka", t.stavka_qosh(db, krom.id, None, D(1), d2, u1.id), "allaqachon")
        dan, gacha = today - timedelta(days=5), today - timedelta(days=1)
        await rad("prisadka stavkasiz — vedomost yo'q", t.vedomost_yarat(db, dan, gacha, u1.id), "Stavka yo'q: Prisadka")
        await t.stavka_qosh(db, pris.id, None, D(5_000), today - timedelta(days=10), u1.id)
        h = {(x.employee_id, x.post_id): x for x in await t.skan_haqlari(db, dan, gacha)}
        tek("arra: 0.48 m² × 10 000", (h[(h1.id, arra.id)].hajm, h[(h1.id, arra.id)].summa), (D("0.480"), D("4800.00")))
        tek(
            "kromka: 2.8 m, 1.4 × 2 000 + 1.4 × 3 000",
            (h[(h2.id, krom.id)].hajm, h[(h2.id, krom.id)].summa),
            (D("2.800"), D("7000.00")),
        )
        tek("prisadka: bekor skan sanalmaydi", (h[(h1.id, pris.id)].skanlar, h[(h1.id, pris.id)].summa), (1, D("5000.00")))

        print("2) vedomost")
        await rad("bugungi kun bilan — rad", t.vedomost_yarat(db, dan, today, u1.id), "kechagi kun")
        v = await t.vedomost_yarat(db, dan, gacha, u1.id)
        tek("jami 16 800, skanlar 9", (v.jami, v.skanlar), (D("16800.00"), 9))
        await rad("ustma-ust davr", t.vedomost_yarat(db, d2, gacha, u1.id), "ustma-ust")

        print("3) ikki kalit va o'zgargan skan")
        await rad("yozgan o'zi tasdiqlay olmaydi", t.vedomost_tasdiq(db, v.id, u1.id), "Ikki kalit")
        arra_skan[0].is_cancelled = True
        await db.flush()
        await rad("skan bekor qilindi — tasdiq rad", t.vedomost_tasdiq(db, v.id, u2.id), "skanlar o'zgargan")
        await t.vedomost_bekor(db, v.id)
        v = await t.vedomost_yarat(db, dan, gacha, u1.id)
        tek("qayta: jami 14 400", v.jami, D("14400.00"))
        await t.vedomost_tasdiq(db, v.id, u2.id)
        await rad("tasdiqlangan bekor qilinmaydi", t.vedomost_bekor(db, v.id), "faqat qoralama")

        print("4) orqaga stavka")
        await rad("tasdiqlangan davrga stavka — rad", t.stavka_qosh(db, arra.id, None, D(1), d2, u1.id), "tasdiqlangan")

        print("5) tannarx va buxgalteriya")
        tek("buyurtma mehnati", await tf.buyurtma_mehnati(db, [o.id]), {o.id: D("14400.00")})
        await b.sinxron(db)
        tek("6710 kredit saldo", await b.saldo(db, "6710"), D("-14400.00"))
        N = k.Tolov
        await k.smena_och(db, {"100000": 1}, u1.id)
        await k.kirim(db, maqsad="avans", tolovlar=[N("naqd", D(100_000))], user_id=u1.id, order_id=o.id)
        await k.chiqim(
            db, maqsad="xarajat", hisob_kod="naqd", summa=D(10_000), user_id=u1.id, turkum="Ish haqi (ishbay)"
        )
        o.status, o.delivered_at = OrderStatus.DELIVERED, datetime.now(TASHKENT_TZ)
        await db.flush()
        await b.sinxron(db)
        tek("6710 qoldiq = 4 400", await b.saldo(db, "6710"), D("-4400.00"))
        tek("hamma nazorat 0", [x.nom for x in await b.nazorat(db) if x.farq.quantize(D("0.01")) != 0], [])

        print("6) P&L")
        pl = await moliya.pnl(db, today)
        tek("ish haqi to'lovi xarajatda yo'q", "Ish haqi (ishbay)" in {x.nom for x in pl.xarajatlar}, False)
        tek("tannarxda mehnat bor", pl.tannarx_buyurtma >= D("14400.00"), True)

        print("7) to'liq tannarx: stanok va asbob (norma, buxgalteriyaga yozilmaydi)")
        uzoq = today - timedelta(days=10)
        await norma.stanok_narx_qosh(db, pris_m.id, D(36_000), uzoq, u1.id)
        await rad("takror stanok narxi", norma.stanok_narx_qosh(db, pris_m.id, D(1), uzoq, u1.id), "allaqachon")
        for amal, n in (("teshik", 100), ("paz", 500), ("kromka_metr", 50)):
            await norma.asbob_stavka_qosh(db, amal, D(n), uzoq, u1.id)
        x = (await norma.buyurtma_tannarxi(db, [o.id]))[o.id]
        tek("stanok: (15 + 6*2 + 8) s * 36 000/soat = 350", (x.stanok, x.stanok_soat), (D("350.00"), D("0.01")))
        tek("arra normasi yo'q — kamchilik", "asbob: Arra m² (disk)" in x.kamchilik, True)
        await norma.asbob_stavka_qosh(db, "arra_m2", D(1_000), d3, u1.id)
        x = (await norma.buyurtma_tannarxi(db, [o.id]))[o.id]
        tek("asbob: 600 teshik + 500 paz + 2.8 m * 50 + 0.24 m² * 1 000", x.asbob, D("1480.00"))
        tek("mehnat 14 400, hammasi tasdiqlangan", (x.mehnat, x.mehnat_tasdiqlangan), (D("14400.00"), D("14400.00")))
        tek("jami = 14 400 + 350 + 1 480", (x.jami, x.kamchilik), (D("16230.00"), set()))
        s6710 = await b.saldo(db, "6710")
        await b.sinxron(db)
        farq = [n.nom for n in await b.nazorat(db) if n.farq.quantize(D("0.01"))]
        tek("norma buxgalteriyaga tushmadi", (await b.saldo(db, "6710"), farq), (s6710, []))
        await db.rollback()
    print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")


asyncio.run(main())
