"""Mahsulotlar ombori katalogini yuklash — `catalog_item`.

Manba: tsexning Google Sheets katalogi (`docs/Katalog.xlsx`). Undan
`scripts/catalog.csv` yasaladi (repoda turadi, diff'i ko'rinadi), bazaga esa
o'sha CSV yuklanadi. Nega ikki qadam: xlsx serverda kerak emas va u binar —
nima o'zgargani ko'rinmaydi; CSV esa deploy bilan boradi va har qatori o'qiladi.

Yuklash KOD bo'yicha upsert: kod katalogning yagona kaliti va u hech qachon
o'zgarmaydi. Qayta yurgizish xavfsiz — mavjud pozitsiya YANGILANADI, qoldiq va
joylashuv esa TEGILMAYDI (ular omborchining ishi, varaqda yo'q).

    # varaqdan CSV yasash (faqat lokalda, xlsx yonida bo'lsa)
    cd backend && uv run python ../scripts/catalog_import.py --xlsx ../docs/Katalog.xlsx

    # bazaga yuklash (lokalda yoki serverda)
    cd backend && uv run python ../scripts/catalog_import.py --apply

Serverda:
    docker compose -f docker-compose.prod.yml exec -T api \\
      python /app/scripts/catalog_import.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
CSV_FILE = SCRIPTS / "catalog.csv"

#: Kod tuzilishi — `docs/14` §1. Buzuq kod KIRITILMAYDI: katalogning butun
#: ma'nosi shu kodda, «deyarli to'g'ri» kod keyin hech narsaga ulanmaydi.
KOD = re.compile(r"^([MFX])-([A-Z]{2})-(\d{3})-(\d{2})$")

#: CSV ustunlari — modeldagi nom bilan bir xil (`extra` JSON matn sifatida)
USTUNLAR = (
    "code", "catalog", "group_code", "group_name", "model_no", "variant_no",
    "name", "unit", "size_text", "thickness_mm", "article",
    "decor_no", "decor_name", "matrix", "image_url",
    "purchase_price", "sale_price", "status", "note", "extra",
)

#: Ustun bo'lib ajratilganlari — qolgani `extra` ga tushadi
_OLINGAN = {
    "Variant kodi", "Katalog", "Guruh", "Guruh nomi", "Model №", "Variant №", "Model kodi",
    "To'liq nomi", "Birlik", "O'lcham", "O'lchami", "Qalinlik", "qalinlik",
    "Zavod artikuli", "Artikul", "Dekor №", "Dekor nomi", "Matritsa", "Struktura", "RASM",
    "Miqdor", "Min", "Joylashuv", "Xarid (so'm)", "Sotuv (so'm)", "Harajat (so'm)",
    "Holat", "Izoh",
}

#: Varaqda bor, lekin katalogga TUSHMAYDIGAN ustunlar:
#: - `Nom holati` — hamma satrda bir xil matn, ya'ni izoh (legenda), ma'lumot emas
#: - `Nima tuzatildi` — varaqni tozalash jurnali, katalogning o'zi emas
#: - `Foyda`, `Marja %` — sotuv va xarid ayirmasi, saqlash shart emas
#: - `1 list m²` — o'lchamdan kelib chiqadi (2750×1830 = 5.03), hamma satrda bir xil
_TASHLANADI = {"Nom holati", "Nima tuzatildi", "Foyda", "Marja %", "1 list m²"}


def _matn(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "None", "—", "#ERROR!", "#N/A"):
        return None
    # Google Sheets sonni `117003.0` qilib beradi — artikul matn bo'lishi kerak
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def _son(v: Any) -> Decimal | None:
    s = _matn(v)
    if s is None:
        return None
    try:
        return Decimal(s.replace(" ", "").replace(",", "."))
    except InvalidOperation:
        return None


def _butun(v: Any) -> int | None:
    d = _son(v)
    return int(d) if d is not None else None


def varaqdan_csv(xlsx: Path) -> int:
    """Katalog varaqlarini bitta normallashgan CSV ga yig'adi."""
    import openpyxl

    wb = openpyxl.load_workbook(xlsx, data_only=True)

    def satrlar(nom: str) -> list[dict[str, Any]]:
        rows = list(wb[nom].iter_rows(values_only=True))
        bosh = [str(x) if x is not None else "" for x in rows[0]]
        return [
            {b: v for b, v in zip(bosh, r, strict=False) if b}
            for r in rows[1:]
            if any(x not in (None, "") for x in r)
        ]

    # Guruh nomlari: `Maxsulotlar` varag'ida ular yo'q (faqat `LD`/`LM`),
    # `Kodlash` varag'idagi guruhlar jadvalida esa bor
    guruh_nomi: dict[str, str] = {}
    for r in wb["Kodlash"].iter_rows(values_only=True):
        kod, nom = (_matn(r[0]), _matn(r[1])) if len(r) > 1 else (None, None)
        if kod and nom and re.fullmatch(r"[MFX]-[A-Z]{2}", kod):
            guruh_nomi[kod] = nom

    # Dekor rasmlari: `Maxsulotlar` dagi `RASM` ustuni buzuq formula (`#ERROR!`),
    # haqiqiy havola `Dekorlar` varag'ida turadi
    dekor_rasm: dict[int, str] = {}
    for r in satrlar("Dekorlar"):
        no, url = _butun(r.get("Dekor №")), _matn(r.get("Rasm URL"))
        if no is not None and url:
            dekor_rasm[no] = url

    chiqdi: list[dict[str, Any]] = []
    korilgan: set[str] = set()
    for varaq in ("Maxsulotlar", "Materiallar", "Furnitura", "Xizmatlar"):
        for r in satrlar(varaq):
            kod = _matn(r.get("Variant kodi"))
            m = KOD.match(kod or "")
            if m is None:
                print(f"  ! {varaq}: kod buzuq, tashlandi — {kod!r}", file=sys.stderr)
                continue
            if kod in korilgan:
                print(f"  ! {varaq}: kod takrorlandi, tashlandi — {kod}", file=sys.stderr)
                continue
            korilgan.add(kod)  # type: ignore[arg-type]
            katalog, guruh, model_no, variant_no = m.groups()
            dekor_no = _butun(r.get("Dekor №"))
            # Xizmatda «xarid» o'rniga «harajat» yoziladi — ma'nosi bir xil
            xarid = _son(r.get("Xarid (so'm)")) or _son(r.get("Harajat (so'm)"))
            chiqdi.append({
                "code": kod,
                "catalog": katalog,
                "group_code": guruh,
                "group_name": _matn(r.get("Guruh nomi")) or guruh_nomi.get(f"{katalog}-{guruh}") or guruh,
                "model_no": int(model_no),
                "variant_no": int(variant_no),
                "name": _matn(r.get("To'liq nomi")) or kod,
                "unit": _matn(r.get("Birlik")),
                "size_text": _matn(r.get("O'lcham")) or _matn(r.get("O'lchami")),
                "thickness_mm": _son(r.get("Qalinlik")) or _son(r.get("qalinlik")),
                "article": _matn(r.get("Zavod artikuli")) or _matn(r.get("Artikul")),
                "decor_no": dekor_no,
                "decor_name": _matn(r.get("Dekor nomi")),
                "matrix": _matn(r.get("Matritsa")) or _matn(r.get("Struktura")),
                "image_url": dekor_rasm.get(dekor_no) if dekor_no is not None else None,
                "purchase_price": xarid,
                "sale_price": _son(r.get("Sotuv (so'm)")),
                "status": _matn(r.get("Holat")) or "Aktiv",
                "note": _matn(r.get("Izoh")),
                "extra": {
                    k: s for k, v in r.items()
                    if k not in _OLINGAN and k not in _TASHLANADI and (s := _matn(v)) is not None
                },
            })

    chiqdi.sort(key=lambda x: (x["catalog"], x["group_code"], x["model_no"], x["variant_no"]))
    with CSV_FILE.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=USTUNLAR, lineterminator="\n")
        w.writeheader()
        for row in chiqdi:
            w.writerow({**row, "extra": json.dumps(row["extra"], ensure_ascii=False, sort_keys=True)})
    return len(chiqdi)


