"""OEE yo'qotishi pulda (EKO 10d) — `oee_oracle.py` ssenariysi ustida (u ma'lumotni bazaga yozib qoldiradi).

Kechagi Prisadka: reja 28 800 s, ishladi 21 600 s, 80 detal × ideal 27 s = 2 160 s, brak 16. Soat narxi 3 600 so'm:
  to'xtash 7 200 s → 7 200 so'm, sekin 21 600 − 2 160 = 19 440 s → 19 440 so'm, brak 2 160 × 16/80 = 432 s → 432 so'm.
Narxi yo'q stanokda pul `None` (nol emas).
    cd backend && uv run python ../scripts/oracles/oee_pul_oracle.py
"""

import asyncio
import subprocess
import sys
from datetime import timedelta
from decimal import Decimal as D
from pathlib import Path

from sqlalchemy import select

from app.core.db import local_session
from app.models import Machine
from app.modules.tannarx import norma
from app.modules.tannarx import services as t

# Alohida jarayonda: ikkita `asyncio.run` bitta ulanish pulini bo'lisha olmaydi
subprocess.run([sys.executable, str(Path(__file__).with_name("oee_oracle.py"))], check=True, capture_output=True)
natija: list[bool] = []


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


async def main() -> None:
    kecha = t.bugun() - timedelta(days=1)
    async with local_session() as db:
        p = (await db.execute(select(Machine).where(Machine.name == "Prisadka"))).scalar_one()
        y = {r.nom: r for r in await norma.oee_yoqotish(db, kecha, kecha)}["Prisadka"]
        tek("narx yo'q — pul None", (y.soat_narxi, y.pul(y.to_xtash_s)), (None, None))
        tek("soniyalar: to'xtash, sekin, brak", (y.to_xtash_s, y.sekin_s, y.brak_s), (7200, 19440, 432))
        y5 = {r.nom: r for r in await norma.oee_yoqotish(db, kecha - timedelta(days=5), kecha)}["Prisadka"]
        tek(
            "ma'lumotsiz kunlar to'xtash emas — 6 kunlik davr = kechagi kun",
            (y5.to_xtash_s, y5.sekin_s, y5.malumotsiz_kun >= 4),
            (7200, 19440, True),
        )
        await norma.stanok_narx_qosh(db, p.id, D(3600), kecha - timedelta(days=5), None)
        y = {r.nom: r for r in await norma.oee_yoqotish(db, kecha, kecha)}["Prisadka"]
        tek(
            "pul: 3 600 so'm/soat",
            (y.pul(y.to_xtash_s), y.pul(y.sekin_s), y.pul(y.brak_s)),
            (D("7200.00"), D("19440.00"), D("432.00")),
        )
        await db.rollback()
    print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")


asyncio.run(main())
