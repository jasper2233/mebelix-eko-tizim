"""ROVER (CNC 2130) OEE — Availability (IDLE qoidasi), Performance (kontur), Quality.

HAQIQIY handler (`report_machine_time`) va HAQIQIY to'xtash sinxroni (`sync_machine`)
HAQIQIY Postgres ustida. Kutilgan raqamlar qo'lda hisoblangan (docs/12 §4.15):

    Smena 08:00-17:00, tanaffus 12:00-13:00  →  reja = 8 soat = 28800 s

ROVER (`uskuna`, `manba="rover"`, `pwr` bilan):
    08:00 ishlov · 10:00-10:03 bo'sh turish (yoqiq, 3 daq — mikro, sanalmaydi)
    10:03 ishlov · 11:00-11:36 bo'sh turish (36 daq — to'xtash, 2160 s)
    11:36 ishlov · 12:00-13:00 o'chiq (tanaffus — ish vaqtidan tashqarida)
    13:00 ishlov · 15:00-16:00 o'chiq (3600 s) · 16:00 ishlov
    17:00-17:20 bo'sh turish · 17:20 o'chiq (smenadan keyin)
    to'xtash 5760 s → ishladi 23040 s → A = 80.0%
    40 detal 600×400 (perimetr 2 m) × (20 + 2 × 6) = 1280 s + 1 o'lchamsiz detal 20 s
    → ideal 1300 s → P = 1300 / 23040 = 5.6%
    4 brak (rad etilgani sanalmaydi) → Q = 37 / 41 = 90.2%  →  OEE = 80 × 5.6 × 90.2 / 10⁴ = 4.0%

NAZORAT stanogi (o'sha hodisalar `manba`/`pwr` SIZ — Kromka xulqi): har `holat=0` — OFF,
ya'ni 3 daqiqalik pauza ham to'xtash: 180 + 2160 + 3600 = 5940 s.

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . /tmp/oee_test.env && set +a \
      && uv run python ../scripts/oracles/rover_oee_oracle.py
"""

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select, text

