"""MES → MX xabarlar navbati (EKO 3d, prototip qoidasi) — HAQIQIY Postgres, HAQIQIY MX (lokal klon).

    1) bir kalit ikki marta navbatga — bitta xabar
    2) MX ishlamaydi (noto'g'ri manzil): birinchi xabar `yangi`, urinish 1, keyingisi 1 daqiqadan keyin;
       ikkinchi xabar UMUMAN yuborilmagan (tartib buzilmaydi)
    3) vaqti kelmagan — yuborilmaydi; vaqti kelgach MX ishlasa — ikkalasi tartib bilan `yuborildi`
    4) 4xx (masalan, yo'q loyiha) — `rad`, navbatni to'sib qo'ymaydi
Talab: MX klon ishlab turgan bo'lsin; `MX_URL`, `MX_SSO_PRIVATE_KEY` muhitda; buyurtmaga bog'langan MX loyihasi
(`argv[1]` — project_id, `argv[2]` — op_id). Lokal sinov, prod EMAS:
    cd backend && uv run python ../scripts/oracles/kroy_outbox_oracle.py <project_id> <op_id>
"""

import asyncio
import sys
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.core.config import settings
from app.core.db import local_session
from app.models import IntegOutbox
from app.modules.integratsiya import outbox

natija: list[bool] = []


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


async def holat(kalit: str) -> tuple[str, int]:
    async with local_session() as db:
        m = (await db.execute(select(IntegOutbox).where(IntegOutbox.kalit == kalit))).scalar_one()
        return m.holat, m.urinish


async def main(pid: str, op: str) -> None:
    u = uuid.uuid4().hex[:8]
    k1, k2, k3 = f"sinov:{u}:1", f"sinov:{u}:2", f"sinov:{u}:3"
    path = f"/projects/{pid}/operations/{op}/maps/1"
    async with local_session() as db:
        # Avvalgi sinovlardan qolgan yuborilmagan xabarlar tartibni buzmasin
        await db.execute(
            update(IntegOutbox).where(IntegOutbox.holat == "yangi").values(holat="rad", xato="sinovdan oldin")
        )
        await outbox.navbatga(db, k1, "PATCH", path, {"done_count": 0})
        await outbox.navbatga(db, k1, "PATCH", path, {"done_count": 0})
        await outbox.navbatga(db, k2, "PATCH", path, {"done_count": 0})
        await db.commit()
        n = len((await db.execute(select(IntegOutbox).where(IntegOutbox.kalit.in_([k1, k2])))).scalars().all())
    print("1) takror kalit")
    tek("ikki xabar (uchta navbatga qo'yish)", n, 2)

    print("2) MX ishlamaydi")
    asl = settings.MX_URL
    settings.MX_URL = "http://127.0.0.1:9"
    async with local_session() as db:
        r = await outbox.yubor(db)
    tek("hech narsa yuborilmadi", r["yuborildi"], 0)
    tek("1-xabar yangi, urinish 1", await holat(k1), ("yangi", 1))
    tek("2-xabar tegilmagan", await holat(k2), ("yangi", 0))
    async with local_session() as db:
        m = (await db.execute(select(IntegOutbox).where(IntegOutbox.kalit == k1))).scalar_one()
        kutish = (m.keyingi_at - datetime.now(UTC)).total_seconds() if m.keyingi_at else 0
    tek("keyingi urinish ~1 daqiqadan keyin", 30 < kutish <= 60, True)

    print("3) vaqti kelmagan / kelgan")
    settings.MX_URL = asl
    async with local_session() as db:
        r = await outbox.yubor(db)
    tek("vaqti kelmagan — 0", r["yuborildi"], 0)
    async with local_session() as db:
        await db.execute(
            update(IntegOutbox)
            .where(IntegOutbox.kalit == k1)
            .values(keyingi_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await db.commit()
        r = await outbox.yubor(db)
    tek("ikkalasi yuborildi", r["yuborildi"], 2)
    tek("tartib: 1 va 2 yuborildi", (await holat(k1))[0] + "/" + (await holat(k2))[0], "yuborildi/yuborildi")

    print("4) 4xx")
    async with local_session() as db:
        await outbox.navbatga(db, k3, "PATCH", "/projects/yoq-loyiha/operations/x/maps/1", {"done_count": 1})
        await db.commit()
        r = await outbox.yubor(db)
    tek("rad etildi, navbat to'silmadi", (r["rad"], (await holat(k3))[0]), (1, "rad"))

    print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")


asyncio.run(main(sys.argv[1], sys.argv[2]))
