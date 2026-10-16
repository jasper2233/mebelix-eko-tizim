"""To'xtash sababi qo'shni yozuvning chetidan olinmaydi (docs/12 §4.23).

HAQIQIY `report_machine_time` HAQIQIY Postgres ustida. Hisobot to'xtashga sababni `downtime`
yozuvlaridan VAQT bo'yicha topadi (`_reason_lookup`). Ilgari 1 soniyalik ustma-ust tushish ham
yetardi: rejali «Tushlik» 12:00-13:00:01 yozuvi, 13:00 da boshlangan 4 daqiqalik avariyaga ham
o'z sababini berib, uni rejali qilib qo'yardi — Availability shishardi.

    Smena 08:00-17:00, tanaffussiz (tushlik — rejali to'xtash sababi bilan)
    08:00-12:00 ishlov · 12:00-13:00 OFF («Tushlik», rejali; yozuv 13:00:01 da yopilgan)
    13:00-13:04 FAULT (qisqa avariya — chegaradan qisqa, yozuvi yo'q, sababsiz)
    13:04-15:00 ishlov · 15:00-16:00 OFF («Material yo'q», rejasiz; yozuv uzunroq: 14:58-16:00)
    16:00-17:00 ishlov
    → rejali: Tushlik 3600 s; rejasiz: avariya 240 + Material yo'q 3600 = 3840 s
    → smena 32400, reja = 32400 − 3600 = 28800, ishladi = 28800 − 3840 = 24960 → A = 86.7%

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . <test.env> && set +a \\
      && uv run python ../scripts/oracles/reason_lookup_oracle.py
"""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import text

from app.api.routes.reports import report_machine_time
from app.core.config import TASHKENT_TZ
from app.core.db import local_session
from app.models import AndonEvent, Downtime, DowntimeReason, Machine, Post, SystemSetting, User
from app.models.enums import DowntimeKind, PostCode, PostUnit, UserRole

KECHA = datetime.now(TASHKENT_TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
T = lambda h, m=0, s=0: KECHA + timedelta(hours=h, minutes=m, seconds=s)  # noqa: E731
JADVAL = '{"shifts":[{"name":"Kunduzi","start":"08:00","end":"17:00","breaks":[]}],"days_off":[],"holidays":[]}'


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    async with local_session() as db:
        for jadval in ("downtime", "downtime_reason", "andon_event", "machine", '"user"', "post", "system_setting"):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()
        db.add_all([SystemSetting(key="work_schedule", value=JADVAL),
                    SystemSetting(key="stop_prompt_idle_minutes", value="5")])
        post = Post(code=PostCode.PRISADKA, name="Prisadka", order_index=7, unit=PostUnit.PIECE)
        tushlik = DowntimeReason(name="Tushlik", is_planned=True)
        material = DowntimeReason(name="Material yo'q")
        db.add_all([post, tushlik, material])
        await db.flush()
        m = Machine(name="Prisadka", post_id=post.id)
        admin = User(username="admin", phone="+998900000001", hashed_password="x", name="Admin", role=UserRole.ADMIN)
        db.add_all([m, admin])
        await db.flush()
        seq = 0

        def chiroq(at: datetime, prev: str, dur: float, keyingi: str) -> None:
            nonlocal seq
            seq += 1
            db.add(AndonEvent(machine_id=m.id, session="s", seq=seq, kind="state", happened_at=at, state=keyingi,
                              prev_state=prev, prev_duration_s=int(dur), payload={"state": keyingi}))

        oraliqlar = [("PROCESSING", T(8), T(12)), ("OFF", T(12), T(13)), ("FAULT", T(13), T(13, 4)),
                     ("PROCESSING", T(13, 4), T(15)), ("OFF", T(15), T(16)), ("PROCESSING", T(16), T(17))]
        for i, (holat, a, b) in enumerate(oraliqlar):
            keyingi = oraliqlar[i + 1][0] if i + 1 < len(oraliqlar) else "OFF"
            chiroq(b, holat, (b - a).total_seconds(), keyingi)
        db.add_all([
            Downtime(machine_id=m.id, kind=DowntimeKind.OFF, start_key="s-1", started_at=T(12),
                     ended_at=T(13, 0, 1), reason_id=tushlik.id),
            Downtime(machine_id=m.id, kind=DowntimeKind.OFF, start_key="s-4", started_at=T(14, 58),
                     ended_at=T(16), reason_id=material.id),
        ])
        await db.commit()

        rep = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=KECHA.date())
        r = next(x for x in rep.rows if x.machine_id == m.id)
        sabablar = sorted((x.name or "Sabab kiritilmagan", x.seconds, x.is_planned) for x in r.reasons)
        natija.append(("avariya qo'shni «Tushlik» sababini olmadi", sabablar, [
            ("Material yo'q", 3600, False), ("Sabab kiritilmagan", 240, False), ("Tushlik", 3600, True)]))
        natija.append(("reja vaqti faqat haqiqiy tushlikni chiqaradi", r.planned_s, 28800))
        natija.append(("rejasiz to'xtash = avariya + material", r.unplanned_stop_s, 3840))
        natija.append(("Availability", r.availability_pct, 86.7))

    xato = sum(1 for _, a, b in natija if a != b)
    for nom, a, b in natija:
        print(f"  {'OK ' if a == b else 'XATO'} {nom}: olingan={a} kutilgan={b}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
