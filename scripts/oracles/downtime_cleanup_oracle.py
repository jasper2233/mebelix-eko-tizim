"""`scripts/downtime_deleted_events.sql` — soxta to'xtash yozuvlarini tozalash.

Ikki manba qayta yasaladi:
  (a) yumshoq o'chirilgan andon hodisasidan yasalgan to'xtash (TODO.md #15);
  (b) ROVER stanogidagi `idle-*` yozuv (2026-10-16 deploy'idagi takror).
SQL AYNAN psql orqali yurgiziladi (`\\if`, `\\set`, tranzaksiya haqiqiy) va tekshiriladi:
soxtalari tozalandimi, haqiqiylari, qulf va Kromka bo'sh yurishi joyidami, operator
yozgan sabab yo'qolmadimi, ikkinchi yurgizish xavfsizmi.

Yurgizish (lokal sinov bazasi, prod EMAS; `psql` PATH da bo'lsin):
    cd backend && set -a && . /tmp/oee_test.env && set +a \
      && uv run python ../scripts/oracles/downtime_cleanup_oracle.py
"""

import asyncio
import os
import subprocess
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text

from app.core.config import settings
from app.core.db import local_session
from app.models import AndonEvent, Downtime, DowntimeReason, Machine, Post
from app.models.enums import DowntimeKind, PostCode, PostUnit

SQL = os.path.join(os.path.dirname(__file__), "..", "downtime_deleted_events.sql")
HOZIR = datetime.now(UTC)
OLDIN = HOZIR - timedelta(days=2)   # 12 soatdan uzoq ochiq — 2-bo'limga tushadi


def sqlni_yurgiz(faqat_hisobot: bool = False) -> str:
    buyruq = ["psql", "-X", "-v", "ON_ERROR_STOP=1",
              "-h", settings.POSTGRES_SERVER, "-p", str(settings.POSTGRES_PORT),
              "-U", settings.POSTGRES_USER, "-d", settings.POSTGRES_DB]
    if faqat_hisobot:
        buyruq += ["-v", "faqat_hisobot=1"]
    muhit = {**os.environ}
    if settings.POSTGRES_PASSWORD:
        muhit["PGPASSWORD"] = settings.POSTGRES_PASSWORD
    with open(os.path.abspath(SQL), encoding="utf-8") as f:
        p = subprocess.run(buyruq, stdin=f, capture_output=True, text=True, encoding="utf-8",
                           env=muhit, check=False)
    if p.returncode != 0:
        raise RuntimeError(f"psql xato ({p.returncode}):\n{p.stderr[-2000:]}")
    return p.stdout


async def holat(db) -> dict[str, tuple[bool, bool, bool]]:
    """start_key -> (o'chirilgan, ochiq, nol uzunlik)."""
    db.expire_all()
    rows = (await db.execute(select(Downtime).order_by(Downtime.id))).scalars().all()
    return {
        f"{d.machine_id}:{d.start_key}:{d.kind.value}": (
            d.is_deleted, d.ended_at is None, d.ended_at is not None and d.ended_at == d.started_at)
        for d in rows
    }


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    async with local_session() as db:
        for jadval in ("downtime", "downtime_reason", "andon_event", "machine", "post"):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()

        kromka_post = Post(code=PostCode.KROMKA, name="Kromka", order_index=2, unit=PostUnit.METER)
        rover_post = Post(code=PostCode.ROVER, name="Rover", order_index=6, unit=PostUnit.PIECE)
        db.add_all([kromka_post, rover_post])
        await db.flush()
        kromka = Machine(name="Kromka-1", post_id=kromka_post.id)
        rover = Machine(name="Rover-1", post_id=rover_post.id)
        sabab = DowntimeReason(name="Remont", is_planned=False)
        db.add_all([kromka, rover, sabab])
        await db.flush()
        k, r = kromka.id, rover.id   # expire_all dan keyin atribut o'qilmasin

        for seq, ochirilgan in ((5, True), (6, True), (7, True), (8, False)):
            db.add(AndonEvent(machine_id=kromka.id, session="s", seq=seq, kind="uskuna",
                              happened_at=OLDIN, payload={"holat": 0}, is_deleted=ochirilgan))

        def toxtash(m, key, kind=DowntimeKind.OFF, ochiq=True, reason=None):
            db.add(Downtime(machine_id=m.id, kind=kind, start_key=key, started_at=OLDIN,
                            ended_at=None if ochiq else OLDIN + timedelta(hours=1), reason_id=reason))

        toxtash(kromka, "s-5")                                   # soxta, ochiq, sababsiz → o'chadi
        toxtash(kromka, "s-6", ochiq=False)                      # soxta, yopiq, sababsiz → o'chadi
        toxtash(kromka, "s-7", reason=sabab.id)                  # soxta, sababli → nolga yopiladi
        toxtash(kromka, "s-8")                                   # tirik hodisa → tegilmaydi
        toxtash(kromka, "lock-1", kind=DowntimeKind.LOCK)        # qulf → tegilmaydi
        toxtash(kromka, "idle-100", kind=DowntimeKind.IDLE)      # kromka bo'sh yurishi → tegilmaydi
        toxtash(rover, "idle-200", kind=DowntimeKind.IDLE)       # rover takrori, sababsiz → o'chadi
        toxtash(rover, "idle-300", kind=DowntimeKind.IDLE, reason=sabab.id)  # sababli → nolga yopiladi
        toxtash(rover, "a1-4", kind=DowntimeKind.IDLE)           # rover haqiqiy to'xtashi → tegilmaydi
        await db.commit()

        oldin = await holat(db)
        hisobot = sqlni_yurgiz(faqat_hisobot=True)
        natija.append(("faqat hisobot: hech narsa o'zgarmadi", await holat(db), oldin))
        natija.append(("hisobotda ikkala manba", ("o'chirilgan hodisa" in hisobot, "rover idle-*" in hisobot),
                       (True, True)))
        natija.append(("hisobotda o'zgarmadi degan yozuv", "FAQAT HISOBOT" in hisobot, True))

        sqlni_yurgiz()
        kutilgan = {
            f"{k}:s-5:off": (True, True, False),
            f"{k}:s-6:off": (True, False, False),
            f"{k}:s-7:off": (False, False, True),
            f"{k}:s-8:off": (False, True, False),
            f"{k}:lock-1:lock": (False, True, False),
            f"{k}:idle-100:idle": (False, True, False),
            f"{r}:idle-200:idle": (True, True, False),
            f"{r}:idle-300:idle": (False, False, True),
            f"{r}:a1-4:idle": (False, True, False),
        }
        keyin = await holat(db)
        for kalit, qiymat in kutilgan.items():
            natija.append((f"tozalash: {kalit} (o'chirilgan, ochiq, nol)", keyin.get(kalit), qiymat))
        natija.append(("sabab yo'qolmadi",
                       (await db.execute(text("SELECT count(*) FROM downtime WHERE reason_id IS NOT NULL"))).scalar(),
                       2))

        sqlni_yurgiz()
        natija.append(("ikkinchi yurgizish hech narsani o'zgartirmaydi", await holat(db), keyin))

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
