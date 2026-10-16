"""Brak — SKANNING xossasi: Quality skan vaqti/stanogida, tasdiq bekor qilgan ish sanalaveradi.

HAQIQIY handler (`report_machine_time`) va HAQIQIY `reopen_from_step` HAQIQIY Postgres ustida
(docs/12 §4.17). Kutilgan raqamlar qo'lda:

    Smena 08:00-17:00, tanaffus 12:00-13:00; Prisadka kun bo'yi ishlov (Pico)
    Marshrut: 1-qadam PRISADKA, 2-qadam KROMKA. 10 nusxa, Prisadka skanlari 09:00-09:09
    ideal: 15 + 6 teshik × 2 = 27 s → 10 detal = 270 s

    Prisadka braklari (hammasi skan qilingan detalga):
      - 2-nusxa: BRAK 12:03 da — TUSHLIKDA bosilgan          (eski kod: sanalmasdi)
      - 3-nusxa: BRAK ERTASI KUNI bosilgan                    (eski kod: kechaga tushmasdi)
      - 4-nusxa: BRAK boshqa stanok terminalidan (machine_id begona) (eski kod: begonaga tushardi)
    → Quality = (10 − 3) / 10 = 70.0%

    1-nusxa: brak KROMKA'da topildi, tasdiq PRISADKA (1-qadam) dan qayta ochdi →
    Prisadka skani bekor bo'ldi, LEKIN ish qilingan: Prisadka 10 detal / 270 s qoladi
    (eski kod: 9 / 243). Keyin «brak emas» deb rad etildi — baribir 10 / 270.

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . /tmp/oee_test.env && set +a \
      && uv run python ../scripts/oracles/defect_oracle.py
"""

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import text

from app.api.routes.reports import report_machine_time
from app.core.config import TASHKENT_TZ
from app.core.db import local_session
from app.models import (
    AndonEvent,
    Client,
    Employee,
    KromkaMeasurement,
    Machine,
    Order,
    Part,
    PartDefect,
    PartInstance,
    PartRoute,
    Post,
    Product,
    Scan,
    SystemSetting,
    User,
    WorkSession,
)
from app.models.enums import DefectStatus, KromkaVerdict, PostCode, PostUnit, UserRole
from app.services.defects import reopen_from_step
from app.services.kromka import _progress

