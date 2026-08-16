"""Materiallar ombori katalogini Excel'dan yuklash (idempotent).

Manba: `uploads/Umumiy maxsulotlar kataligi.xlsx` — yagona kodlash tizimi
`K-GG-MMM-VV`. Uchta varaq bor, ikkitasi olinadi:

* `Furnitura` — 464 pozitsiya, qoldiq va MIN zaxira bilan
* `Materiallar` — 174 pozitsiya (plita, kromka…), MIN ustuni yo'q
* `Xizmatlar` — OLINMAYDI: xizmatning qoldig'i bo'lmaydi, ya'ni omborga kirmaydi

Ishga tushirish:
    python -m app.commands.import_stock_catalog ["fayl.xlsx"]

Idempotent: kod bo'yicha topilsa YANGILANADI, topilmasa qo'shiladi. Qoldiq
(`qty`) esa faqat YANGI pozitsiyada yoziladi — mavjud pozitsiyada omborchi uni
tizimda yuritadi va qayta import uni Excel'dagi eski raqamga qaytarib
yubormasligi kerak. Narx va nom har importda yangilanadi.
"""

import asyncio
import logging
import sys
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from app.core.db import local_session
from app.models import StockItem
from app.models.enums import StockCatalog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEFAULT_FILE = Path(__file__).resolve().parents[3] / "uploads" / "Umumiy maxsulotlar kataligi.xlsx"

#: Varaq -> ustun sarlavhasi bo'yicha moslash. Sarlavhalar ikki varaqda birxil
#: emas (furniturada "Rang" va "Min", materialda "Struktura" va "Qalinlik"),
#: shuning uchun tartib raqamiga emas SARLAVHAGA tayanamiz — ustun qo'shilsa
#: import buzilmaydi.
SHEETS: dict[str, dict[str, str]] = {
    "Furnitura": {
        "code": "Variant kodi",
        "group_code": "Guruh",
        "group_name": "Guruh nomi",
        "name": "To'liq nomi",
        "variant": "Rang",
        "size": "O'lcham",
        "unit": "O'lchov",
        "qty": "Miqdor",
        "min_qty": "Min",
        "purchase_usd": "Xarid ($)",
        "purchase_uzs": "Xarid (so'm)",
        "sale_uzs": "Sotuv (so'm)",
        "note": "Izoh",
    },
    "Materiallar": {
        "code": "Variant kodi",
        "group_code": "Guruh",
        "group_name": "Guruh nomi",
        "name": "To'liq nomi",
        "variant": "Struktura",
        "size": "O'lcham",
        "qty": "Miqdor",
        "purchase_usd": "Xarid ($)",
        "purchase_uzs": "Xarid (so'm)",
        "sale_uzs": "Sotuv (so'm)",
        "note": "Izoh",
    },
}

MAX_LEN = {
    "code": 20,
    "group_code": 4,
    "group_name": 60,
    "name": 200,
    "variant": 40,
    "size": 40,
    "unit": 16,
    "note": 200,
}


def _text(value: Any, limit: int) -> str | None:
    if value is None:
        return None
    out = str(value).strip()
    return out[:limit] or None


def _num(value: Any) -> Decimal | None:
    """Excel raqami -> Decimal. Bo'sh katak va "0.09" kabi float ham keladi."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(" ", "").replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def read_rows(source: Path | BytesIO) -> list[dict[str, Any]]:
    """Excel -> pozitsiyalar ro'yxati. Manba fayl yo'li ham, bayt oqimi ham
    bo'lishi mumkin: buyruq diskdan o'qiydi, endpoint esa yuklangan faylni
    diskka yozmasdan to'g'ridan-to'g'ri beradi."""
    import openpyxl

    wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
    out: list[dict[str, Any]] = []
    for sheet, mapping in SHEETS.items():
        if sheet not in wb.sheetnames:
            logger.warning("varaq topilmadi: %s", sheet)
            continue
        ws = wb[sheet]
        rows = ws.iter_rows(values_only=True)
        header = [str(c).strip() if c is not None else "" for c in next(rows)]
        index = {name: header.index(title) for name, title in mapping.items() if title in header}
        missing = set(mapping) - set(index)
        if missing:
            logger.warning("%s: ustun topilmadi %s", sheet, sorted(missing))
        for row in rows:
            code = _text(row[index["code"]] if "code" in index else None, MAX_LEN["code"])
            if not code:
                continue
            item: dict[str, Any] = {"code": code, "catalog": StockCatalog(code[0])}
            for field, col in index.items():
                if field == "code":
                    continue
                value = row[col]
                item[field] = _text(value, MAX_LEN[field]) if field in MAX_LEN else _num(value)
            out.append(item)
        logger.info("%s: %d qator", sheet, len([i for i in out if i["catalog"].value == sheet[0].upper()]))
    wb.close()
    return out


async def upsert(db: "AsyncSession", rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Kod bo'yicha qo'shadi/yangilaydi. Qaytaradi: (qo'shildi, yangilandi).

    Tranzaksiyani CHAQIRUVCHI yopadi — buyruq o'z sessiyasida, endpoint esa
    so'rov sessiyasida ishlaydi.
    """
    rows_db = (
        (await db.execute(select(StockItem).where(StockItem.is_deleted == False)))  # noqa: E712
        .scalars()
        .all()
    )
    existing = {i.code: i for i in rows_db}
    added = updated = 0
    for row in rows:
        item = existing.get(row["code"])
        if item is None:
            db.add(
                StockItem(
                    code=row["code"],
                    catalog=row["catalog"],
                    group_code=row.get("group_code") or row["code"].split("-")[1],
                    group_name=row.get("group_name") or "—",
                    name=row.get("name") or row["code"],
                    variant=row.get("variant"),
                    size=row.get("size"),
                    unit=row.get("unit"),
                    qty=row.get("qty") or Decimal(0),
                    min_qty=row.get("min_qty") or Decimal(0),
                    purchase_usd=row.get("purchase_usd"),
                    purchase_uzs=row.get("purchase_uzs"),
                    sale_uzs=row.get("sale_uzs"),
                    note=row.get("note"),
                )
            )
            added += 1
            continue
        # QOLDIQQA TEGILMAYDI: uni omborchi tizimda yuritadi, Excel esa
        # bir marta boshlang'ich holat berib, keyin eskirib qoladi.
        item.group_name = row.get("group_name") or item.group_name
        item.name = row.get("name") or item.name
        item.variant = row.get("variant")
        item.size = row.get("size")
        item.unit = row.get("unit")
        item.min_qty = row.get("min_qty") or item.min_qty
        item.purchase_usd = row.get("purchase_usd")
        item.purchase_uzs = row.get("purchase_uzs")
        item.sale_uzs = row.get("sale_uzs")
        item.note = row.get("note")
        updated += 1
    return added, updated


async def run(path: Path) -> None:
    rows = read_rows(path)
    if not rows:
        logger.error("Katalog bo'sh: %s", path)
        return
    async with local_session() as db:
        added, updated = await upsert(db, rows)
        await db.commit()
    logger.info("Tayyor: %d qo'shildi, %d yangilandi (jami %d)", added, updated, len(rows))


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FILE
    if not target.exists():
        logger.error("Fayl topilmadi: %s", target)
        raise SystemExit(1)
    asyncio.run(run(target))
