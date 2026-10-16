"""Mahsulotlar ombori 1-bosqich — narx qoidalari, kod berish, o'chirish, sinf, zaxira, ABC, import
(docs/14 §8). HAQIQIY route handlerlari HAQIQIY Postgres ustida, `scripts/catalog.csv` yuklangan
katalog bilan (`catalog_import.py --apply` + `ombor_seed.py --apply` oldin yurgizilgan bo'lsin).

Kutilgan qiymatlar dizayndagi qoidalardan QO'LDA hisoblangan (`markupPrice`, `setTierPrice`,
`setUsd`, `nextCode`, `buildCatalog` ABC):

    furnitura: sotuv = round(xarid × (1 + ustama/100) / 100) × 100
    dekor:     sotuv = sinf narxi (Standart / Medium / Premium)
    dollar:    xarid = round($ × kurs) → sotuv ustamadan

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . <test.env> && set +a \\
      && uv run python ../scripts/oracles/ombor_nomenklatura_oracle.py
"""

import asyncio
import subprocess
import sys
import types
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select

from app.api.routes.catalog import (
    bulk_update_catalog_items,
    create_catalog_item,
    delete_catalog_items,
    import_catalog_items,
    read_catalog_all,
    update_catalog_item,
    update_warehouse_pricing,
)
from app.core.db import local_session
from app.models import CatalogItem
from app.schemas.catalog import (
    CatalogBulk,
    CatalogIds,
    CatalogImport,
    CatalogItemCreate,
    CatalogItemUpdate,
    WarehousePricing,
)

natija: list[tuple[str, object, object]] = []
user = types.SimpleNamespace(id=None)
req = types.SimpleNamespace(headers={}, client=types.SimpleNamespace(host="127.0.0.1"))
D = Decimal


