"""Yarim tundan o'tgan to'xtash bir kunlik hisobotda kesilib, chegaradan tushib qolmaydi (docs/12 §4.22).

HAQIQIY `report_machine_time` HAQIQIY Postgres ustida. Sariq chiroq (IDLE → STOPPED) chegarasi
5 daqiqa: undan qisqasi mikro-to'xtash, sanalmaydi. To'xtash UZUNLIGI esa butun to'xtash bo'yicha
o'lchanishi kerak — so'ralgan kunga tushgan bo'lagi bo'yicha emas.

    Tungi smena 20:00-08:00 (yarim tundan o'tadi), tanaffussiz
    P-tun:  23:00-23:56 ishlov · 23:56-23:59:30 IDLE · 23:59:30-00:04 STOPPED · 00:04-01:00 ishlov
            → bitta 8 daqiqalik sariq to'xtash, ikki kunga bo'linadi: 4 + 4 daqiqa
    P-qisqa: xuddi shunday, lekin 23:58:30-00:01 (2.5 daqiqa) — butunicha chegaradan qisqa

Eski kod hodisalarni `happened_at >= start` bilan o'qirdi: «ertangi» kun hisobotida 23:59:30 dagi
hodisa (IDLE tugadi) yo'q edi, to'xtash 4.5 daqiqa bo'lib chegaradan o'tmasdi — 4 daqiqa yo'qolardi.

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . <test.env> && set +a \\
      && uv run python ../scripts/oracles/day_boundary_stop_oracle.py
"""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import text

from app.api.routes.reports import report_machine_time
from app.core.config import TASHKENT_TZ
from app.core.db import local_session
from app.models import AndonEvent, Machine, Post, SystemSetting, User
from app.models.enums import PostCode, PostUnit, UserRole

KUN2 = datetime.now(TASHKENT_TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=2)
KUN1 = KUN2 - timedelta(days=1)  # yarim tun KUN1 → KUN2
T = lambda h, m=0, s=0: KUN1 + timedelta(hours=h, minutes=m, seconds=s)  # noqa: E731
JADVAL = '{"shifts":[{"name":"Tungi","start":"20:00","end":"08:00","breaks":[]}],"days_off":[],"holidays":[]}'


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    async with local_session() as db:
        for jadval in ("downtime", "downtime_reason", "andon_event", "machine", '"user"', "post", "system_setting"):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()
        db.add_all([SystemSetting(key="work_schedule", value=JADVAL),
                    SystemSetting(key="stop_prompt_idle_minutes", value="5")])
        post = Post(code=PostCode.PRISADKA, name="Prisadka", order_index=7, unit=PostUnit.PIECE)
        db.add(post)
        await db.flush()
        tun, qisqa = Machine(name="P-tun", post_id=post.id), Machine(name="P-qisqa", post_id=post.id)
        admin = User(username="admin", phone="+998900000001", hashed_password="x", name="Admin", role=UserRole.ADMIN)
        db.add_all([tun, qisqa, admin])
        await db.flush()
        seq = 0

        def chiroq(m: Machine, at: datetime, prev: str, dur: float, keyingi: str) -> None:
            nonlocal seq
            seq += 1
            db.add(AndonEvent(machine_id=m.id, session="s", seq=seq, kind="state", happened_at=at, state=keyingi,
                              prev_state=prev, prev_duration_s=int(dur), payload={"state": keyingi}))

        for m, idle_bosh, stop_bosh, stop_oxir in (
            (tun, T(23, 56), T(23, 59, 30), T(24, 4)),
            (qisqa, T(23, 58, 30), T(23, 59, 30), T(24, 1)),
        ):
            chiroq(m, idle_bosh, "PROCESSING", (idle_bosh - T(23)).total_seconds(), "IDLE")
            chiroq(m, stop_bosh, "IDLE", (stop_bosh - idle_bosh).total_seconds(), "STOPPED")
            chiroq(m, stop_oxir, "STOPPED", (stop_oxir - stop_bosh).total_seconds(), "PROCESSING")
            chiroq(m, T(25), "PROCESSING", (T(25) - stop_oxir).total_seconds(), "OFF")
        await db.commit()

        async def toxtash(day: datetime, m: Machine) -> int:
            rep = await report_machine_time(db, admin, date_from=day.date(), date_to=day.date())
            return next(r for r in rep.rows if r.machine_id == m.id).unplanned_stop_s

        natija.append(("P-tun: 1-kun (23:56-24:00) sanaladi", await toxtash(KUN1, tun), 240))
        natija.append(("P-tun: 2-kun (00:00-00:04) ham sanaladi — to'xtash butunicha 8 daq",
                       await toxtash(KUN2, tun), 240))
        rep = await report_machine_time(db, admin, date_from=KUN1.date(), date_to=KUN2.date())
        natija.append(("P-tun: ikki kunlik hisobot = ikkala kun yig'indisi",
                       next(r for r in rep.rows if r.machine_id == tun.id).unplanned_stop_s, 480))
        natija.append(("P-qisqa: 2.5 daqiqalik to'xtash hech qaysi kunda sanalmaydi",
                       (await toxtash(KUN1, qisqa), await toxtash(KUN2, qisqa)), (0, 0)))

    xato = sum(1 for _, a, b in natija if a != b)
    for nom, a, b in natija:
        print(f"  {'OK ' if a == b else 'XATO'} {nom}: olingan={a} kutilgan={b}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
