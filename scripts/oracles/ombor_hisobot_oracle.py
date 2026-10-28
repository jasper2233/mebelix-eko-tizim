"""Ombor hisoboti (docs/14 §11) — guruh bo'yicha aylanma, ABC va harakatsiz tovarlar.

HAQIQIY `GET /stock/report` handleri HAQIQIY Postgres ustida. Fixture qo'lda sanaladigan
qilib tanlangan — kutilgan raqamlar shu yerda yozilgan, koddan hisoblab chiqarilmaydi:

    F-RC-001-01   qoldiq 10, partiya 10 × 3 000            → qiymat 30 000
    F-RC-002-01   qoldiq  4, partiya  4 × 1 000            → qiymat  4 000
    F-KM-001-01   qoldiq  6, PARTIYASIZ, xarid 500         → qiymat  3 000   (zaxira narxidan)
    M-LD-005-05   qoldiq  0                                → qiymat      0
    X-RS-001-01   xizmat                                   → hisobotga UMUMAN kirmaydi

    Oraliqda: F-RC-001-01 ga +10 kirim va −3 chiqim, F-RC-002-01 ga +4 kirim.
    F-KM-001-01 ning harakati ORALIQDAN TASHQARIDA — u «harakatsiz».

Yurgizish (lokal sinov bazasi, prod EMAS):
    cd backend && set -a && . /tmp/oee_test.env && set +a \
      && uv run python ../scripts/oracles/ombor_hisobot_oracle.py
"""

import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, text

from app.modules.ombor.routes.stock import read_stock_report
from app.core.config import TASHKENT_TZ
from app.core.db import local_session
from app.models import CatalogItem, StockLot, StockMovement, User
from app.models.enums import UserRole

BUGUN = datetime.now(TASHKENT_TZ).replace(hour=12, minute=0, second=0, microsecond=0)
KECHA = BUGUN - timedelta(days=1)
ESKI = BUGUN - timedelta(days=60)


def mahsulot(code: str, name: str, qty, xarid, guruh_nomi: str) -> CatalogItem:
    katalog, guruh, model, variant = code.split("-")
    return CatalogItem(
        code=code,
        catalog=katalog,
        group_code=guruh,
        group_name=guruh_nomi,
        model_no=int(model),
        variant_no=int(variant),
        name=name,
        unit="dona",
        quantity=Decimal(qty),
        purchase_price=Decimal(xarid),
    )


