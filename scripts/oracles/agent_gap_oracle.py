"""Agent uzilgan payt: ROVER Pico'ning o'z yozuvlaridan tiklanadi, KROMKA davomiyligi saqlanadi.

HAQIQIY handler (`report_machine_time`) va HAQIQIY to'xtash sinxroni (`sync_machine`)
HAQIQIY Postgres ustida. Kutilgan raqamlar qo'lda hisoblangan (docs/12 §4.16):

    Smena 08:00-17:00, tanaffus 12:00-13:00  →  reja = 8 soat = 28800 s

ROVER — agent 1-ulanish 08:00-10:30, UZILDI, 2-ulanish 11:30 dan:
    Pico fleshdan: SPINDLE_IDLE 10:40-10:55, POWER_ON 07:59-11:00, POWER_CYCLE 11:00-11:20,
                   SPINDLE_IDLE 15:00-15:20 (agent ham ko'rgan), POWER_ON 11:20-16:00
    11:30 qayta ulanish: ishlov, on_sec = 600 (11:20 dan yoqiq)
    agent: 15:00 bo'sh turish, 15:20 ishlov, 16:00 o'chiq — agent aloqada emas
    to'xtash: 15 + 20 + 20 daq = 3300 s, 16:00-17:00 ma'lumot yo'q 3600 s
    → ishladi 21900 s → A = 76.0%   (eski hisob: uzilish ishlov bo'lib, A = 87.5%)

KROMKA-1 — o'sha kunda agent uzilgan, Pico tirik (RAM saqlaydi): davomiylik TO'G'RI
    08:00 yoqildi, 11:30 qayta ulanish (o'sha holat), 16:00 o'chdi → ishladi 7 soat, A = 87.5%
KROMKA-2 — 10:00 oxirgi hodisa, 11:00 da tokdan qayta yondi (`sabab: tok`) → 10:00-11:00 noma'lum
    → ishladi 6 soat, A = 75.0%
KROMKA-3 — o'sha, lekin `sabab: wdt` (soniyalik) → kesilmaydi, A = 87.5%

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . /tmp/oee_test.env && set +a \
      && uv run python ../scripts/oracles/agent_gap_oracle.py
"""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select, text

from app.api.routes.reports import report_machine_time
from app.core.config import TASHKENT_TZ
from app.core.db import local_session
from app.models import AndonEvent, Downtime, Machine, Post, SystemSetting, User
from app.models.enums import DowntimeKind, PostCode, PostUnit, UserRole
from app.services.downtimes import sync_machine

