"""Qulf stanok ishlay boshlaguncha amal qiladi (docs/12 §4.24).

HAQIQIY `downtimes.sync_machine` HAQIQIY Postgres ustida. Operator 12:00 da qulf tugmasini
«Tushlik» (rejali) sababi bilan bosib ketdi va terminalga qaytib KIRMADI (smena ochilmadi — qulf
yozuvi ochiq). Stanok esa 12:50 da yana ishlay boshladi.

    PRISADKA: 12:05-12:50 OFF (tushlik) · 12:50 ishlov · 13:30-13:45 FAULT · 13:45 ishlov
    KROMKA:   12:05-12:50 lenta to'xtagan · 12:50 yurdi · 13:30-13:45 to'xtagan · 13:45 yurdi

Kutilgan: tushlikdagi to'xtash qulf sababini oladi; 13:30 dagi to'xtash — yo'q (sabab so'raladi).
Eski kod ikkalasiga ham «Tushlik» berardi va avariya reja vaqtidan chiqib ketardi.

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . <test.env> && set +a \\
      && uv run python ../scripts/oracles/lock_end_oracle.py
"""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select, text

from app.core.config import TASHKENT_TZ
from app.core.db import local_session
from app.models import AndonEvent, Downtime, DowntimeReason, Machine, Post, SystemSetting
from app.models.enums import DowntimeKind, PostCode, PostUnit
from app.services.downtimes import sync_machine

KUN = datetime.now(TASHKENT_TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
T = lambda h, m=0: KUN + timedelta(hours=h, minutes=m)  # noqa: E731


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    async with local_session() as db:
        for jadval in ("downtime", "downtime_reason", "andon_event", "machine", "post", "system_setting"):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()
        db.add(SystemSetting(key="stop_prompt_idle_minutes", value="5"))
        pp = Post(code=PostCode.PRISADKA, name="Prisadka", order_index=7, unit=PostUnit.PIECE)
        kp = Post(code=PostCode.KROMKA, name="Kromka", order_index=2, unit=PostUnit.METER)
        tushlik = DowntimeReason(name="Tushlik", is_planned=True)
        db.add_all([pp, kp, tushlik])
        await db.flush()
        pr, kr = Machine(name="Prisadka", post_id=pp.id), Machine(name="Kromka-1", post_id=kp.id)
        db.add_all([pr, kr])
        await db.flush()
        seq = 0

        def ev(m: Machine, at: datetime, **kw: object) -> None:
            nonlocal seq
            seq += 1
            db.add(AndonEvent(machine_id=m.id, session="s", seq=seq, happened_at=at, **kw))  # type: ignore[arg-type]

        def chiroq(at: datetime, holat: str, prev: str, dur: int) -> None:
            ev(pr, at, kind="state", state=holat, prev_state=prev, prev_duration_s=dur, payload={"state": holat})

        chiroq(T(11), "PROCESSING", "OFF", 60)
        chiroq(T(12, 5), "OFF", "PROCESSING", 3900)
        chiroq(T(12, 50), "PROCESSING", "OFF", 2700)
        chiroq(T(13, 30), "FAULT", "PROCESSING", 2400)
        chiroq(T(13, 45), "PROCESSING", "FAULT", 900)
        for at, holat in ((T(11), 1), (T(12, 5), 0), (T(12, 50), 1), (T(13, 30), 0), (T(13, 45), 1)):
            ev(kr, at, kind="uskuna", payload={"ev": "uskuna", "holat": holat})
        for m in (pr, kr):  # qulf: sabab aytilgan, smena qayta ochilmagan
            db.add(Downtime(machine_id=m.id, kind=DowntimeKind.LOCK, start_key=f"lock-{m.id}", started_at=T(12),
                            reason_id=tushlik.id, reason_at=T(12)))
        await db.commit()

        for m in (pr, kr):
            await sync_machine(db, m.id, T(14))
        await db.commit()

        for m in (pr, kr):
            rows = (await db.execute(
                select(Downtime.started_at, Downtime.reason_id).where(
                    Downtime.machine_id == m.id, Downtime.kind != DowntimeKind.LOCK
                ).order_by(Downtime.started_at)
            )).tuples().all()
            got = [(a.astimezone(TASHKENT_TZ).strftime("%H:%M"), r) for a, r in rows]
            natija.append((f"{m.name}: tushlik qulf sababini oldi, 13:30 dagi to'xtash — yo'q", got,
                           [("12:05", tushlik.id), ("13:30", None)]))

        # Qulf yozuvi faqat smena ochilganda yopiladi (`close_open_locks`) — sinxron unga tegmaydi
        lk = await db.scalar(select(Downtime).where(Downtime.machine_id == pr.id, Downtime.kind == DowntimeKind.LOCK))
        natija.append(("qulf yozuvining o'ziga tegilmadi (terminal o'z holatida)", lk.ended_at if lk else "yo'q", None))

    xato = sum(1 for _, a, b in natija if a != b)
    for nom, a, b in natija:
        print(f"  {'OK ' if a == b else 'XATO'} {nom}: olingan={a} kutilgan={b}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
