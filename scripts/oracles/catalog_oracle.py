"""Mahsulotlar ombori katalogi — import va API.

`scripts/catalog_import.py` HAQIQIY CSV ni HAQIQIY bazaga yuklaydi, so'ng
`/catalog` handlerlari o'sha ma'lumot ustida chaqiriladi.

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . /tmp/oee_test.env && set +a \
      && uv run python ../scripts/oracles/catalog_oracle.py
"""

import asyncio
import csv
import importlib.util
import os
import re
from decimal import Decimal

from sqlalchemy import func, select, text

from app.api.deps import require_roles
from app.api.routes.catalog import read_catalog_groups, read_catalog_items, update_catalog_item
from app.core.db import local_session
from app.core.exceptions import ForbiddenException
from app.models import CatalogItem, User
from app.models.enums import UserRole
from app.schemas.catalog import CatalogItemUpdate

SCRIPTS = os.path.join(os.path.dirname(__file__), "..")
CSV_FILE = os.path.join(SCRIPTS, "catalog.csv")
KOD = re.compile(r"^[MFX]-[A-Z]{2}-\d{3}-\d{2}$")


def importni_yukla():
    spec = importlib.util.spec_from_file_location(
        "catalog_import", os.path.abspath(os.path.join(SCRIPTS, "catalog_import.py"))
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


class SoxtaRequest:
    """`client_ip` faqat `request.client` ni o'qiydi."""

    client = None


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    imp = importni_yukla()

    with open(CSV_FILE, encoding="utf-8") as f:
        satrlar = list(csv.DictReader(f))
    natija.append(("CSV dagi hamma kod qoidaga mos",
                   sum(1 for r in satrlar if not KOD.match(r["code"])), 0))
    natija.append(("CSV da takror kod yo'q",
                   len({r["code"] for r in satrlar}), len(satrlar)))

    async with local_session() as db:
        await db.execute(text("TRUNCATE catalog_item RESTART IDENTITY CASCADE"))
        await db.execute(text('TRUNCATE "user" RESTART IDENTITY CASCADE'))
        db.add_all([
            User(username="skladchi", phone="+998900000004", hashed_password="x",
                 name="Mahsulot omborchisi", role=UserRole.SKLADCHI),
            User(username="omborchi", phone="+998900000005", hashed_password="x",
                 name="TMO omborchisi", role=UserRole.OMBORCHI),
            User(username="texnolog", phone="+998900000006", hashed_password="x",
                 name="Texnolog", role=UserRole.TEXNOLOG),
        ])
        await db.commit()

    yangi, yangilandi = await imp.bazaga()
    natija.append(("import: hammasi yangi", (yangi, yangilandi), (len(satrlar), 0)))

    async with local_session() as db:
        kim = {u.role: u for u in (await db.execute(select(User))).scalars()}
        user = kim[UserRole.SKLADCHI]

        # --- Huquqlar: dep'larning O'ZI chaqiriladi (endpoint bilan bir xil qoida)
        async def ruxsat(dep, u) -> bool:
            try:
                await dep(u)
            except ForbiddenException:
                return False
            return True

        oqish = require_roles(UserRole.MANAGER, UserRole.TEXNOLOG, UserRole.DIRECTOR, UserRole.SKLADCHI)
        yozish = require_roles(UserRole.MANAGER, UserRole.SKLADCHI)
        natija.append(("skladchi katalogni o'qiydi", await ruxsat(oqish, kim[UserRole.SKLADCHI]), True))
        natija.append(("skladchi qoldiqni yozadi", await ruxsat(yozish, kim[UserRole.SKLADCHI]), True))
        natija.append(("texnolog o'qiydi, lekin yozmaydi",
                       (await ruxsat(oqish, kim[UserRole.TEXNOLOG]),
                        await ruxsat(yozish, kim[UserRole.TEXNOLOG])), (True, False)))
        # TMO omborchisi — BOSHQA ombor: bu katalogga umuman kirmaydi
        natija.append(("TMO omborchisi kirmaydi",
                       (await ruxsat(oqish, kim[UserRole.OMBORCHI]),
                        await ruxsat(yozish, kim[UserRole.OMBORCHI])), (False, False)))
        jami = await db.scalar(select(func.count()).select_from(CatalogItem))
        natija.append(("bazada CSV dagicha", jami, len(satrlar)))

        # --- Kategoriya daraxti
        tree = await read_catalog_groups(db, user)
        natija.append(("katalog bo'limlari", sorted(tree.totals), ["F", "M", "X"]))
        natija.append(("bo'limlar yig'indisi = jami", sum(tree.totals.values()), len(satrlar)))
        natija.append(("guruh sanoqlari yig'indisi = jami",
                       sum(g.count for g in tree.groups), len(satrlar)))
        ld = next(g for g in tree.groups if g.catalog == "M" and g.group_code == "LD")
        natija.append(("guruh nomi kodda emas, varaqdan", ld.group_name, "LDSP dekorlar"))
        natija.append(("guruhlar tartiblangan",
                       [(g.catalog, g.group_code) for g in tree.groups]
                       == sorted((g.catalog, g.group_code) for g in tree.groups), True))

        # --- Ro'yxat va filtrlar
        hammasi = await read_catalog_items(db, user, limit=1)
        natija.append(("ro'yxat jami sonni beradi", hammasi.count, len(satrlar)))
        natija.append(("sahifa hajmi hurmat qilinadi", len(hammasi.data), 1))
        natija.append(("tartib: katalog, guruh, model, variant",
                       (hammasi.data[0].catalog, hammasi.data[0].group_code), ("F", "AK")))

        furnitura = await read_catalog_items(db, user, catalog="F", limit=1)
        natija.append(("katalog filtri", furnitura.count,
                       sum(1 for r in satrlar if r["catalog"] == "F")))
        ruchka = await read_catalog_items(db, user, catalog="F", group_code="RC", limit=1)
        natija.append(("guruh filtri", ruchka.count,
                       sum(1 for r in satrlar if r["code"].startswith("F-RC"))))

        kod_izlash = await read_catalog_items(db, user, search="M-LD-005-05")
        natija.append(("kod bo'yicha qidiruv", [i.code for i in kod_izlash.data], ["M-LD-005-05"]))
        dekor_izlash = await read_catalog_items(db, user, search="tambrano", limit=5)
        natija.append(("dekor nomi bo'yicha qidiruv topdi", dekor_izlash.count > 0, True))

        # --- Bitta pozitsiya to'liq tushdimi
        bitta = next(i for i in (await read_catalog_items(db, user, search="M-LD-005-05")).data)
        natija.append(("kod qismlari ustun bo'lib yotadi",
                       (bitta.catalog, bitta.group_code, bitta.model_no, bitta.variant_no),
                       ("M", "LD", 5, 5)))
        natija.append(("artikul son emas, matn", bitta.article, "117003"))
        natija.append(("o'lcham va qalinlik", (bitta.size_text, bitta.thickness_mm),
                       ("2750x1830x16", Decimal("16.0"))))
        natija.append(("dekor rasmi Dekorlar varag'idan ulandi",
                       (bitta.image_url or "").startswith("https://"), True))
        natija.append(("matritsa variant raqamiga mos (05 = kamin)", bitta.matrix, "kamin"))
        natija.append(("yangi pozitsiya qoldig'i nol", bitta.quantity, Decimal("0.000")))

        # --- Omborchi qoldiq va joyni yozadi
        yangilangan = await update_catalog_item(
            db, user, SoxtaRequest(), bitta.id,
            CatalogItemUpdate(quantity=Decimal("12.5"), location="A-3", min_quantity=Decimal(5)),
        )
        natija.append(("qoldiq va joy yozildi",
                       (yangilangan.quantity, yangilangan.location, yangilangan.min_quantity),
                       (Decimal("12.500"), "A-3", Decimal("5.000"))))
        natija.append(("katalog maydonlari tegilmadi",
                       (yangilangan.code, yangilangan.name), (bitta.code, bitta.name)))

        past = await read_catalog_items(db, user, low_stock=True)
        natija.append(("chegaradan past emas — ro'yxatda yo'q", past.count, 0))
        await update_catalog_item(db, user, SoxtaRequest(), bitta.id,
                                  CatalogItemUpdate(quantity=Decimal(1)))
        past = await read_catalog_items(db, user, low_stock=True)
        natija.append(("chegaradan past — ro'yxatda", [i.code for i in past.data], [bitta.code]))

        arxiv = await update_catalog_item(db, user, SoxtaRequest(), bitta.id,
                                          CatalogItemUpdate(status="Arxiv"))
        natija.append(("holat Arxivga o'tdi", arxiv.status, "Arxiv"))
        aktiv = await read_catalog_items(db, user, status="Aktiv", limit=1)
        natija.append(("arxiv aktivlar ro'yxatidan chiqdi", aktiv.count, len(satrlar) - 1))

    # --- Qayta import: qoldiq va joylashuv SAQLANADI
    yangi2, yangilandi2 = await imp.bazaga()
    natija.append(("qayta import yangi qo'shmadi", (yangi2, yangilandi2), (0, len(satrlar))))
    async with local_session() as db:
        item = (await db.execute(select(CatalogItem).where(CatalogItem.code == "M-LD-005-05"))).scalar_one()
        natija.append(("qoldiq va joy saqlanib qoldi",
                       (item.quantity, item.location), (Decimal("1.000"), "A-3")))
        # 2026-10-16 dan holat (va nom, narx, izoh) OMBORNIKI — varaq qayta yozmaydi (docs/14 §8, TODO #9)
        natija.append(("holat omborniki — varaq uni qaytarmaydi (Arxiv qoladi)", item.status, "Arxiv"))
        jami = await db.scalar(select(func.count()).select_from(CatalogItem))
        natija.append(("takror yozuv paydo bo'lmadi", jami, len(satrlar)))

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
