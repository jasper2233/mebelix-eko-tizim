"""Bitta kunning Availability'si so'ralgan ORALIQQA bog'liq emas (docs/12 §4.21).

HAQIQIY `report_machine_time` HAQIQIY Postgres va Redis ustida. Prisadka Pico'si holat TUGAGANDA
hodisa yuboradi; tugamagan oxirgi holat jonli holatdan (Redis) qo'shiladi. Eski kodda u faqat
oraliq HOZIRGACHA bo'lsa qo'shilardi — «Kecha» so'rovida kechagi 15:00 dan keyingi vaqt yo'qolib,
«Kecha + bugun» so'rovidagidan boshqa natija chiqardi.

    Smena 08:00-17:00, tanaffus 12:00-13:00 → reja 8 soat
    P-ish:  08:00-15:00 ishlov (hodisa 15:00 da), 15:00 dan HOZIRGACHA yana ishlov (tugamagan)
            → kecha: ishladi 8 soat → A = 100%
    P-off:  08:00-15:00 ishlov, 15:00 dan HOZIRGACHA o'chiq (tugamagan)
            → kecha: A = 6/8 = 75%, trekda OFF 15:00-24:00 = 32400 s
    P-olik: xuddi P-ish, lekin agent hozir aloqada EMAS (jonli holat yo'q) → tugamagan holat
            ishonchsiz, qo'shilmaydi: 15:00-17:00 ma'lumotsiz → A = 75%

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . <test.env> && set +a \\
      && uv run python ../scripts/oracles/availability_range_oracle.py
"""

import asyncio
import json
from datetime import datetime, timedelta

from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import text

from app.api.routes.reports import report_machine_time
from app.core.config import TASHKENT_TZ, settings
from app.core.db import local_session
from app.models import AndonEvent, Machine, Post, SystemSetting, User
from app.models.enums import PostCode, PostUnit, UserRole
from app.services.andon import ANDON_LIVE_KEY

KECHA = datetime.now(TASHKENT_TZ).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
T = lambda h, m=0: KECHA + timedelta(hours=h, minutes=m)  # noqa: E731
JADVAL = ('{"shifts":[{"name":"Kunduzi","start":"08:00","end":"17:00",'
          '"breaks":[{"name":"Tushlik","start":"12:00","end":"13:00"}]}],"days_off":[],"holidays":[]}')


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    async with AsyncRedis.from_url(settings.REDIS_URL) as r:
        await r.flushall()
    async with local_session() as db:
        for jadval in ("downtime", "downtime_reason", "andon_event", "machine", '"user"', "post", "system_setting"):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()
        db.add_all([SystemSetting(key="work_schedule", value=JADVAL),
                    SystemSetting(key="stop_prompt_idle_minutes", value="5")])
        post = Post(code=PostCode.PRISADKA, name="Prisadka", order_index=7, unit=PostUnit.PIECE)
        db.add(post)
        await db.flush()
        ish, off, olik = (Machine(name=n, post_id=post.id) for n in ("P-ish", "P-off", "P-olik"))
        admin = User(username="admin", phone="+998900000001", hashed_password="x", name="Admin", role=UserRole.ADMIN)
        db.add_all([ish, off, olik, admin])
        await db.flush()
        seq = 0
        for m, keyingi in ((ish, "PROCESSING"), (off, "OFF"), (olik, "PROCESSING")):
            seq += 1
            db.add(AndonEvent(machine_id=m.id, session="s", seq=seq, kind="state", happened_at=T(15),
                              state=keyingi, prev_state="PROCESSING", prev_duration_s=7 * 3600,
                              payload={"state": keyingi}))
        await db.commit()
        # Jonli holat (agent har 30 s yozadi). `save_live` emas: lokal Windows Redis'da `SET ... GET` yo'q
        async with AsyncRedis.from_url(settings.REDIS_URL) as r:
            for m, holat in ((ish, "PROCESSING"), (off, "OFF")):  # P-olik — agent aloqada emas
                await r.set(ANDON_LIVE_KEY.format(m.id), json.dumps({"state": holat, "since": int(T(15).timestamp())}))

        faqat_kecha = await report_machine_time(db, admin, date_from=KECHA.date(), date_to=KECHA.date())
        bugungacha = await report_machine_time(db, admin, date_from=KECHA.date(),
                                               date_to=(KECHA + timedelta(days=1)).date())

        def kun(rep, m: Machine):  # noqa: ANN001, ANN202
            d = next(x for x in rep.days if x.machine_id == m.id and x.day == KECHA.date())
            return d.availability_pct, d.run_s, d.seconds.get("OFF", 0)

        for m in (ish, off, olik):
            natija.append((f"{m.name}: kecha ikkala so'rovda bir xil", kun(faqat_kecha, m), kun(bugungacha, m)))
        natija.append(("P-ish: tugamagan ishlov kechaga sanaladi (A = 100%)", kun(faqat_kecha, ish)[:2], (100.0, 28800)))
        natija.append(("P-off: tugamagan OFF kechaning oxirigacha (trek)", kun(faqat_kecha, off), (75.0, 21600, 32400)))
        natija.append(("P-olik: agent o'lik — tugamagan holat qo'shilmaydi", kun(faqat_kecha, olik)[:2], (75.0, 21600)))
        p = next(x for x in faqat_kecha.rows if x.machine_id == ish.id)
        natija.append(("P-ish: davr yakuni ham kunga mos", (p.availability_pct, p.no_data_s), (100.0, 0)))

    xato = sum(1 for _, a, b in natija if a != b)
    for nom, a, b in natija:
        print(f"  {'OK ' if a == b else 'XATO'} {nom}: olingan={a} kutilgan={b}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
