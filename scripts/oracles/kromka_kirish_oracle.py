"""Kromka: kirish vaqti `ts − (ish_ms + d2)` va asimmetrik oyna (−60 s … +20 s), FIFO.

HAQIQIY endpoint (`push_andon_events` → `kromka.bind_measurement`) HAQIQIY Postgres ustida.
Stansiya egasining qoidasi (`jasper2233/kromka-stansiya-OYY: docs/onlayn_mes_hodisalar.md` §5):
o'lchov detal D2 dan CHIQQANDA tayyor — kirish = o'lchov vaqti − (D1→D2 old qirralar orasi +
detal D2 ostidan o'tgan vaqt). Operator detalni lentaga qo'yishdan OLDIN skanerlaydi.

    1) 2000 mm detal, 10 m/min: ish_ms 15 s, d2 12 s. Operator 15 s OLDIN skanerlagan.
       To'g'ri kirish = o'lchov − 27 s → skan kirishdan 15 s oldin → «mos».
       Eski formula (faqat ish_ms) kirishni 12 s kech olardi → skan 27 s oldin → ±20 s
       oynadan tashqari → «skansiz».
    2) 45 s oldindan skanerlangan detal: eski ±20 s oynada yo'q, yangi −60 s da bor → «mos».
    3) FIFO: bir xil o'lchamli ikki detal 40 s va 10 s oldin skanerlangan — birinchi o'lchov
       ESKISIGA, ikkinchisi keyingisiga bog'lanadi.
    4) Kirishdan 70 s oldingi skan — oynadan tashqari → «skansiz» (oyna cheklangan).

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . /tmp/oee_test.env && set +a \\
      && uv run python ../scripts/oracles/kromka_kirish_oracle.py
"""

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, text

from app.api.routes.bridge_agents import push_andon_events
from app.core.db import local_session
from app.models import (
    BridgeAgent,
    Client,
    Employee,
    KromkaMeasurement,
    Machine,
    Order,
    Part,
    PartInstance,
    PartRoute,
    Post,
    Product,
    Scan,
    WorkSession,
)
from app.models.enums import KromkaVerdict, PostCode, PostUnit
from app.schemas.bridge_agents import AndonPush

