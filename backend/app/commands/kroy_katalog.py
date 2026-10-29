"""MES katalogini MX Kroy ga yuborish (EKO 3e, K5) — birinchi ulashda yoki qo'lda.

Worker buni har 10 daqiqada o'zi qiladi (faqat o'zgarganlarini); bu buyruq navbatga qo'yib, darhol yuboradi.

    python -m app.commands.kroy_katalog
"""

import asyncio

from app.core.db import local_session
from app.modules.integratsiya import service as integratsiya


async def run() -> None:
    async with local_session() as db:
        n = await integratsiya.katalog_sinxron(db)
        await db.commit()
    print(f"Navbatga qo'yildi: {n} ta pozitsiya")
    while True:
        async with local_session() as db:
            r = await integratsiya.outbox_yubor(db)
        print(f"Yuborildi: {r['yuborildi']}, rad: {r['rad']}")
        if r["yuborildi"] == 0:
            break


if __name__ == "__main__":
    asyncio.run(run())
