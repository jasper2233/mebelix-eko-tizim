"""Lokal demo: taxtani ko'rsatish uchun uchta stanok + jonli holat.

Orakl bazani tozalab o'z fixture'ini yozadi (kromka + rover). Bu skript ustiga
PRISADKA ni (chiroq hodisalari, smena, skanlar) va uchala stanokning jonli
holatini qo'shadi. Faqat sinov bazasi uchun — prodga hech qanday aloqasi yo'q.
"""

import asyncio
import time
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.core.config import TASHKENT_TZ
from app.core.db import local_session
from app.core.security import get_password_hash
from app.models import (
    AndonEvent,
    Employee,
    Machine,
    Order,
    Part,
    PartInstance,
    PartRoute,
    Post,
    Scan,
    User,
    WorkSession,
)
from app.models.enums import PostCode
from app.services.andon import save_live

BUGUN = datetime.now(TASHKENT_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
T = lambda h, m=0: BUGUN + timedelta(hours=h, minutes=m)  # noqa: E731


async def main() -> None:
    async with local_session() as db:
        m = {x.name: x for x in (await db.execute(select(Machine))).scalars()}
        prisadka = m.get("Prisadka")
        if prisadka is None:
            print("Prisadka ish markazi yo'q — avval oraklni yurgizing")
            return
        # Admin paroli (orakl uni "x" bilan yozadi)
        user = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
        user.hashed_password = await get_password_hash("demo12345")
        user.is_superuser = user.is_active = True

        bor = (
            await db.execute(select(AndonEvent.id).where(AndonEvent.machine_id == prisadka.id).limit(1))
        ).first()
        if bor is None:
            post = (await db.execute(select(Post).where(Post.code == PostCode.PRISADKA))).scalar_one()
            hodim = Employee(full_name="Axmedov Alisher", badge_id=uuid4().hex, assigned_post_ids=[post.id])
            db.add(hodim)
            await db.flush()
            smena = WorkSession(employee_id=hodim.id, machine_id=prisadka.id, post_id=post.id)
            db.add(smena)
            await db.flush()
            smena.created_at = T(8)

            seq = 500

            def chiroq(state: str, at: datetime, prev: str | None = None, dur: int | None = None) -> None:
                nonlocal seq
                seq += 1
                db.add(
                    AndonEvent(
                        machine_id=prisadka.id, session="p1", seq=seq, kind="state", state=state,
                        prev_state=prev, prev_duration_s=dur, happened_at=at, payload={"state": state},
                    )
                )

            chiroq("PROCESSING", T(8))
            chiroq("IDLE", T(9), "PROCESSING", 3600)
            chiroq("PROCESSING", T(9, 20), "IDLE", 1200)
            chiroq("FAULT", T(10, 30), "PROCESSING", 4200)
            chiroq("PROCESSING", T(10, 45), "FAULT", 900)

            buyurtma = (await db.execute(select(Order))).scalars().first()
            detal = (await db.execute(select(Part))).scalars().first()
            nusxalar = list((await db.execute(select(PartInstance).limit(10))).scalars().all())
            qadam = PartRoute(order_id=buyurtma.id, part_id=detal.id, post_id=post.id, seq=2,
                              process_code=6, per_instance=1, total_required=10)
            db.add(qadam)
            await db.flush()
            for i, nusxa in enumerate(nusxalar):
                db.add(Scan(order_id=buyurtma.id, part_id=detal.id, instance_id=nusxa.id,
                            route_id=qadam.id, post_id=post.id, machine_id=prisadka.id,
                            employee_id=hodim.id, session_id=smena.id,
                            client_event_id=uuid4().hex, created_at=T(8, 10 + i * 12)))
        await db.commit()
        ids = {x.name: x.id for x in (await db.execute(select(Machine))).scalars()}

    t = int(time.time())
    for nom, (holat, daq) in {
        "Kromka-1": ("PROCESSING", 14),
        "Prisadka": ("PROCESSING", 5),
        "Rover-1": ("IDLE", 38),
    }.items():
        if nom in ids:
            await save_live(ids[nom], {"state": holat, "since": t - daq * 60, "lamps": {},
                                       "part_count": None, "agent_id": 1, "updated_at": t})
    print("demo tayyor:", ids, "· admin / demo12345")


asyncio.run(main())
