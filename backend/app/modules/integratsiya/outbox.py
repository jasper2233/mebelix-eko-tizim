"""MES → MX xabarlar navbati (outbox). `navbatga` — biznes tranzaksiyasi ichida; `yubor` — worker (har daqiqa)."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integratsiya import kroy
from app.modules.integratsiya.models import IntegOutbox

logger = logging.getLogger(__name__)

#: Qayta urinish oraliqlari, daqiqa (prototip qoidasi): 1, 5, 30, 120, 360 — keyin 360 da qoladi
BACKOFF_MIN = (1, 5, 30, 120, 360)


async def navbatga(db: AsyncSession, kalit: str, method: str, path: str, body: Any) -> None:
    """Xabarni navbatga qo'yadi; shu kalit avval yozilgan bo'lsa — hech narsa (takror xabar yo'q)."""
    await db.execute(
        insert(IntegOutbox)
        .values(manba="kroy", kalit=kalit[:200], method=method, path=path[:300], body=body, is_deleted=False)
        .on_conflict_do_nothing(index_elements=["manba", "kalit"])
    )


async def yubor(db: AsyncSession, limit: int = 100) -> dict[str, int]:
    """Navbatni tartib bilan yuboradi. Ulanish/5xx xatosida TO'XTAYDI (tartib buzilmasin), 4xx — `rad`."""
    if not kroy.enabled():
        return {"yuborildi": 0, "rad": 0}
    now = datetime.now(UTC)
    rows = (
        await db.execute(
            select(IntegOutbox)
            .where(IntegOutbox.manba == "kroy", IntegOutbox.holat == "yangi")
            .order_by(IntegOutbox.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).scalars()
    sent = rejected = 0
    for m in rows:
        if m.keyingi_at is not None and m.keyingi_at > now:
            break
        try:
            code, res = await asyncio.to_thread(kroy._request, m.method, m.path, m.body, m.kalit)
        except kroy.KroyXato as e:
            code, res = 0, str(e)
        if 200 <= code < 300:
            m.holat, m.yuborilgan_at, m.xato = "yuborildi", now, ""
            sent += 1
            continue
        m.urinish += 1
        m.xato = f"{code}: {res}"[:300]
        if 400 <= code < 500 and code not in (408, 429):
            m.holat = "rad"
            rejected += 1
            logger.error("MX xabari rad etildi (%s %s): %s", m.method, m.path, m.xato)
            continue
        m.keyingi_at = now + timedelta(minutes=BACKOFF_MIN[min(m.urinish, len(BACKOFF_MIN)) - 1])
        break
    await db.commit()
    return {"yuborildi": sent, "rad": rejected}
