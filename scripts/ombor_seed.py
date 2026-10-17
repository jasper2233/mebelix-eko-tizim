"""Mahsulotlar ombori — boshlang'ich qoldiq, chegara, narx va tavsif (docs/14 §8, 1-bosqich).

Manba — «Qudrat Ombor» dizayn fayli ichidagi katalog (`scripts/ombor_seed.json`, 2026-10-16 da
`Ombor Dastur.html` dan chiqarilgan; kodlar `scripts/catalog.csv` bilan 2662/2662 mos). Egasining
qarori: boshlang'ich ma'lumot shu yerdan olinadi.

FAQAT BO'SH maydon to'ldiriladi: qoldiq 0 bo'lsa, chegara / xarid / sotuv / joy / tavsif bo'sh
bo'lsa. Omborchi allaqachon kiritgan qiymat hech qachon ustidan yozilmaydi — skriptni ikki marta
yurgizish ham xavfsiz.

QOLDIQQA alohida shart: pozitsiyaning `stock_movement` yozuvi bo'lsa qoldiqqa UMUMAN tegilmaydi.
Sotilib nolga tushgan tovar «bo'sh» ko'rinadi va skript uni boshlang'ich qoldiq bilan qaytarib
tiriltirardi — 2026-10-17 da prodda aynan shunday pozitsiya topildi (`F-OS-001-03`, sotilgan).

    cd backend && uv run python ../scripts/ombor_seed.py            # faqat hisobot (bazaga yozmaydi)
    cd backend && uv run python ../scripts/ombor_seed.py --apply    # yozadi

Prod: `docker compose -f docker-compose.prod.yml exec api python /app/scripts/ombor_seed.py [--apply]`.
"""

import argparse
import asyncio
import json
import sys
from decimal import Decimal
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS.parent / "backend"))
sys.path.insert(0, "/app")  # prod konteyneri

#: dizayn kaliti -> (bazadagi maydon, bo'sh hisoblanadigan qiymat)
MAYDON = {
    "a": ("quantity", Decimal(0)),
    "min": ("min_quantity", None),
    "b": ("purchase_price", None),
    "p": ("sale_price", None),
    "y": ("location", None),
    "o": ("description", None),
}


async def main(apply: bool) -> None:
    from sqlalchemy import select

    from app.core.db import local_session
    from app.models import CatalogItem, StockMovement

    data: dict[str, dict] = json.loads((SCRIPTS / "ombor_seed.json").read_text(encoding="utf-8"))
    sanoq = dict.fromkeys(MAYDON.values(), 0)
    topilmadi: list[str] = []
    #: Qoldig'i harakat bilan o'zgargan — seed unga tegmaydi
    tegilmadi: list[str] = []
    async with local_session() as db:
        bor = {i.code: i for i in (await db.execute(select(CatalogItem))).scalars() if not i.is_deleted}
        # Qoldig'i HARAKAT bilan o'zgargan pozitsiyalar: ularning qoldig'iga tegilmaydi.
        # Sotilib nolga tushgan tovar «bo'sh» ko'rinadi — skript uni boshlang'ich qoldiq bilan
        # qaytarib tiriltirardi (prodda topildi: `F-OS-001-03` sotilgan, qoldiq 0).
        harakatli = set(
            (await db.execute(select(StockMovement.item_id).distinct())).scalars()
        )
        for code, r in data.items():
            item = bor.get(code)
            if item is None:
                topilmadi.append(code)
                continue
            for key, (field, bosh) in MAYDON.items():
                if key not in r or getattr(item, field) != bosh:
                    continue
                if field == "quantity" and item.id in harakatli:
                    tegilmadi.append(code)
                    continue
                v = r[key]
                setattr(item, field, Decimal(str(v)) if isinstance(v, (int, float)) else str(v)[:200])
                sanoq[(field, bosh)] += 1
        for (field, _), n in sanoq.items():
            print(f"  {field:15} {n:5} ta to'ldiriladi")
        print(f"  bazada yo'q kod: {len(topilmadi)} {topilmadi[:5]}")
        if tegilmadi:
            print(f"  harakati bor — qoldiqqa tegilmadi: {len(tegilmadi)} {tegilmadi[:5]}")
        if apply:
            await db.commit()
            print("YOZILDI.")
        else:
            await db.rollback()
            print("Faqat hisobot — yozish uchun --apply.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--apply", action="store_true")
    asyncio.run(main(p.parse_args().apply))
