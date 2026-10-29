"""Ombor solishtirishi (EKO 2.4): qoldiq = jurnal, partiyalar, barkodlar, buyurtma sarfi.

Hech narsani o'zgartirmaydi. Farq bo'lsa — ro'yxat va chiqish kodi 1 (monitoring/cron ushlaydi).
Worker buni har kecha o'zi ham yurgizadi (`tasks.ombor_solishtirish`).

    python -m app.commands.ombor_solishtirish
"""

import asyncio
import sys

from app.core.db import local_session
from app.modules.ombor import service as ombor


async def run() -> int:
    async with local_session() as db:
        farqlar = await ombor.reconcile(db)
    for f in farqlar:
        print(f"[{f.tur}] {f.kalit}: hisobda {f.hisobda.normalize()}, kerak {f.kerak.normalize()} — {f.izoh}")
    print(f"Solishtirish: {len(farqlar)} ta farq" if farqlar else "Solishtirish: farq yo'q")
    return 1 if farqlar else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