KECHA = datetime.now(TASHKENT_TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
T = lambda h, m=0: KECHA + timedelta(hours=h, minutes=m)  # noqa: E731
JADVAL = ('{"shifts":[{"name":"Kunduzi","start":"08:00","end":"17:00",'
          '"breaks":[{"name":"Tushlik","start":"12:00","end":"13:00"}]}],"days_off":[],"holidays":[]}')


def iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S")


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    async with local_session() as db:
        for jadval in ("downtime", "downtime_reason", "andon_event", "machine", '"user"', "post", "system_setting"):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()
        db.add_all([
            SystemSetting(key="work_schedule", value=JADVAL),
            SystemSetting(key="stop_prompt_idle_minutes", value="5"),
            SystemSetting(key="kromka_idle_minutes", value="240"),
        ])
        rp = Post(code=PostCode.ROVER, name="Rover", order_index=6, unit=PostUnit.PIECE)
        kp = Post(code=PostCode.KROMKA, name="Kromka", order_index=2, unit=PostUnit.METER)
        db.add_all([rp, kp])
        await db.flush()
        rover = Machine(name="Rover-1", post_id=rp.id)
        k1, k2, k3 = (Machine(name=f"Kromka-{i}", post_id=kp.id) for i in (1, 2, 3))
        admin = User(username="admin", phone="+998900000001", hashed_password="x", name="A", role=UserRole.ADMIN)
        db.add_all([rover, k1, k2, k3, admin])
        await db.flush()

        seq = 0

        def ev(m, kind, at, session, payload):
            nonlocal seq
            seq += 1
            db.add(AndonEvent(machine_id=m.id, session=session, seq=seq, kind=kind, happened_at=at, payload=payload))

        def rv(at, session, run, pwr, on_sec=0, idle_sec=0):
            ev(rover, "uskuna", at, session, {"ev": "uskuna", "holat": int(run and pwr), "manba": "rover",
                                              "pwr": pwr, "run": run, "on_sec": on_sec, "idle_sec": idle_sec})

        rn = 0

        def pico(tur, a, b):
            nonlocal rn
            rn += 1
            db.add(AndonEvent(machine_id=rover.id, session="rover", seq=rn, kind="rover", happened_at=b,
                              payload={"rover_type": tur, "start": iso(a), "end": iso(b),
                                       "duration_sec": int((b - a).total_seconds())}))

        # ROVER — agent 1-ulanish
        rv(T(8), "s1", 1, 1, on_sec=60)
        # ... 10:30 da agent uzildi. Pico fleshga yozdi:
        pico("SPINDLE_IDLE", T(10, 40), T(10, 55))
        pico("POWER_ON", T(7, 59), T(11))
        pico("POWER_CYCLE", T(11), T(11, 20))
        # 2-ulanish
        rv(T(11, 30), "s2", 1, 1, on_sec=600)
        rv(T(15), "s2", 0, 1, idle_sec=0)
        rv(T(15, 20), "s2", 1, 1)
        pico("SPINDLE_IDLE", T(15), T(15, 20))
        rv(T(16), "s2", 0, 0)
        pico("POWER_ON", T(11, 20), T(16))

        # KROMKA — Pico'ning o'z hodisalari (xb sessiyasi), qayta ulanishdagi HOLAT agent kalitida
        for m in (k1, k2, k3):
            ev(m, "uskuna", T(8), "aa", {"ev": "uskuna", "holat": 1})
            ev(m, "ogoh", T(10), "aa", {"ev": "ogoh", "tur": "iflos"})
            ev(m, "uskuna", T(16), "aa" if m is k1 else "bb", {"ev": "uskuna", "holat": 0})
        ev(k1, "uskuna", T(11, 30), "agent1", {"ev": "uskuna", "holat": 1, "manba": "holat"})
        for m, sabab in ((k2, "tok"), (k3, "wdt")):
            ev(m, "boot", T(11), "bb", {"ev": "boot", "sabab": sabab})
            ev(m, "uskuna", T(11), "agent2", {"ev": "uskuna", "holat": 1, "manba": "holat"})
        await db.commit()

        h = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=KECHA.date())
        r = {x.machine_name: x for x in h.rows}
        rr = r["Rover-1"]
        natija.append(("rover: to'xtash (15+20+20 daq) va ma'lumotsiz (1 soat)",
                       (rr.unplanned_stop_s, rr.no_data_s), (3300, 3600)))
        natija.append(("rover: uzilish Pico yozuvlaridan tiklandi — ishladi", rr.run_s, 21900))
        natija.append(("rover: Availability", rr.availability_pct, 76.0))
        kun = next(d for d in h.days if d.machine_id == rr.machine_id)
        natija.append(("rover: kunlik trekda o'chiq 11:00-11:20 va bo'sh 35 daq",
                       (kun.seconds["OFF"], kun.seconds["IDLE"]), (1200, 2100)))
        natija.append(("kromka-1: Pico tirik — uzilish davomiyligi saqlandi",
                       (r["Kromka-1"].run_s, r["Kromka-1"].availability_pct), (25200, 87.5)))
        natija.append(("kromka-2: tokdan qayta yonish — 10:00-11:00 noma'lum",
                       (r["Kromka-2"].run_s, r["Kromka-2"].availability_pct), (21600, 75.0)))
        natija.append(("kromka-3: qorovul (wdt) — kesilmadi",
                       (r["Kromka-3"].run_s, r["Kromka-3"].availability_pct), (25200, 87.5)))

        # To'xtash sinxroni: agent ko'rmagan to'xtashlar Pico'dan, ko'rgani takrorlanmaydi
        await sync_machine(db, rover.id, T(17, 30))
        await db.commit()
        await sync_machine(db, rover.id, T(17, 30))
        await db.commit()
        yozuvlar = (await db.execute(
            select(Downtime.kind, Downtime.started_at, Downtime.ended_at, Downtime.start_key)
            .where(Downtime.machine_id == rover.id, Downtime.is_deleted == False)  # noqa: E712
            .order_by(Downtime.started_at)
        )).tuples().all()
        soat = lambda t: t.astimezone(TASHKENT_TZ).strftime("%H:%M") if t else None  # noqa: E731
        natija.append(("rover downtime: Pico'dan 2 ta, agentdan 2 ta, takrorsiz",
                       [(k, soat(a), soat(b), key.startswith("rv-")) for k, a, b, key in yozuvlar],
                       [(DowntimeKind.IDLE, "10:40", "10:55", True), (DowntimeKind.OFF, "11:00", "11:20", True),
                        (DowntimeKind.IDLE, "15:00", "15:20", False), (DowntimeKind.OFF, "16:00", None, False)]))

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