KECHA = datetime.now(TASHKENT_TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
T = lambda h, m=0: KECHA + timedelta(hours=h, minutes=m)  # noqa: E731
JADVAL = ('{"shifts":[{"name":"Kunduzi","start":"08:00","end":"17:00",'
          '"breaks":[{"name":"Tushlik","start":"12:00","end":"13:00"}]}],"days_off":[],"holidays":[]}')


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    async with local_session() as db:
        for jadval in (
            "kromka_measurement", "part_defect", "scan", "work_session", "downtime", "downtime_reason",
            "andon_event", "part_route", "part_instance", "part", "product", '"order"',
            "machine", "employee", '"user"', "client", "post", "system_setting",
        ):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()
        db.add_all([SystemSetting(key="work_schedule", value=JADVAL),
                    SystemSetting(key="stop_prompt_idle_minutes", value="5")])
        pp = Post(code=PostCode.PRISADKA, name="Prisadka", order_index=7, unit=PostUnit.PIECE)
        kp = Post(code=PostCode.KROMKA, name="Kromka", order_index=2, unit=PostUnit.METER)
        db.add_all([pp, kp])
        await db.flush()
        pr = Machine(name="Prisadka", post_id=pp.id)
        pr2 = Machine(name="Prisadka-2", post_id=pp.id)
        kr = Machine(name="Kromka-1", post_id=kp.id)
        hodim = Employee(full_name="H", badge_id=uuid4().hex, assigned_post_ids=[])
        mijoz = Client(full_name="M")
        admin = User(username="admin", phone="+998900000001", hashed_password="x", name="A", role=UserRole.ADMIN)
        db.add_all([pr, pr2, kr, hodim, mijoz, admin])
        await db.flush()
        smena = WorkSession(employee_id=hodim.id, machine_id=pr.id, post_id=pp.id)
        buyurtma = Order(number="B-2026-040", client_id=mijoz.id)
        db.add_all([smena, buyurtma])
        await db.flush()
        mahsulot = Product(order_id=buyurtma.id, code="01", name="S", count=1)
        db.add(mahsulot)
        await db.flush()
        detal = Part(order_id=buyurtma.id, product_id=mahsulot.id, code="01_001", name="Yon", count=10,
                     length=900, width=430, xnc_summary={"bores": 6},
                     edges={"t": {"name": "K"}, "b": {"name": "K"}})
        db.add(detal)
        await db.flush()
        r1 = PartRoute(order_id=buyurtma.id, part_id=detal.id, post_id=pp.id, seq=1, process_code=6,
                       per_instance=1, total_required=10, total_done=10)
        r2 = PartRoute(order_id=buyurtma.id, part_id=detal.id, post_id=kp.id, seq=2, process_code=3,
                       per_instance=1, total_required=10, total_done=1)
        nusxalar = [PartInstance(order_id=buyurtma.id, part_id=detal.id, instance_no=i,
                                 qr_text=f"B-2026-040_01_001_{i}") for i in range(1, 11)]
        db.add_all([r1, r2, *nusxalar])
        await db.flush()
        # Prisadka kun bo'yi ishlov (Pico chiroq oraliqlari)
        db.add_all([
            AndonEvent(machine_id=pr.id, session="s", seq=1, kind="state", happened_at=T(12), state="PROCESSING",
                       prev_state="PROCESSING", prev_duration_s=4 * 3600, payload={}),
            AndonEvent(machine_id=pr.id, session="s", seq=2, kind="state", happened_at=T(17), state="PROCESSING",
                       prev_state="PROCESSING", prev_duration_s=5 * 3600, payload={}),
        ])

        def skan(nusxa, route, post, machine, at):
            s = Scan(order_id=buyurtma.id, part_id=detal.id, instance_id=nusxa.id, route_id=route.id,
                     post_id=post.id, machine_id=machine.id, employee_id=hodim.id, session_id=smena.id,
                     client_event_id=uuid4().hex, created_at=at)
            db.add(s)
            return s

        p_skan = [skan(n, r1, pp, pr, T(9, i)) for i, n in enumerate(nusxalar)]
        k_skan = skan(nusxalar[0], r2, kp, kr, T(10))
        await db.flush()

        def brak(s, machine, at, **kw):
            d = PartDefect(order_id=buyurtma.id, part_id=detal.id, instance_id=s.instance_id, scan_id=s.id,
                           machine_id=machine.id, post_id=s.post_id, reason="Skol", created_at=at, **kw)
            db.add(d)
            return d

        brak(p_skan[1], pr, T(12, 3))                                   # tushlikda bosilgan
        brak(p_skan[2], pr, T(9, 30) + timedelta(days=1))               # ertasi kuni
        brak(p_skan[3], pr2, T(9, 40))                                  # begona terminal stanogi
        kd = brak(k_skan, kr, T(10, 1), status=DefectStatus.CONFIRMED, restart_route_id=r1.id)
        await db.commit()

        hisobot = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=KECHA.date())
        p = next(x for x in hisobot.rows if x.machine_name == "Prisadka")
        natija.append(("tushlikdagi, ertangi va begona terminaldagi brak ham sanaladi", p.defects, 3))
        natija.append(("Quality = (10 − 3) / 10", p.quality_pct, 70.0))
        natija.append(("begona stanokka brak tushmadi",
                       [x.defects for x in hisobot.rows if x.machine_name == "Prisadka-2"], []))
        natija.append(("tasdiqdan oldin: Prisadka 10 detal / 270 s", (p.parts, p.ideal_s), (10, 270)))

        # 1-nusxa: Kromka'dagi brak tasdiqlandi, PRISADKA (1-qadam) dan qayta ochiladi
        await reopen_from_step(db, kd)
        await db.commit()
        await db.refresh(p_skan[0])
        natija.append(("tasdiq Prisadka skanini belgilab bekor qildi",
                       (p_skan[0].is_cancelled, p_skan[0].defect_id), (True, kd.id)))
        h2 = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=KECHA.date())
        p2 = next(x for x in h2.rows if x.machine_name == "Prisadka")
        natija.append(("tasdiqdan keyin ham Prisadka 10 detal / 270 s (ish qilingan)",
                       (p2.parts, p2.ideal_s), (10, 270)))

        kd.status = DefectStatus.REJECTED
        await db.commit()
        h3 = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=KECHA.date())
        p3 = next(x for x in h3.rows if x.machine_name == "Prisadka")
        natija.append(("«brak emas» deb rad etilsa ham 10 detal / 270 s", (p3.parts, p3.ideal_s), (10, 270)))

        # Kromka kvotasi: bekor qilingan skanga bog'langan «mos» o'lchov joyni band qilmaydi
        db.add(KromkaMeasurement(machine_id=kr.id, measured_at=T(10), code="OK", verdict=KromkaVerdict.MOS,
                                 measured_mm=900.0, scan_id=k_skan.id, instance_id=nusxalar[0].id,
                                 order_id=buyurtma.id, side_group="900"))
        await db.commit()
        kvota = await _progress(db, nusxalar[0].id, detal)
        natija.append(("kromka: bekor skandagi o'lchov kvotani yopmaydi",
                       sum(g["done"] for g in kvota.values()), 0))

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
