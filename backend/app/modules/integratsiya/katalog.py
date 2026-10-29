"""MES katalogi → MX Kroy (K5): faqat O'ZGARGAN pozitsiyalar, outbox orqali (MX o'chiq bo'lsa ham yo'qolmaydi).

Har pozitsiyaning oxirgi yuborilgan holati xeshi `kroy_katalog` da: worker har 10 daqiqada solishtiradi va
farqlilarini 500 tadan bo'lib navbatga qo'yadi. Katalogni o'zgartiradigan joylarga (narx, qoldiq, nom — ular ko'p)
alohida ilmoq qo'yilmaydi: holat solishtirish hech birini o'tkazib yubormaydi.
"""

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.integratsiya import kroy
from app.modules.integratsiya.models import KroyKatalog
from app.modules.integratsiya.outbox import navbatga
from app.modules.ombor import service as ombor

QISM = 500


def _xesh(d: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


async def sinxron(db: AsyncSession) -> int:
    """O'zgarganlarini navbatga qo'yadi (commit — chaqiruvchida). Qaytaradi: navbatga qo'yilgan pozitsiyalar soni."""
    if not kroy.enabled():
        return 0
    items = await ombor.katalog_mx(db)
    eski = dict((await db.execute(select(KroyKatalog.kod, KroyKatalog.xesh))).tuples().all())
    farq = [(d, x) for d, x in ((d, _xesh(d)) for d in items) if eski.get(d["id"]) != x]
    for i in range(0, len(farq), QISM):
        qism = farq[i : i + QISM]
        kalit = "katalog:" + hashlib.sha256("".join(x for _, x in qism).encode()).hexdigest()[:40]
        await navbatga(db, kalit, "POST", "/catalog/sync", [d for d, _ in qism])
        stmt = insert(KroyKatalog).values([{"kod": d["id"], "xesh": x, "is_deleted": False} for d, x in qism])
        await db.execute(stmt.on_conflict_do_update(index_elements=["kod"], set_={"xesh": stmt.excluded.xesh}))
    return len(farq)
