"""OEE — Availability, Performance, Quality va ularning ko'paytmasi.

HAQIQIY handler (`report_machine_time`) HAQIQIY Postgres ustida. Fixture ataylab
qo'lda hisoblanadigan qilib tanlangan: kutilgan raqamlar shu faylning boshida
yozilgan, kod ulardan hisoblab chiqarilmaydi.

    Smena 08:00-17:00, tanaffus 12:00-13:00  →  reja = 8 soat = 28800 s

PRISADKA (chiroq ustuni, `prev_duration_s` Pico'dan):
    08:00-10:00 ishlov · 10:00-10:03 TO'XTASH (3 daq — chegaradan qisqa, sanalmaydi)
    10:03-12:00 ishlov · 12:00-13:00 tanaffus · 13:00-15:00 ishlov · 15:00-17:00 to'xtash
    to'xtash 7200 s → ishladi 21600 s → A = 75.0%
    80 detal × 27 s ideal (15 + 6 teshik × 2) = 2160 s → P = 10.0%
    16 brak → Q = (80-16)/80 = 80.0%  →  OEE = 75 × 10 × 80 / 10⁴ = 6.0%

KROMKA (RUN kirishi + o'lchovlar):
    RUN 08:00-17:00 yoqiq, lekin o'lchov faqat 08:00-10:00 va 13:00-14:00 da
    → bo'sh yurish (IDLE) 10:00-13:00 va 14:00-17:00, ish vaqtiga tushgani 18000 s
    → ishladi 10800 s → A = 37.5%
    182 o'tish × (900 mm ÷ 300 mm/s + 3 s) = 1092 s → P = 1092/10800 = 10.1%
    18 brak → Q = 164/182 = 90.1%  →  OEE = 3.4%

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . /tmp/oee_test.env && set +a \
      && uv run python ../scripts/oracles/oee_oracle.py
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
from app.models.enums import DefectStatus, PostCode, PostUnit, UserRole

KECHA = datetime.now(TASHKENT_TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
T = lambda h, m=0: KECHA + timedelta(hours=h, minutes=m)  # noqa: E731
BUGUN = KECHA + timedelta(days=1)
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

        db.add_all([
            SystemSetting(key="work_schedule", value=JADVAL),
            SystemSetting(key="stop_prompt_idle_minutes", value="5"),
            SystemSetting(key="kromka_idle_minutes", value="10"),
        ])
        prisadka_post = Post(code=PostCode.PRISADKA, name="Prisadka", order_index=7, unit=PostUnit.PIECE)
        kromka_post = Post(code=PostCode.KROMKA, name="Kromka", order_index=2, unit=PostUnit.METER)
        db.add_all([prisadka_post, kromka_post])
        await db.flush()
        prisadka = Machine(name="Prisadka", post_id=prisadka_post.id)
        kromka = Machine(name="Kromka-1", post_id=kromka_post.id)
        bugungi = Machine(name="Prisadka-2", post_id=prisadka_post.id)
        hodim = Employee(full_name="Ikromov Samariddin", badge_id=uuid4().hex, assigned_post_ids=[])
        mijoz = Client(full_name="Mijoz")
        admin = User(username="admin", phone="+998900000001", hashed_password="x",
                     name="Admin", role=UserRole.ADMIN)
        db.add_all([prisadka, kromka, bugungi, hodim, mijoz, admin])
        await db.flush()
        smena = WorkSession(employee_id=hodim.id, machine_id=prisadka.id, post_id=prisadka_post.id)
        db.add(smena)
        await db.flush()
        buyurtma = Order(number="B-2026-010", client_id=mijoz.id)
        db.add(buyurtma)
        await db.flush()
        mahsulot = Product(order_id=buyurtma.id, code="01", name="Shkaf", count=1)
        db.add(mahsulot)
        await db.flush()
        # 6 yuza teshik → ideal sikl 15 + 6 × 2 = 27 s
        detal = Part(order_id=buyurtma.id, product_id=mahsulot.id, code="01_001", name="Yon", count=100,
                     length=900, width=430, thickness=16, xnc_summary={"bores": 6})
        db.add(detal)
        await db.flush()
        qadam = PartRoute(order_id=buyurtma.id, part_id=detal.id, post_id=prisadka_post.id, seq=1,
                          process_code=6, per_instance=1, total_required=100)
        nusxa = PartInstance(order_id=buyurtma.id, part_id=detal.id, instance_no=1,
                             qr_text="B-2026-010_01_001_1")
        db.add_all([qadam, nusxa])
        await db.flush()

        seq = 0

        def hodisa(m, kind, at, **kw):
            nonlocal seq
            seq += 1
            db.add(AndonEvent(machine_id=m.id, session="s1", seq=seq, kind=kind, happened_at=at, **kw))

        def chiroq(m, at, prev, dur):
            hodisa(m, "state", at, state="PROCESSING", prev_state=prev,
                   prev_duration_s=dur, payload={"state": "PROCESSING"})

        # --- PRISADKA: chiroq oraliqlari
        chiroq(prisadka, T(10), "PROCESSING", 7200)        # 08:00-10:00 ishlov
        chiroq(prisadka, T(10, 3), "STOPPED", 180)         # 3 daqiqalik mikro-to'xtash
        chiroq(prisadka, T(12), "PROCESSING", 7020)        # 10:03-12:00
        chiroq(prisadka, T(13), "OFF", 3600)               # tanaffus — ish vaqtidan tashqarida
        chiroq(prisadka, T(15), "PROCESSING", 7200)        # 13:00-15:00
        chiroq(prisadka, T(17), "STOPPED", 7200)           # 15:00-17:00 sababsiz to'xtash

        skanlar = []
        for i in range(81):
            s = Scan(order_id=buyurtma.id, part_id=detal.id, instance_id=nusxa.id, route_id=qadam.id,
                     post_id=prisadka_post.id, machine_id=prisadka.id, employee_id=hodim.id,
                     session_id=smena.id, client_event_id=uuid4().hex, created_at=T(8) + timedelta(seconds=i * 60))
            skanlar.append(s)
        # Oxirgisi BEKOR qilingan va braki yo'q — sanalmaydi (80 ta qoladi)
        skanlar[80].is_cancelled = True
        # Birinchisi ham bekor, LEKIN braki bor: ish qilingan, vaqt ketgan — sanaladi
        skanlar[0].is_cancelled = True
        db.add_all(skanlar)
        await db.flush()
        for i in range(16):
            d = PartDefect(order_id=buyurtma.id, part_id=detal.id, instance_id=nusxa.id,
                           scan_id=skanlar[0].id if i == 0 else None,
                           machine_id=prisadka.id, post_id=prisadka_post.id,
                           reason="Chipilgan", created_at=T(9))
            db.add(d)
            if i == 0:
                # Birinchi skanni brak TASDIG'I bekor qilgan (`reopen_from_step` belgisi bilan)
                await db.flush()
                skanlar[0].defect_id = d.id
        # «Brak emas» deb rad etilgani Quality'ga kirmaydi
        db.add(PartDefect(order_id=buyurtma.id, part_id=detal.id, instance_id=nusxa.id,
                          machine_id=prisadka.id, post_id=prisadka_post.id, reason="Chipilgan",
                          status=DefectStatus.REJECTED, created_at=T(9)))

        # --- KROMKA: RUN kirishi va o'lchovlar
        hodisa(kromka, "uskuna", T(8), payload={"ev": "uskuna", "holat": 1})
        hodisa(kromka, "uskuna", T(17), payload={"ev": "uskuna", "holat": 0})
        olchov_soni = 0
        for boshi, soni in ((T(8), 121), (T(13), 61)):   # 08:00-10:00 va 13:00-14:00, har 60 s
            for i in range(soni):
                hodisa(kromka, "olchov", boshi + timedelta(seconds=i * 60),
                       payload={"ev": "olchov", "L": 900.0, "kod": "OK", "v_nom": 18})
                olchov_soni += 1
        for i in range(18):
            db.add(PartDefect(order_id=buyurtma.id, part_id=detal.id, instance_id=nusxa.id,
                              machine_id=kromka.id, post_id=kromka_post.id,
                              reason="Kromka ko'chgan", created_at=T(9) + timedelta(seconds=i)))

        # --- BUGUNGI stanok: reja HOZIRGACHA kesilishini tekshirish uchun
        hodisa(bugungi, "state", BUGUN + timedelta(hours=8, minutes=30), state="PROCESSING",
               prev_state="PROCESSING", prev_duration_s=1800, payload={"state": "PROCESSING"})
        await db.commit()

        # ---------- 1. Kechagi kun: A, P, Q, OEE ----------
        hisobot = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=KECHA.date())
        p = next(r for r in hisobot.rows if r.machine_name == "Prisadka")
        k = next(r for r in hisobot.rows if r.machine_name == "Kromka-1")

        natija.append(("prisadka: reja = smena − tanaffus", (p.shift_s, p.planned_s), (28800, 28800)))
        natija.append(("prisadka: 3 daqiqalik to'xtash sanalmaydi", p.unplanned_stop_s, 7200))
        natija.append(("prisadka: ma'lumotsiz vaqt yo'q", p.no_data_s, 0))
        natija.append(("prisadka: ishladi", p.run_s, 21600))
        natija.append(("prisadka: Availability", p.availability_pct, 75.0))
        natija.append(("prisadka: brakli bekor skan sanaladi, brakksizi yo'q", p.parts, 80))
        natija.append(("prisadka: ideal vaqt (80 × 27 s)", p.ideal_s, 2160))
        natija.append(("prisadka: Performance", p.performance_pct, 10.0))
        natija.append(("prisadka: rad etilgan brak sanalmaydi", p.defects, 16))
        natija.append(("prisadka: Quality", p.quality_pct, 80.0))
        natija.append(("prisadka: OEE = A × P × Q", p.oee_pct, 6.0))
        natija.append(("prisadka: sabab kiritilmagan to'xtash",
                       [(r.name, r.seconds) for r in p.reasons], [("Sabab kiritilmagan", 7200)]))

        natija.append(("kromka: o'lchovsiz vaqt bo'sh yurish", k.unplanned_stop_s, 18000))
        natija.append(("kromka: ishladi", k.run_s, 10800))
        natija.append(("kromka: Availability", k.availability_pct, 37.5))
        natija.append(("kromka: har O'TISH alohida sanaladi", (k.parts, olchov_soni), (182, 182)))
        natija.append(("kromka: ideal vaqt (182 × 6 s)", k.ideal_s, 1092))
        natija.append(("kromka: Performance", k.performance_pct, 10.1))
        natija.append(("kromka: Quality", k.quality_pct, 90.1))
        natija.append(("kromka: OEE", k.oee_pct, 3.4))

        # ---------- 2. To'xtash chegarasi sozlamadan olinadi ----------
        await db.execute(text("UPDATE system_setting SET value = '1' WHERE key = 'stop_prompt_idle_minutes'"))
        await db.commit()
        past = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=KECHA.date())
        p1 = next(r for r in past.rows if r.machine_name == "Prisadka")
        natija.append(("chegara 1 daqiqa: 3 daqiqalik to'xtash sanaldi",
                       (p1.unplanned_stop_s, p1.run_s), (7380, 21420)))
        natija.append(("chegara hisobotda ko'rinadi", past.idle_threshold_min, 1))
        await db.execute(text("UPDATE system_setting SET value = '5' WHERE key = 'stop_prompt_idle_minutes'"))
        await db.commit()

        # ---------- 3. Bo'sh yurish chegarasi ----------
        await db.execute(text("UPDATE system_setting SET value = '240' WHERE key = 'kromka_idle_minutes'"))
        await db.commit()
        uzun = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=KECHA.date())
        k4 = next(r for r in uzun.rows if r.machine_name == "Kromka-1")
        # 4 soatlik chegara: 3 soatlik tirqishlar endi bo'sh yurish emas — lenta kun bo'yi ishlagan
        natija.append(("chegara 4 soat: bo'sh yurish yo'qoladi",
                       (k4.unplanned_stop_s, k4.run_s, k4.availability_pct), (0, 28800, 100.0)))
        await db.execute(text("UPDATE system_setting SET value = '10' WHERE key = 'kromka_idle_minutes'"))
        await db.commit()

        # ---------- 4. OEE kesim sanasi ----------
        db.add(SystemSetting(key="oee_start_date", value=BUGUN.date().isoformat()))
        await db.commit()
        kesilgan = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=KECHA.date())
        natija.append(("kesimdan oldingi kun butunlay tushib qoladi", kesilgan.rows, []))
        natija.append(("kesim sanasi javobda", kesilgan.oee_start, BUGUN.date()))
        await db.execute(text("DELETE FROM system_setting WHERE key = 'oee_start_date'"))
        await db.commit()

        # ---------- 5. Bugungi kun: reja HOZIRGACHA ----------
        hozir = datetime.now(TASHKENT_TZ)
        kutilgan_smena = sum(
            max(0, int((min(hozir, b) - a).total_seconds()))
            for a, b in ((BUGUN + timedelta(hours=8), BUGUN + timedelta(hours=12)),
                         (BUGUN + timedelta(hours=13), BUGUN + timedelta(hours=17)))
        )
        bugungi_hisobot = await report_machine_time(db, admin, date_from=BUGUN.date(), date_to=BUGUN.date())
        b2 = next(r for r in bugungi_hisobot.rows if r.machine_name == "Prisadka-2")
        natija.append(("bugun: reja hozirgacha kesiladi", b2.shift_s, kutilgan_smena))
        natija.append(("bugun: kun tugamaguncha to'liq smena berilmaydi",
                       b2.shift_s < 28800 or hozir >= BUGUN + timedelta(hours=17), True))

        # Soat 08:00 dan oldin yurgizilsa yuqoridagi tekshiruv 0 == 0 bo'lib qoladi —
        # shuning uchun yana bir marta, ATAYLAB hozir davom etayotgan smena bilan:
        # yarim tundan boshlangan smenada reja aynan «shundan beri o'tgan vaqt» bo'lishi kerak.
        await db.execute(text(
            "UPDATE system_setting SET value = :v WHERE key = 'work_schedule'"
        ), {"v": '{"shifts":[{"name":"Tun-kun","start":"00:00","end":"23:59","breaks":[]}],'
                 '"days_off":[],"holidays":[]}'})
        await db.commit()
        oldin = datetime.now(TASHKENT_TZ)
        sutka = await report_machine_time(db, admin, date_from=BUGUN.date(), date_to=BUGUN.date())
        b3 = next(r for r in sutka.rows if r.machine_name == "Prisadka-2")
        otgan = int((oldin - BUGUN).total_seconds())
        natija.append(("davom etayotgan smenada reja = o'tgan vaqt",
                       abs(b3.shift_s - otgan) <= 2, True))
        natija.append(("smena oxirigacha bo'lgan vaqt rejaga kirmaydi", b3.shift_s < 86340, True))
        await db.execute(text("UPDATE system_setting SET value = :v WHERE key = 'work_schedule'"),
                         {"v": JADVAL})
        await db.commit()

        # ---------- 6. Kunlar bo'yicha ----------
        ikki_kun = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=BUGUN.date())
        kecha_p = next(d for d in ikki_kun.days if d.machine_id == p.machine_id and d.day == KECHA.date())
        natija.append(("kunlik qator kechagi jamiga teng",
                       (kecha_p.planned_s, kecha_p.run_s, kecha_p.parts, kecha_p.defects),
                       (28800, 21600, 80, 16)))
        natija.append(("kunlik OEE ham hisoblanadi", kecha_p.oee_pct, 6.0))

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