async def main() -> None:
    async with local_session() as db:

        async def by(code: str) -> CatalogItem:
            item = await db.scalar(select(CatalogItem).where(CatalogItem.code == code))
            assert item is not None, code
            await db.refresh(item)
            return item

        # --- 1. Narx sozlamasi: umumiy ustama 35%, Ruchkalar guruhi 40%, sinf narxlari, kurs
        cfg = WarehousePricing(
            usd_rate=D(12800),
            tier_prices={"M-LD": {"S": D(450000), "M": D(520000), "P": D(610000)}, "M-LM": {"S": D(480000)}},
            markup_all=D(35),
            markup_groups={"F-RC": D(40)},
        )
        await update_warehouse_pricing(db, user, cfg, req)  # type: ignore[arg-type]
        r = await by("F-RC-001-01")  # xarid 3660 → 3660 × 1.40 = 5124 → 5100
        natija.append(("guruh ustamasi 40%: 3660 → 5100 (100 so'mgacha)", r.sale_price, D(5100)))
        ak = (
            await db.execute(
                select(CatalogItem).where(
                    CatalogItem.catalog == "F",
                    CatalogItem.group_code == "AK",
                    CatalogItem.purchase_price.is_not(None),
                )
            )
        ).scalars().first()
        assert ak is not None
        kut = (ak.purchase_price * D("1.35") / 100).quantize(D(1)) * 100
        natija.append(("umumiy ustama 35% boshqa guruhda", ak.sale_price, kut))

        # --- 2. Pozitsiya ustamasi guruhnikidan ustun; olib tashlansa guruhniki qaytadi
        await update_catalog_item(db, user, req, r.id, CatalogItemUpdate(markup_pct=D(50)))  # type: ignore[arg-type]
        natija.append(("pozitsiya ustamasi 50%: 3660 → 5500", (await by("F-RC-001-01")).sale_price, D(5500)))
        await update_catalog_item(db, user, req, r.id, CatalogItemUpdate.model_validate({"markup_pct": None}))  # type: ignore[arg-type]
        natija.append(("ustama olib tashlandi — guruhniki (40%)", (await by("F-RC-001-01")).sale_price, D(5100)))

        # --- 3. Dollar xarid: $0.29 × 12800 = 3712 → ×1.40 = 5196.8 → 5200; kurs 13000 → 3770 → 5300
        await update_catalog_item(db, user, req, r.id, CatalogItemUpdate(purchase_usd=D("0.29")))  # type: ignore[arg-type]
        x = await by("F-RC-001-01")
        natija.append(("$0.29 × 12800 = 3712, sotuv 5200", (x.purchase_price, x.sale_price), (D(3712), D(5200))))
        await update_warehouse_pricing(db, user, cfg.model_copy(update={"usd_rate": D(13000)}), req)  # type: ignore[arg-type]
        x = await by("F-RC-001-01")
        natija.append(("kurs 13000: xarid 3770, sotuv 5300", (x.purchase_price, x.sale_price), (D(3770), D(5300))))
        await update_catalog_item(db, user, req, r.id, CatalogItemUpdate(purchase_price=D(3660)))  # type: ignore[arg-type]
        x = await by("F-RC-001-01")
        natija.append(("so'mda qo'lda kiritilsa dollar narxi bekor", (x.purchase_usd, x.sale_price), (None, D(5100))))

        # --- 4. Dekor sinfi: bitta va ko'plab; sinf narxi o'zgarsa hammasi yangilanadi
        d1, d2, d3 = await by("M-LD-046-01"), await by("M-LD-046-02"), await by("M-LM-046-01")
        await bulk_update_catalog_items(db, user, CatalogBulk(ids=[d1.id, d2.id], tier="M"), req)  # type: ignore[arg-type]
        await bulk_update_catalog_items(db, user, CatalogBulk(ids=[d3.id], tier="S"), req)  # type: ignore[arg-type]
        natija.append(
            ("sinf Medium → 520 000, LMDF Standart → 480 000",
             [(await by(c)).sale_price for c in ("M-LD-046-01", "M-LD-046-02", "M-LM-046-01")],
             [D(520000), D(520000), D(480000)])
        )
        cfg2 = cfg.model_copy(update={"usd_rate": D(13000), "tier_prices": {"M-LD": {"S": D(450000), "M": D(555000)}, "M-LM": {"S": D(480000)}}})
        await update_warehouse_pricing(db, user, cfg2, req)  # type: ignore[arg-type]
        natija.append(("Medium narxi 555 000 — ikkala dekor birdan", [(await by(c)).sale_price for c in ("M-LD-046-01", "M-LD-046-02")], [D(555000), D(555000)]))
        f = await by("F-RC-002-01")
        await bulk_update_catalog_items(db, user, CatalogBulk(ids=[f.id], tier="P"), req)  # type: ignore[arg-type]
        natija.append(("furnituraga sinf berilmaydi", (await by("F-RC-002-01")).tier, None))

        # --- 5. Zaxira: faqat material
        await bulk_update_catalog_items(db, user, CatalogBulk(ids=[d1.id, f.id], tracked=True), req)  # type: ignore[arg-type]
        natija.append(("zaxiraga olish — faqat material", ((await by("M-LD-046-01")).tracked, (await by("F-RC-002-01")).tracked), (True, False)))

        # --- 6. Kod berish: yangi model va mavjud model varianti; o'chirilgan kod qayta berilmaydi
        n1 = await create_catalog_item(db, user, CatalogItemCreate(catalog="F", group_code="RC", name="Ruchka sinov 1", purchase_price=D(10000)), req)  # type: ignore[arg-type]
        mx = await db.scalar(select(CatalogItem.model_no).where(CatalogItem.code == n1.code))
        natija.append(("yangi model: guruhning keyingi raqami, variant 01", n1.code.endswith("-01") and n1.code.startswith("F-RC-"), True))
        natija.append(("yangi furnitura sotuvi ustamadan (10000 × 1.40)", n1.sale_price, D(14000)))
        v2 = await create_catalog_item(db, user, CatalogItemCreate(catalog="F", group_code="RC", model=f"F-RC-{mx:03d}", name="Ruchka sinov 1 qora"), req)  # type: ignore[arg-type]
        natija.append(("mavjud model varianti 02", v2.code, f"F-RC-{mx:03d}-02"))
        await delete_catalog_items(db, user, CatalogIds(ids=[v2.id]), req)  # type: ignore[arg-type]
        v3 = await create_catalog_item(db, user, CatalogItemCreate(catalog="F", group_code="RC", model=f"F-RC-{mx:03d}", name="Ruchka sinov 1 oq"), req)  # type: ignore[arg-type]
        natija.append(("o'chirilgan -02 qayta berilmaydi → -03", v3.code, f"F-RC-{mx:03d}-03"))
        xz = await create_catalog_item(db, user, CatalogItemCreate(catalog="X", group_code="PR", name="Xizmat sinov", quantity=D(5), min_quantity=D(2), unit="xizmat"), req)  # type: ignore[arg-type]
        natija.append(("xizmatda qoldiq va chegara yo'q", (xz.quantity, xz.min_quantity), (D(0), None)))
        try:
            await create_catalog_item(db, user, CatalogItemCreate(catalog="F", group_code="QQ", name="x"), req)  # type: ignore[arg-type]
            natija.append(("noma'lum guruh rad etiladi", "qabul qilindi", 404))
        except HTTPException as e:
            natija.append(("noma'lum guruh rad etiladi", e.status_code, 404))

        # --- 7. Import: hammasi yoki hech biri
        before = await db.scalar(select(CatalogItem.id).order_by(CatalogItem.id.desc()).limit(1))
        try:
            await import_catalog_items(
                db, user,
                CatalogImport(rows=[CatalogItemCreate(catalog="F", group_code="RC", name="A"), CatalogItemCreate(catalog="F", group_code="ZZ", name="B")]),
                req,
            )  # type: ignore[arg-type]
        except HTTPException:
            await db.rollback()
        after = await db.scalar(select(CatalogItem.id).order_by(CatalogItem.id.desc()).limit(1))
        natija.append(("import: bitta xato qator — hech narsa yozilmadi", after, before))
        res = await import_catalog_items(
            db, user, CatalogImport(rows=[CatalogItemCreate(catalog="F", group_code="AK", name="Import 1"), CatalogItemCreate(catalog="F", group_code="AK", name="Import 2")]), req,
        )  # type: ignore[arg-type]
        natija.append(("import: 2 ta yangi kod, ketma-ket model", len(set(res.codes)), 2))

        # --- 8. Ro'yxat va ABC
        rows = await read_catalog_all(db, user)  # type: ignore[arg-type]
        kodlar = {r.code for r in rows}
        natija.append(("o'chirilgan ro'yxatda yo'q", v2.code in kodlar, False))
        abc = [r.abc for r in rows if r.catalog != "X"]
        natija.append(("ABC: A, B, C hammasi bor; xizmatda None", (set(abc) >= {"A", "B", "C"}, {r.abc for r in rows if r.catalog == "X"}), (True, {None})))
        qiymat = sorted(((r.quantity * (r.purchase_price or r.sale_price or 0), r.abc) for r in rows if r.catalog != "X"), key=lambda z: -z[0])
        natija.append(("eng qimmat qoldiq — A", qiymat[0][1], "A"))

    # --- 9. Importer narxni va o'chirilganni qayta yozmaydi
    subprocess.run([sys.executable, str(Path(__file__).parents[1] / "catalog_import.py"), "--apply"], check=True, capture_output=True)
    async with local_session() as db:
        x = await db.scalar(select(CatalogItem).where(CatalogItem.code == "F-RC-001-01"))
        d = await db.scalar(select(CatalogItem).where(CatalogItem.code == "M-LD-046-01"))
        natija.append(("catalog_import --apply narxni qayta yozmadi", (x.sale_price if x else None, d.sale_price if d else None), (D(5100), D(555000))))


asyncio.run(main())
xato = sum(1 for _, a, b in natija if a != b)
for nom, a, b in natija:
    print(f"  {'OK ' if a == b else 'XATO'} {nom}: olingan={a} kutilgan={b}")
print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")