from app.api.routes.reports import report_machine_time
from app.core.config import TASHKENT_TZ
from app.core.db import local_session
from app.models import (
    AndonEvent,
    Client,
    Downtime,
    Employee,
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
from app.models.enums import DefectStatus, DowntimeKind, PostCode, PostUnit, UserRole
from app.services.downtimes import sync_machine

KECHA = datetime.now(TASHKENT_TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
T = lambda h, m=0: KECHA + timedelta(hours=h, minutes=m)  # noqa: E731
JADVAL = ('{"shifts":[{"name":"Kunduzi","start":"08:00","end":"17:00",'
          '"breaks":[{"name":"Tushlik","start":"12:00","end":"13:00"}]}],"days_off":[],"holidays":[]}')

#: (vaqt, shpindel aylanyapti, stanok yoqiq)
REJA = [
    (T(8), 1, 1), (T(10), 0, 1), (T(10, 3), 1, 1), (T(11), 0, 1), (T(11, 36), 1, 1),
    (T(12), 0, 0), (T(13), 1, 1), (T(15), 0, 0), (T(16), 1, 1), (T(17), 0, 1), (T(17, 20), 0, 0),
]


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

        db.add_all([
            SystemSetting(key="work_schedule", value=JADVAL),
            SystemSetting(key="stop_prompt_idle_minutes", value="5"),
        ])
        rover_post = Post(code=PostCode.ROVER, name="Rover", order_index=6, unit=PostUnit.PIECE)
        kromka_post = Post(code=PostCode.KROMKA, name="Kromka", order_index=2, unit=PostUnit.METER)
        db.add_all([rover_post, kromka_post])
        await db.flush()
        rover = Machine(name="Rover-1", post_id=rover_post.id)
        nazorat = Machine(name="Kromka-1", post_id=kromka_post.id)
        hodim = Employee(full_name="Ikromov Samariddin", badge_id=uuid4().hex, assigned_post_ids=[])
        mijoz = Client(full_name="Mijoz")
        admin = User(username="admin", phone="+998900000001", hashed_password="x",
                     name="Admin", role=UserRole.ADMIN)
        db.add_all([rover, nazorat, hodim, mijoz, admin])
        await db.flush()
        smena = WorkSession(employee_id=hodim.id, machine_id=rover.id, post_id=rover_post.id)
        buyurtma = Order(number="B-2026-020", client_id=mijoz.id)
        db.add_all([smena, buyurtma])
        await db.flush()
        mahsulot = Product(order_id=buyurtma.id, code="01", name="Shkaf", count=1)
        db.add(mahsulot)
        await db.flush()
        eshik = Part(order_id=buyurtma.id, product_id=mahsulot.id, code="01_001", name="Eshik", count=40,
                     length=600, width=400, thickness=16)
        olchamsiz = Part(order_id=buyurtma.id, product_id=mahsulot.id, code="01_002", name="Bezak", count=1)
        db.add_all([eshik, olchamsiz])
        await db.flush()
        qadam = PartRoute(order_id=buyurtma.id, part_id=eshik.id, post_id=rover_post.id, seq=1,
                          process_code=7, per_instance=1, total_required=40)
        qadam2 = PartRoute(order_id=buyurtma.id, part_id=olchamsiz.id, post_id=rover_post.id, seq=1,
                           process_code=7, per_instance=1, total_required=1)
        nusxa = PartInstance(order_id=buyurtma.id, part_id=eshik.id, instance_no=1, qr_text="B-2026-020_01_001_1")
        nusxa2 = PartInstance(order_id=buyurtma.id, part_id=olchamsiz.id, instance_no=1,
                              qr_text="B-2026-020_01_002")
        db.add_all([qadam, qadam2, nusxa, nusxa2])
        await db.flush()

        for i, (at, run, pwr) in enumerate(REJA, 1):
            db.add(AndonEvent(machine_id=rover.id, session="a1", seq=i, kind="uskuna", happened_at=at,
                              payload={"type": "uskuna", "ev": "uskuna", "holat": run and pwr,
                                       "manba": "rover", "pwr": pwr, "run": run}))
            db.add(AndonEvent(machine_id=nazorat.id, session="k1", seq=i, kind="uskuna", happened_at=at,
                              payload={"ev": "uskuna", "holat": run and pwr}))

        def skan(part, inst, route, at, **kw):
            s = Scan(order_id=buyurtma.id, part_id=part.id, instance_id=inst.id, route_id=route.id,
                     post_id=rover_post.id, machine_id=rover.id, employee_id=hodim.id, session_id=smena.id,
                     client_event_id=uuid4().hex, created_at=at, **kw)
            db.add(s)
            return s

        # 40 ta detal ish vaqtida (08:05 dan har 2 daqiqa), birinchisi bekor — lekin braki bor, sanaladi
        skanlar = [skan(eshik, nusxa, qadam, T(8, 5) + timedelta(minutes=2 * i)) for i in range(40)]
        skanlar[0].is_cancelled = True
        skan(olchamsiz, nusxa2, qadam2, T(9, 50))                     # o'lchamsiz detal — faqat load_s
        skan(eshik, nusxa, qadam, T(12, 30))                         # tanaffusda — sanalmaydi
        skan(eshik, nusxa, qadam, T(9, 55), is_cancelled=True)       # braksiz bekor — sanalmaydi
        await db.flush()
        for i in range(4):
            db.add(PartDefect(order_id=buyurtma.id, part_id=eshik.id, instance_id=nusxa.id,
                              scan_id=skanlar[0].id if i == 0 else None, machine_id=rover.id,
                              post_id=rover_post.id, reason="Skol", created_at=T(9) + timedelta(seconds=i)))
        db.add(PartDefect(order_id=buyurtma.id, part_id=eshik.id, instance_id=nusxa.id, machine_id=rover.id,
                          post_id=rover_post.id, reason="Skol", status=DefectStatus.REJECTED, created_at=T(9)))
        await db.commit()

        # ---------- 1. Hisobot: A, P, Q, OEE ----------
        hisobot = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=KECHA.date())
        r = next(x for x in hisobot.rows if x.machine_name == "Rover-1")
        k = next(x for x in hisobot.rows if x.machine_name == "Kromka-1")
        natija.append(("rover: reja = smena − tanaffus", r.planned_s, 28800))
        natija.append(("rover: 3 daqiqalik bo'sh turish sanalmaydi (IDLE qoidasi)",
                       r.unplanned_stop_s + r.no_data_s, 5760))
        natija.append(("rover: ishladi", r.run_s, 23040))
        natija.append(("rover: Availability", r.availability_pct, 80.0))
        natija.append(("rover: detallar (tanaffusdagi va braksiz bekori yo'q)", r.parts, 41))
        natija.append(("rover: ideal (40 × 32 s + 20 s)", r.ideal_s, 1300))
        natija.append(("rover: Performance", r.performance_pct, 5.6))
        natija.append(("rover: rad etilgan brak sanalmaydi", r.defects, 4))
        natija.append(("rover: Quality", r.quality_pct, 90.2))
        natija.append(("rover: OEE = A × P × Q", r.oee_pct, 4.0))
        natija.append(("rover: sababsiz to'xtash", [(x.name, x.seconds) for x in r.reasons],
                       [("Sabab kiritilmagan", 5760)]))
        natija.append(("koeffitsiyentlar javobda", (hisobot.ideal_cycle_rover.load_s,
                                                    hisobot.ideal_cycle_rover.cut_s_per_m), (20.0, 6.0)))
        natija.append(("nazorat (manba siz): 3 daqiqa ham OFF", k.unplanned_stop_s + k.no_data_s, 5940))
        kun = next(d for d in hisobot.days if d.machine_id == r.machine_id)
        # Trek butun SUTKA bo'yicha (reja emas): 17:00-17:20 dagi bo'sh turish ham kiradi,
        # 17:20 dan keyingi OFF esa yopilmagan va agent aloqada emas — noma'lum, kirmaydi
        natija.append(("kunlik trek: IDLE va OFF soniyalari",
                       (kun.seconds["IDLE"], kun.seconds["OFF"]), (180 + 2160 + 1200, 3600 + 3600)))
        natija.append(("kunlik OEE = qator OEE", kun.oee_pct, r.oee_pct))

        # ---------- 2. Chegara 1 daqiqa: 3 daqiqalik bo'sh turish endi to'xtash ----------
        await db.execute(text("UPDATE system_setting SET value = '1' WHERE key = 'stop_prompt_idle_minutes'"))
        await db.commit()
        past = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=KECHA.date())
        r1 = next(x for x in past.rows if x.machine_name == "Rover-1")
        natija.append(("chegara 1 daqiqa: 3 daqiqalik bo'sh turish sanaldi", r1.unplanned_stop_s, 5940))
        await db.execute(text("UPDATE system_setting SET value = '5' WHERE key = 'stop_prompt_idle_minutes'"))
        await db.commit()

        # ---------- 3. Koeffitsiyent o'zgarsa o'tgan kun qayta hisoblanadi ----------
        db.add(SystemSetting(key="ideal_cycle_rover", value='{"load_s": 10, "cut_s_per_m": 5}'))
        await db.commit()
        yangi = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=KECHA.date())
        r2 = next(x for x in yangi.rows if x.machine_name == "Rover-1")
        natija.append(("yangi koeffitsiyent: 40 × (10 + 2 × 5) + 10", r2.ideal_s, 810))

        # ---------- 4. To'xtash sinxroni: tur, chegara va TAKROR yo'qligi ----------
        await sync_machine(db, rover.id, T(18))
        await db.commit()
        await sync_machine(db, rover.id, T(18))   # ikkinchi marta — yangi yozuv chiqmasligi kerak
        await db.commit()
        yozuvlar = (await db.execute(
            select(Downtime.kind, Downtime.started_at, Downtime.ended_at)
            .where(Downtime.machine_id == rover.id).order_by(Downtime.started_at, Downtime.id)
        )).tuples().all()
        natija.append(("downtime: faqat chegaradan uzunlari, turi bilan",
                       [(kind, a.astimezone(TASHKENT_TZ).strftime("%H:%M"),
                         b.astimezone(TASHKENT_TZ).strftime("%H:%M") if b else None) for kind, a, b in yozuvlar],
                       [(DowntimeKind.IDLE, "11:00", "11:36"), (DowntimeKind.OFF, "12:00", "13:00"),
                        (DowntimeKind.OFF, "15:00", "16:00"), (DowntimeKind.IDLE, "17:00", "17:20"),
                        (DowntimeKind.OFF, "17:20", None)]))
        natija.append(("rover IDLE ikkinchi (`idle-*`) yozuv bermaydi",
                       (await db.execute(text(
                           "SELECT count(*) FROM downtime WHERE start_key LIKE 'idle-%'"))).scalar(), 0))

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
