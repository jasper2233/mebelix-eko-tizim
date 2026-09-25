"""Stanok taxtasi (`GET /tablo/machines`) — haqiqiy handler, haqiqiy Postgres.

Kun: smena 08:00-17:00. Kromka-1 da lenta 08:00-16:00 ishladi, 40 ta o'tish,
bittasi brak. Prisadka da hodisa YO'Q (Pico ulanmagan) — taxtaga tushmasligi kerak.
Rover-1 da hodisa bor, lekin smena ochilmagan va bitta to'xtash sababsiz.
"""

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import text

from app.api.routes.reports import report_machine_time
from app.api.routes.tablo import read_tablo_machine, read_tablo_machines
from app.core.config import TASHKENT_TZ
from app.core.db import local_session
from app.models import (
    AndonEvent,
    Client,
    Downtime,
    DowntimeReason,
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
from app.models.enums import DowntimeKind, KromkaVerdict, PostCode, PostUnit, UserRole

BUGUN = datetime.now(TASHKENT_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
T = lambda h, m=0, s=0: BUGUN + timedelta(hours=h, minutes=m, seconds=s)  # noqa: E731


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

        db.add(SystemSetting(key="stop_prompt_idle_minutes", value="5"))
        db.add(SystemSetting(
            key="work_schedule",
            value='{"shifts":[{"name":"Kunduzi","start":"08:00","end":"17:00","breaks":[]}],'
                  '"days_off":[],"holidays":[]}'))
        kromka_post = Post(code=PostCode.KROMKA, name="Kromka", order_index=2, unit=PostUnit.METER)
        rover_post = Post(code=PostCode.ROVER, name="Rover", order_index=6, unit=PostUnit.PIECE)
        prisadka_post = Post(code=PostCode.PRISADKA, name="Prisadka", order_index=7, unit=PostUnit.PIECE)
        db.add_all([kromka_post, rover_post, prisadka_post])
        await db.flush()
        kromka = Machine(name="Kromka-1", post_id=kromka_post.id)
        rover = Machine(name="Rover-1", post_id=rover_post.id)
        prisadka = Machine(name="Prisadka", post_id=prisadka_post.id)  # Pico YO'Q
        hodim = Employee(full_name="Ikromov Samariddin", badge_id=uuid4().hex, assigned_post_ids=[kromka_post.id])
        mijoz = Client(full_name="Mijoz")
        admin = User(username="admin", phone="+998900000003", hashed_password="x",
                     name="Admin", role=UserRole.ADMIN)
        db.add_all([kromka, rover, prisadka, hodim, mijoz, admin])
        await db.flush()
        smena = WorkSession(employee_id=hodim.id, machine_id=kromka.id, post_id=kromka_post.id)
        buyurtma = Order(number="B-2026-001", client_id=mijoz.id)
        db.add_all([smena, buyurtma])
        await db.flush()
        smena.created_at = T(8)
        mahsulot = Product(order_id=buyurtma.id, code="01", name="Shkaf", count=1)
        db.add(mahsulot)
        await db.flush()
        detal = Part(order_id=buyurtma.id, product_id=mahsulot.id, code="01_001", name="Yon", count=10,
                     length=520, width=430, thickness=16,
                     edges={k: {"mat": "PVC"} for k in ("t", "b", "l", "r")})
        db.add(detal)
        await db.flush()
        qadam = PartRoute(order_id=buyurtma.id, part_id=detal.id, post_id=kromka_post.id, seq=1,
                          process_code=2, per_instance=4, total_required=40)
        nusxalar = [
            PartInstance(order_id=buyurtma.id, part_id=detal.id, instance_no=i + 1,
                         qr_text=f"B-2026-001_01_001_{i + 1}")
            for i in range(10)
        ]
        db.add_all([qadam, *nusxalar])
        await db.flush()

        seq = 0

        def hodisa(m, kind, payload, at):
            nonlocal seq
            seq += 1
            db.add(AndonEvent(machine_id=m.id, session="s1", seq=seq, kind=kind,
                              happened_at=at, payload=payload))

        # Kromka: 08:00-16:00 ishladi, 40 o'tish; bittasi brak
        hodisa(kromka, "uskuna", {"ev": "uskuna", "holat": 1}, T(8))
        hodisa(kromka, "uskuna", {"ev": "uskuna", "holat": 0}, T(16))
        for i in range(40):
            at = T(8) + timedelta(seconds=i * 60)
            hodisa(kromka, "olchov", {"ev": "olchov", "L": 520.0, "kod": "OK", "v_nom": 18}, at)
            skan = Scan(order_id=buyurtma.id, part_id=detal.id, instance_id=nusxalar[i // 4].id,
                        route_id=qadam.id, post_id=kromka_post.id, machine_id=kromka.id,
                        employee_id=hodim.id, session_id=smena.id, client_event_id=uuid4().hex,
                        created_at=at)
            db.add(skan)
            # Oxirgi o'tish kutilgan tomonga MOS KELMADI — kartada «1 mos emas» chiqishi kerak
            nomos = i == 39
            db.add(KromkaMeasurement(
                machine_id=kromka.id, measured_at=at, code="OK",
                verdict=KromkaVerdict.NOMOS if nomos else KromkaVerdict.MOS,
                measured_mm=498.0 if nomos else 520.0, expected_mm=520.0,
                delta_mm=-22.0 if nomos else 0.0,
                side_group=None if nomos else "length"))
        await db.flush()
        brak_skan = (await db.execute(text("SELECT id FROM scan ORDER BY id LIMIT 1"))).scalar_one()
        db.add(PartDefect(order_id=buyurtma.id, part_id=detal.id, instance_id=nusxalar[0].id,
                          scan_id=brak_skan, machine_id=kromka.id, post_id=kromka_post.id,
                          employee_id=hodim.id, reason="Chipilgan", created_at=T(9)))
        # Rover: yoqildi va to'xtadi — sababsiz to'xtash
        hodisa(rover, "uskuna", {"ev": "uskuna", "holat": 1}, T(8))
        hodisa(rover, "uskuna", {"ev": "uskuna", "holat": 0}, T(9))
        hodisa(rover, "uskuna", {"ev": "uskuna", "holat": 1}, T(10))
        db.add(Downtime(machine_id=rover.id, kind=DowntimeKind.OFF, started_at=T(9), ended_at=T(10),
                        start_key="s1-2"))
        db.add(DowntimeReason(name="Nosozlik", is_planned=False))
        await db.commit()

        # Redis'dagi jonli holat oraklga tegishli emas (lokal demo yozib qo'ygan
        # bo'lishi mumkin) — shu ikki stanok uchun tozalab olamiz
        from redis.asyncio import Redis as AsyncRedis

        from app.core.config import settings
        from app.services.andon import ANDON_LIVE_KEY

        async with AsyncRedis.from_url(settings.REDIS_URL) as redis:
            await redis.delete(*(ANDON_LIVE_KEY.format(m.id) for m in (kromka, rover, prisadka)))

        qatorlar = await read_tablo_machines(db, admin)
        nomlar = [r.machine_name for r in qatorlar]
        natija.append(("faqat Pico ulanganlari", sorted(nomlar), ["Kromka-1", "Rover-1"]))

        k = next(r for r in qatorlar if r.machine_name == "Kromka-1")
        rv = next(r for r in qatorlar if r.machine_name == "Rover-1")

        # Raqamlar hisobotning AYNAN o'zidan bo'lishi kerak
        hisobot = await report_machine_time(db, admin, date_from=BUGUN.date(), date_to=BUGUN.date())
        h = next(r for r in hisobot.rows if r.machine_id == k.machine_id)
        natija.append(("Availability hisobot bilan bir xil", k.availability_pct, h.availability_pct))
        natija.append(("Performance hisobot bilan bir xil", k.performance_pct, h.performance_pct))
        natija.append(("Quality hisobot bilan bir xil", k.quality_pct, h.quality_pct))
        natija.append(("OEE hisobot bilan bir xil", k.oee_pct, h.oee_pct))
        natija.append(("detal va brak", (k.parts, k.defects), (h.parts, h.defects)))
        natija.append(("to'xtash = rejasiz + ma'lumotsiz", k.stop_s, h.unplanned_stop_s + h.no_data_s))

        natija.append(("post nomi", k.post_name, "Kromka"))
        natija.append(("smenadagi hodim", k.crew, ["Ikromov Samariddin"]))
        natija.append(("smena ochilmagan stanok bo'sh", rv.crew, []))
        natija.append(("oxirgi o'lchov kartada", (k.last_mm, k.last_verdict), (498.0, "nomos")))
        natija.append(("mos / mos emas hisobi", (k.mos_count, k.nomos_count), (39, 1)))
        natija.append(("roverda o'lchov hisobi bo'sh", (rv.mos_count, rv.nomos_count), (0, 0)))
        natija.append(("roverda o'lchov yo'q", (rv.last_mm, rv.last_verdict), (None, None)))
        natija.append(("sababsiz to'xtash sanaldi", rv.pending_reasons, 1))
        natija.append(("kromkada sababsiz to'xtash yo'q", k.pending_reasons, 0))
        # Redis'da jonli holat yo'q — bu «o'chiq» EMAS, «aloqa yo'q»
        natija.append(("jonli holat yo'q bo'lsa None", (k.state, k.since), (None, None)))
        # Smena BOSHLANMAGAN bo'lsa (orakl 08:00 dan oldin yurgizilgan) oyna bo'sh:
        # `plan_windows` hozirgi lahzada kesiladi, ya'ni 07:00 da hali hech narsa yo'q
        kutilgan_oyna = T(8) if datetime.now(TASHKENT_TZ) >= T(8) else None
        natija.append(("hisob qaysi lahzadan beri", k.window_from, kutilgan_oyna))

        # --- Kartani bosganda ochiladigan oyna
        tafsilot = await read_tablo_machine(db, admin, k.machine_id)
        natija.append(("uch davr", [p.label for p in tafsilot.periods], ["Bugun", "7 kun", "30 kun"]))
        bugungi = tafsilot.periods[0]
        natija.append(("bugungi davr karta bilan bir xil",
                       (bugungi.availability_pct, bugungi.oee_pct, bugungi.parts, bugungi.defects),
                       (k.availability_pct, k.oee_pct, k.parts, k.defects)))
        natija.append(("haftalik reja kunlikdan katta", tafsilot.periods[1].planned_s > bugungi.planned_s, True))
        natija.append(("oylik reja haftalikdan katta",
                       tafsilot.periods[2].planned_s > tafsilot.periods[1].planned_s, True))
        natija.append(("oxirgi ishlar ro'yxati", len(tafsilot.recent_scans), 15))
        natija.append(("eng yangisi birinchi",
                       tafsilot.recent_scans[0].at > tafsilot.recent_scans[-1].at, True))
        natija.append(("ishda detal nomi va chek ID si",
                       (tafsilot.recent_scans[0].part_name, tafsilot.recent_scans[0].employee),
                       ("Yon", "Ikromov Samariddin")))
        natija.append(("brak ro'yxati",
                       [(d.reason, d.status) for d in tafsilot.defects], [("Chipilgan", "pending")]))
        natija.append(("kromkada to'xtash yo'q", tafsilot.stops, []))

        rover_tafsilot = await read_tablo_machine(db, admin, rv.machine_id)
        natija.append(("roverda to'xtash ko'rinadi",
                       [(t.kind, t.seconds, t.reason) for t in rover_tafsilot.stops],
                       [("off", 3600, None)]))
        natija.append(("roverda ish va brak yo'q",
                       (len(rover_tafsilot.recent_scans), len(rover_tafsilot.defects)), (0, 0)))

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