HOZIR = datetime.now(UTC).replace(microsecond=0)


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    async with local_session() as db:
        for jadval in ("kromka_measurement", "scan", "work_session", "andon_event", "part_route", "part_instance",
                       "part", "product", '"order"', "bridge_agent", "machine", "employee", "client", "post",
                       "system_setting"):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()
        post = Post(code=PostCode.KROMKA, name="Kromka", order_index=1, unit=PostUnit.METER)
        db.add(post)
        await db.flush()
        stanok = Machine(name="Kromka-1", post_id=post.id)
        hodim = Employee(full_name="Ali Valiyev", badge_id=uuid4().hex, assigned_post_ids=[post.id])
        mijoz = Client(full_name="Mijoz")
        db.add_all([stanok, hodim, mijoz])
        await db.flush()
        token = uuid4().hex
        db.add(BridgeAgent(name="kromka-pc", token_hash=hashlib.sha256(token.encode()).hexdigest(),
                           machine_id=stanok.id))
        smena = WorkSession(employee_id=hodim.id, machine_id=stanok.id, post_id=post.id)
        buyurtma = Order(number="B-2026-050", client_id=mijoz.id)
        db.add_all([smena, buyurtma])
        await db.flush()
        mahsulot = Product(order_id=buyurtma.id, code="01", name="Shkaf", count=1)
        db.add(mahsulot)
        await db.flush()
        ikki_qirra = {"t": {"mat": "PVC"}, "b": {"mat": "PVC"}}
        uzun = Part(order_id=buyurtma.id, product_id=mahsulot.id, code="01_001", name="Yon",
                    count=1, length=2000, width=560, edges=ikki_qirra)
        tokcha = Part(order_id=buyurtma.id, product_id=mahsulot.id, code="01_002", name="Tokcha",
                      count=4, length=800, width=300, edges={"t": {"mat": "PVC"}})
        db.add_all([uzun, tokcha])
        await db.flush()
        qadam = PartRoute(order_id=buyurtma.id, part_id=uzun.id, post_id=post.id, seq=1, process_code=3)
        qadam2 = PartRoute(order_id=buyurtma.id, part_id=tokcha.id, post_id=post.id, seq=1, process_code=3)
        n_uzun = PartInstance(order_id=buyurtma.id, part_id=uzun.id, instance_no=1, qr_text="B-2026-050_01_001")
        n_tok = [PartInstance(order_id=buyurtma.id, part_id=tokcha.id, instance_no=i,
                              qr_text=f"B-2026-050_01_002_{i}") for i in range(1, 5)]
        db.add_all([qadam, qadam2, n_uzun, *n_tok])
        await db.flush()

        def skan(nusxa, route, at):
            row = Scan(order_id=buyurtma.id, part_id=nusxa.part_id, instance_id=nusxa.id, route_id=route.id,
                       post_id=post.id, machine_id=stanok.id, employee_id=hodim.id, session_id=smena.id,
                       client_event_id=uuid4().hex, created_at=at)
            db.add(row)
            return row

        seq = [0]

        async def olchov(L, at, ish_ms, d2_s, v=10):
            seq[0] += 1
            ev = {"type": "olchov", "session": "s1", "seq": seq[0], "ts": int(at.timestamp()),
                  "ev": "olchov", "L": L, "kod": "OK", "v_nom": v, "v_olch": v,
                  "ish_ms": ish_ms, "d2": int(d2_s * 1_000_000)}
            await push_andon_events(db, AndonPush(events=[ev]), authorization=f"Bearer {token}")
            return (await db.execute(
                select(KromkaMeasurement).order_by(KromkaMeasurement.id.desc()).limit(1))).scalar_one()

        # 1) Uzun detal: kirish = o'lchov − 27 s; skan kirishdan 15 s oldin
        kirish = HOZIR - timedelta(minutes=30)
        s1 = skan(n_uzun, qadam, kirish - timedelta(seconds=15))
        await db.commit()
        m = await olchov(2000.4, kirish + timedelta(seconds=27), ish_ms=15000, d2_s=12)
        natija.append(("uzun detal (d2 12 s) o'z skaniga bog'landi",
                       (m.verdict, m.scan_id), (KromkaVerdict.MOS, s1.id)))

        # 2) 45 s oldindan skanerlangan — eski ±20 s oynada yo'q edi
        kirish2 = HOZIR - timedelta(minutes=20)
        s2 = skan(n_tok[0], qadam2, kirish2 - timedelta(seconds=45))
        await db.commit()
        m = await olchov(800.2, kirish2 + timedelta(seconds=19), ish_ms=15000, d2_s=4.8)
        natija.append(("45 s oldindan skan topildi", (m.verdict, m.scan_id), (KromkaVerdict.MOS, s2.id)))

        # 3) FIFO: ikki bir xil detal 40 s va 10 s oldin skanerlangan
        kirish3 = HOZIR - timedelta(minutes=10)
        s3a = skan(n_tok[1], qadam2, kirish3 - timedelta(seconds=40))
        s3b = skan(n_tok[2], qadam2, kirish3 - timedelta(seconds=10))
        await db.commit()
        m_a = await olchov(799.8, kirish3 + timedelta(seconds=19.8), ish_ms=15000, d2_s=4.8)
        m_b = await olchov(800.1, kirish3 + timedelta(seconds=26), ish_ms=15000, d2_s=4.8)
        natija.append(("FIFO: birinchi o'lchov eski skanga, ikkinchisi keyingisiga",
                       (m_a.scan_id, m_b.scan_id), (s3a.id, s3b.id)))

        # 4) Kirishdan 70 s oldingi skan — oynadan tashqari
        kirish4 = HOZIR - timedelta(minutes=5)
        skan(n_tok[3], qadam2, kirish4 - timedelta(seconds=70))
        await db.commit()
        m = await olchov(800.0, kirish4 + timedelta(seconds=19.8), ish_ms=15000, d2_s=4.8)
        natija.append(("70 s oldingi skan oynadan tashqari — skansiz", (m.verdict, m.scan_id),
                       (KromkaVerdict.SKANERSIZ, None)))

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