async def bazaga() -> tuple[int, int]:
    """CSV ni bazaga upsert qiladi. Qaytaradi: (yangi, yangilangan)."""
    sys.path.insert(0, str(SCRIPTS.parent / "backend"))
    from sqlalchemy import select

    from app.core.db import local_session
    from app.models import CatalogItem

    with CSV_FILE.open(encoding="utf-8") as f:
        satrlar = list(csv.DictReader(f))

    yangi = yangilandi = 0
    async with local_session() as db:
        bor = {
            item.code: item
            for item in (await db.execute(select(CatalogItem))).scalars()
        }
        for r in satrlar:
            maydon: dict[str, Any] = {
                "code": r["code"],
                "catalog": r["catalog"],
                "group_code": r["group_code"],
                "group_name": r["group_name"],
                "model_no": int(r["model_no"]),
                "variant_no": int(r["variant_no"]),
                "name": r["name"],
                "unit": r["unit"] or None,
                "size_text": r["size_text"] or None,
                "thickness_mm": Decimal(r["thickness_mm"]) if r["thickness_mm"] else None,
                "article": r["article"] or None,
                "decor_no": int(r["decor_no"]) if r["decor_no"] else None,
                "decor_name": r["decor_name"] or None,
                "matrix": r["matrix"] or None,
                "image_url": r["image_url"] or None,
                "purchase_price": Decimal(r["purchase_price"]) if r["purchase_price"] else None,
                "sale_price": Decimal(r["sale_price"]) if r["sale_price"] else None,
                "status": r["status"],
                "note": r["note"] or None,
                "extra": json.loads(r["extra"] or "{}"),
            }
            item = bor.get(r["code"])
            if item is None:
                # Qoldiq va joylashuv varaqda yo'q — yangi pozitsiya nol bilan tushadi
                db.add(CatalogItem(**maydon))
                yangi += 1
            else:
                # MAVJUD pozitsiyada `quantity`, `min_quantity`, `location` TEGILMAYDI:
                # ular omborchining ishi, varaqdan qaytib kelib ustiga yozmasin
                for k, v in maydon.items():
                    setattr(item, k, v)
                item.is_deleted = False
                yangilandi += 1
        await db.commit()
    return yangi, yangilandi


def main() -> None:
    p = argparse.ArgumentParser(description="Mahsulotlar ombori katalogini yuklash")
    p.add_argument("--xlsx", type=Path, help="Katalog.xlsx dan CSV yasash")
    p.add_argument("--apply", action="store_true", help="CSV ni bazaga yuklash")
    args = p.parse_args()
    if not args.xlsx and not args.apply:
        p.error("--xlsx yoki --apply kerak")
    if args.xlsx:
        n = varaqdan_csv(args.xlsx)
        print(f"{CSV_FILE.name}: {n} pozitsiya yozildi")
    if args.apply:
        if not CSV_FILE.exists():
            sys.exit(f"{CSV_FILE} yo'q — avval --xlsx bilan yasang")
        yangi, yangilandi = asyncio.run(bazaga())
        print(f"katalog: {yangi} yangi, {yangilandi} yangilandi")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