async def main() -> None:
    natija: list[tuple[str, object, object]] = []
    async with local_session() as db:
        for jadval in (
            "stock_movement", "stock_lot", "stock_doc_line", "stock_doc",
            "kromka_measurement", "catalog_item", '"user"',
        ):
            await db.execute(text(f"TRUNCATE {jadval} RESTART IDENTITY CASCADE"))
        await db.commit()

        admin = User(username="omborchi", phone="+998900000009", hashed_password="x",
                     name="Omborchi", role=UserRole.SKLADCHI)
        rc1 = mahsulot("F-RC-001-01", "Ruchka 0014", 10, 3000, "Ruchkalar")
        rc2 = mahsulot("F-RC-002-01", "Ruchka 1055", 4, 1000, "Ruchkalar")
        km1 = mahsulot("F-KM-001-01", "Kromka PVC 19", 6, 500, "Kromka")
        ld = mahsulot("M-LD-005-05", "ldsp beliy tambrano", 0, 400000, "LDSP dekorlar")
        xz = mahsulot("X-RS-001-01", "Raspil", 0, 0, "Raspil / kesish")
        db.add_all([admin, rc1, rc2, km1, ld, xz])
        await db.flush()

        # Partiyalar: qiymat ULARDAN olinadi (dizayndagi `V(i)`)
        db.add_all([
            StockLot(item_id=rc1.id, received_on=KECHA.date(), qty=Decimal(10),
                     qty_left=Decimal(10), unit_cost=Decimal(3000), source="Kirim"),
            StockLot(item_id=rc2.id, received_on=KECHA.date(), qty=Decimal(4),
                     qty_left=Decimal(4), unit_cost=Decimal(1000), source="Kirim"),
        ])
        # Harakatlar: ikkitasi ORALIQDA, kromkaniki 60 kun oldin
        db.add_all([
            StockMovement(item_id=rc1.id, kind="kirim", qty=Decimal(10),
                          balance=Decimal(13), created_at=KECHA),
            StockMovement(item_id=rc1.id, kind="chiqim", qty=Decimal(-3),
                          balance=Decimal(10), created_at=KECHA),
            StockMovement(item_id=rc2.id, kind="kirim", qty=Decimal(4),
                          balance=Decimal(4), created_at=KECHA),
            StockMovement(item_id=km1.id, kind="kirim", qty=Decimal(6),
                          balance=Decimal(6), created_at=ESKI),
        ])
        await db.commit()

        r = await read_stock_report(db, admin, date_from=KECHA.date(), date_to=BUGUN.date())
        guruh = {f"{g.catalog}-{g.group_code}": g for g in r.groups}

        natija.append(("xizmat hisobotga kirmaydi", "X-RS" in guruh, False))
        natija.append(("guruhlar qiymat bo'yicha tartiblangan",
                       [f"{g.catalog}-{g.group_code}" for g in r.groups], ["F-RC", "F-KM", "M-LD"]))
        natija.append(("guruh nomi va pozitsiya soni",
                       (guruh["F-RC"].group_name, guruh["F-RC"].positions), ("Ruchkalar", 2)))
        natija.append(("qiymat PARTIYALARDAN (10×3000 + 4×1000)",
                       guruh["F-RC"].value, Decimal(34000)))
        natija.append(("partiyasiz pozitsiya — qoldiq × xarid (6×500)",
                       guruh["F-KM"].value, Decimal(3000)))
        natija.append(("qoldiqsiz guruh qiymati nol", guruh["M-LD"].value, Decimal(0)))
        natija.append(("oraliqdagi kirim va chiqim (10+4, 3)",
                       (guruh["F-RC"].qty_in, guruh["F-RC"].qty_out), (Decimal(14), Decimal(3))))
        natija.append(("oraliqdan tashqaridagi harakat sanalmaydi",
                       (guruh["F-KM"].qty_in, guruh["F-KM"].qty_out), (Decimal(0), Decimal(0))))
        natija.append(("jami qiymat = guruhlar yig'indisi",
                       r.value, sum((g.value for g in r.groups), Decimal(0))))
        natija.append(("pozitsiyalar soni xizmatsiz", r.positions, 4))

        # --- ABC
        abc = {a.cls: a for a in r.abc}
        natija.append(("ABC uchala sinf qaytadi", sorted(abc), ["A", "B", "C"]))
        natija.append(("ABC qiymatlari jamiga teng",
                       sum(a.value for a in r.abc), r.value))
        natija.append(("ABC ulushlari ~100%", sum(a.pct for a in r.abc) in (99, 100, 101), True))
        natija.append(("eng qimmat pozitsiya A sinfda",
                       abc["A"].value >= abc["B"].value >= abc["C"].value, True))

        # --- Harakatsizlar
        olik = {d.code for d in r.dead}
        natija.append(("harakatsiz — oraliqda qimirlamagani", olik, {"F-KM-001-01"}))
        natija.append(("qoldiqsiz pozitsiya harakatsizga kirmaydi", "M-LD-005-05" in olik, False))
        natija.append(("harakatsizlar soni", r.dead_total, 1))
        natija.append(("harakatsiz qatorida qoldiq va qiymat",
                       (r.dead[0].quantity, r.dead[0].value), (Decimal("6.000"), Decimal(3000))))

        # --- Oraliq: hammasi kirsa, harakatsiz qolmaydi
        keng = await read_stock_report(db, admin, date_from=ESKI.date(), date_to=BUGUN.date())
        natija.append(("keng oraliqda kromka ham qimirlagan", keng.dead_total, 0))
        keng_g = {f"{g.catalog}-{g.group_code}": g for g in keng.groups}
        natija.append(("keng oraliqda kromka kirimi ko'rinadi", keng_g["F-KM"].qty_in, Decimal(6)))

        # --- Yumshoq o'chirilgan harakat sanalmaydi
        mv = (await db.execute(select(StockMovement).where(StockMovement.item_id == rc2.id))).scalar_one()
        mv.is_deleted = True
        await db.commit()
        keyin = await read_stock_report(db, admin, date_from=KECHA.date(), date_to=BUGUN.date())
        keyin_g = {f"{g.catalog}-{g.group_code}": g for g in keyin.groups}
        natija.append(("o'chirilgan harakat aylanmaga kirmaydi", keyin_g["F-RC"].qty_in, Decimal(10)))
        natija.append(("harakati o'chgach pozitsiya harakatsizga qo'shiladi", keyin.dead_total, 2))

    xato = sum(1 for _, olingan, kutilgan in natija if olingan != kutilgan)
    for nom, olingan, kutilgan in natija:
        print(f"  {'OK ' if olingan == kutilgan else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")
    print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")


asyncio.run(main())
