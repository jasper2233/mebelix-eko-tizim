"""Kromka o'lchovini detalga bog'lash — haqiqiy `POST /bridge-agents/andon`, haqiqiy Postgres.

Detal 430x520, TO'RT tomoni ham lentalanadi: kutilgan {520, 520, 430, 430}.
Tekshiriladi: tartib erkinligi, kvota, dopusk, ortiqcha o'tish, mos kelmagan o'lcham,
skansiz o'lchov, oynadan tashqaridagi skan, takror partiya, va eng muhimi —
KETMA-KET qo'yilgan detallar (stansiya egasi 2026-09-21 da prodda topgan xato:
o'lchov keyingi detalning skaniga yopishib qolardi).
"""

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, text

from app.api.routes.bridge_agents import push_andon_events
from app.api.routes.machines import read_kromka_measurement_feed
from app.api.routes.terminal import read_kromka_measurements
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
    SystemSetting,
    WorkSession,
)
from app.models.enums import KromkaVerdict, PostCode, PostUnit
from app.schemas.bridge_agents import AndonPush

HOZIR = datetime.now(UTC).replace(microsecond=0)


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    async with local_session() as db:
        for jadval in (
            "kromka_measurement", "part_defect", "scan", "work_session", "andon_event", "bridge_agent",
            "part_route", "part_instance", "part", "product", '"order"', "machine", "employee",
            "client", "post", "system_setting",
        ):
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
        db.add(SystemSetting(key="kromka_tolerance_mm", value="3"))
        db.add(SystemSetting(key="kromka_bind_window_s", value="60"))
        smena = WorkSession(employee_id=hodim.id, machine_id=stanok.id, post_id=post.id)
        buyurtma = Order(number="B-2026-001", client_id=mijoz.id)
        db.add_all([smena, buyurtma])
        await db.flush()
        mahsulot = Product(order_id=buyurtma.id, code="01", name="Shkaf", count=1)
        db.add(mahsulot)
        await db.flush()
        kromkali = {"t": {"mat": "PVC"}, "b": {"mat": "PVC"}, "l": {"mat": "PVC"}, "r": {"mat": "PVC"}}
        detal = Part(order_id=buyurtma.id, product_id=mahsulot.id, code="01_001", name="Yon",
                     count=3, length=520, width=430, thickness=16, edges=kromkali)
        # Ikki tomoni lentalanadigan detal (faqat uzunlik guruhi)
        detal2 = Part(order_id=buyurtma.id, product_id=mahsulot.id, code="01_002", name="Tokcha",
                      count=1, length=600, width=300, thickness=16,
                      edges={"t": {"mat": "PVC"}, "b": {"mat": "PVC"}})
        db.add_all([detal, detal2])
        await db.flush()
        nusxa1 = PartInstance(order_id=buyurtma.id, part_id=detal.id, instance_no=1, qr_text="B-2026-001_01_001_1")
        nusxa2 = PartInstance(order_id=buyurtma.id, part_id=detal.id, instance_no=2, qr_text="B-2026-001_01_001_2")
        nusxa3 = PartInstance(order_id=buyurtma.id, part_id=detal2.id, instance_no=1, qr_text="B-2026-001_01_002_1")
        qadam = PartRoute(order_id=buyurtma.id, part_id=detal.id, post_id=post.id, seq=1, process_code=2)
        qadam2 = PartRoute(order_id=buyurtma.id, part_id=detal2.id, post_id=post.id, seq=1, process_code=2)
        db.add_all([nusxa1, nusxa2, nusxa3, qadam, qadam2])
        await db.flush()

        def skan(nusxa, route, at, bekor=False):
            row = Scan(order_id=buyurtma.id, part_id=nusxa.part_id, instance_id=nusxa.id, route_id=route.id,
                       post_id=post.id, machine_id=stanok.id, employee_id=hodim.id, session_id=smena.id,
                       client_event_id=uuid4().hex, is_cancelled=bekor, created_at=at)
            db.add(row)
            return row

        seq = [0]

        async def olchov(L, at, kod="OK", ish_ms=0):
            """Bitta o'lchovni AGENT yuborgandek jo'natadi (`ish_ms` — D1→D2 yurish vaqti)."""
            seq[0] += 1
            ev = {"type": "olchov", "session": "s1", "seq": seq[0], "ts": int(at.timestamp()),
                  "ev": "olchov", "L": L, "kod": kod, "v_nom": 18, "v_olch": 18.1,
                  "ish_ms": ish_ms}
            return await push_andon_events(db, AndonPush(events=[ev]), authorization=f"Bearer {token}")

        async def oxirgi() -> KromkaMeasurement:
            return (await db.execute(
                select(KromkaMeasurement).order_by(KromkaMeasurement.id.desc()).limit(1)
            )).scalar_one()

        # --- 1) Skan, so'ng to'rt tomon. Tartib ERKIN: avval eni, keyin uzunlik.
        # Har o'tishda operator qirrani lentaga qo'yadi, detal 8 soniyada o'tadi.
        BOSH = HOZIR - timedelta(minutes=5)
        skan(nusxa1, qadam, BOSH)
        await db.commit()
        await olchov(430.0, BOSH + timedelta(seconds=8), ish_ms=8000)
        r = await oxirgi()
        natija.append(("eni birinchi o'tsa ham mos", (r.verdict, r.side_group), (KromkaVerdict.MOS, "width")))
        await olchov(521.5, BOSH + timedelta(seconds=16), ish_ms=8000)   # dopusk ichida (3 mm)
        r = await oxirgi()
        natija.append(("dopusk ichidagi farq mos", (r.verdict, r.side_group, float(r.delta_mm)),
                       (KromkaVerdict.MOS, "length", 1.5)))
        await olchov(428.0, BOSH + timedelta(seconds=24), ish_ms=8000)
        await olchov(520.0, BOSH + timedelta(seconds=30), ish_ms=8000)
        natija.append(("to'rt tomon yopildi", (await oxirgi()).verdict, KromkaVerdict.MOS))

        # --- 2) Beshinchi o'tish: o'lcham to'g'ri, kvota tugagan => OGOHLANTIRISH
        await olchov(520.0, BOSH + timedelta(seconds=36), ish_ms=8000)
        r = await oxirgi()
        natija.append(("kvota tugagach ortiqcha", (r.verdict, r.side_group), (KromkaVerdict.ORTIQCHA, "length")))
        natija.append(("ortiqcha brak emas", r.verdict != KromkaVerdict.NOMOS, True))

        # --- 3) Mos kelmagan o'lcham => NOMOS (terminal brak oynasini ochadi)
        IKKI = HOZIR - timedelta(minutes=3)
        skan(nusxa2, qadam, IKKI)
        await db.commit()
        await olchov(300.0, IKKI + timedelta(seconds=10), ish_ms=8000)
        r = await oxirgi()
        natija.append(("mos kelmagan o'lcham", r.verdict, KromkaVerdict.NOMOS))
        natija.append(("eng yaqin kutilgan ko'rsatiladi", (float(r.expected_mm), float(r.delta_mm)), (430.0, -130.0)))
        natija.append(("brak oynasi uchun skan bor", r.scan_id is not None, True))
        natija.append(("NOMOS qirrani yopmaydi", r.side_group, None))
        await olchov(520.0, IKKI + timedelta(seconds=18), ish_ms=8000)
        natija.append(("NOMOS dan keyin ham uzunlik ochiq", (await oxirgi()).verdict, KromkaVerdict.MOS))

        # --- 4) Ikki tomonlama detal: eni o'lchovi kutilmaydi => NOMOS
        UCH = HOZIR - timedelta(minutes=2)
        skan(nusxa3, qadam2, UCH)
        await db.commit()
        await olchov(600.0, UCH + timedelta(seconds=8), ish_ms=8000)
        natija.append(("lentalanadigan tomon mos", (await oxirgi()).verdict, KromkaVerdict.MOS))
        await olchov(300.0, UCH + timedelta(seconds=16), ish_ms=8000)
        r = await oxirgi()
        natija.append(("lentalanmaydigan tomon kutilmaydi", (r.verdict, float(r.expected_mm)),
                       (KromkaVerdict.NOMOS, 600.0)))

        # --- 5) Pico kodi OK emas => hukm yo'q
        await olchov(None, UCH + timedelta(seconds=24), kod="FAQAT1")
        r = await oxirgi()
        natija.append(("kod OK emas — shubhali", (r.verdict, r.measured_mm, r.scan_id),
                       (KromkaVerdict.SHUBHALI, None, None)))

        # --- 6) Nusxa bo'yicha hisob (skan jadvali tozalanishidan OLDIN)
        yopilgan = (await db.execute(
            select(KromkaMeasurement.side_group)
            .where(KromkaMeasurement.instance_id == nusxa1.id, KromkaMeasurement.verdict == KromkaVerdict.MOS)
        )).scalars().all()
        natija.append(("1-nusxada 4 qirra yopildi", sorted(yopilgan),
                       ["length", "length", "width", "width"]))

        # --- 6b) Ekranlar shu hukmni ko'radimi (terminal tasmasi va admin oqimi)
        tasma = await read_kromka_measurements(db, None, (stanok, post))
        natija.append(("terminal tasmasida hukm bor", tasma[0].verdict in
                       {"mos", "nomos", "ortiqcha", "shubhali", "skanersiz"}, True))
        oqim = await read_kromka_measurement_feed(db, None)
        mos_qatori = next((r for r in oqim if r.verdict == "mos"), None)
        natija.append(("admin oqimida detal nomi ko'rinadi",
                       (mos_qatori.part_name, mos_qatori.machine_name) if mos_qatori else None,
                       ("Tokcha", "Kromka-1")))
        nomos_qatori = next((r for r in oqim if r.verdict == "nomos"), None)
        natija.append(("admin oqimida kutilgan o'lcham ko'rinadi",
                       nomos_qatori.expected_mm if nomos_qatori else None, 600.0))

        # --- 6c) KETMA-KET DETALLAR (stansiya egasi prodda topgan xato)
        # Operator har 5 soniyada bitta detalni skanerlab lentaga qo'yadi, lenta esa
        # har detalni 15 soniyada o'tkazadi. Demak endi kelgan o'lchov 3 ta skan
        # OLDINGI detalniki. Oxirgi skanga bog'lansa — har detal xato o'lchanardi.
        nusxa_qator = [
            PartInstance(order_id=buyurtma.id, part_id=detal.id, instance_no=10 + i,
                         qr_text=f"B-2026-001_01_001_{10 + i}")
            for i in range(4)
        ]
        db.add_all(nusxa_qator)
        await db.flush()
        t0 = HOZIR - timedelta(minutes=5)
        skanlar = []
        for i, nusxa in enumerate(nusxa_qator):
            skanlar.append(skan(nusxa, qadam, t0 + timedelta(seconds=i * 5)))
        await db.commit()
        # O'lchovlar: har biri o'z detali kirganidan 15 s keyin chiqadi
        for i in range(4):
            await olchov(520.0, t0 + timedelta(seconds=i * 5 + 15), ish_ms=15000)
        oxirgi_tort = (await db.execute(
            select(KromkaMeasurement.scan_id, KromkaMeasurement.verdict)
            .order_by(KromkaMeasurement.id.desc()).limit(4)
        )).all()
        natija.append(("ketma-ket detallar TO'G'RI skanga bog'landi",
                       sorted(r[0] for r in oxirgi_tort), [s.id for s in skanlar]))
        natija.append(("har biri o'z o'lchamiga mos", {r[1] for r in oxirgi_tort}, {KromkaVerdict.MOS}))
        # Eski model (oxirgi skan) bo'lsa hammasi OXIRGI skanga yopishardi
        natija.append(("hammasi bitta skanga yopishib qolmadi",
                       len({r[0] for r in oxirgi_tort}), 4))

        # --- 7) Oynadan tashqaridagi skan bog'lanmaydi
        # DIQQAT: TRUNCATE scan CASCADE o'lchovlarni ham o'chiradi — hisob yuqorida olindi
        await db.execute(text("TRUNCATE scan RESTART IDENTITY CASCADE"))
        skan(nusxa1, qadam, HOZIR - timedelta(minutes=30))
        await db.commit()
        await olchov(520.0, HOZIR - timedelta(seconds=5), ish_ms=8000)
        r = await oxirgi()
        natija.append(("oynadan tashqaridagi skan bog'lanmaydi", r.verdict, KromkaVerdict.SKANERSIZ))

        # --- 7) Bekor qilingan skan ham bog'lanmaydi
        await db.execute(text("TRUNCATE scan RESTART IDENTITY CASCADE"))
        skan(nusxa1, qadam, HOZIR - timedelta(seconds=15), bekor=True)
        await db.commit()
        await olchov(520.0, HOZIR, ish_ms=8000)
        natija.append(("bekor qilingan skan bog'lanmaydi", (await oxirgi()).verdict, KromkaVerdict.SKANERSIZ))

        # --- 8) Agent partiyani QAYTA yuborsa kvota ikkinchi marta yopilmaydi
        oldin = len((await db.execute(select(KromkaMeasurement))).scalars().all())
        takror = await push_andon_events(
            db,
            AndonPush(events=[{"type": "olchov", "session": "s1", "seq": 1,
                               "ts": int((HOZIR - timedelta(minutes=4)).timestamp()),
                               "ev": "olchov", "L": 430.0, "kod": "OK"}]),
            authorization=f"Bearer {token}",
        )
        keyin = len((await db.execute(select(KromkaMeasurement))).scalars().all())
        natija.append(("takror hodisa qayta bog'lanmaydi", (takror.accepted, takror.duplicates, keyin - oldin),
                       (0, 1, 0)))

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
