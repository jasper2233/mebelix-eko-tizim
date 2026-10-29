"""Mustahkamlik (EKO 2.4, prototip qoidalari) — HAQIQIY Postgres, HAQIQIY parallel tranzaksiyalar.

    1) jurnal: `stock_movement` va `audit_log` ni UPDATE/DELETE — baza rad etadi
    2) baza cheklovlari: qoldiq < 0, rulon qoldig'i > hajm, partiya qoldig'i < 0 — rad
    3) solishtirish: seed + kirim + sotuv + berishdan keyin farq 0; qoldiqni jurnalsiz buzish — ushlanadi
    4) parallel: qoldiq 5, 10 ta bir vaqtdagi sotuv (har biri 1) — aniq 5 tasi o'tadi, qoldiq 0
    5) parallel: bitta list barkodi ikki joyda bir vaqtda skanerlanadi — faqat bittasi o'tadi
    7) storno: tegilmagan kirim — qoldiq qaytadi, barkodlar yopiladi, takror storno — rad;
       sotilgan kirim — rad; sotuv stornosi — qoldiq qaytadi; har biridan keyin solishtirish 0
    8) ikki kalit: yoqilganda yozgan odam o'zi tasdiqlay olmaydi, boshqasi tasdiqlaydi
Sinov bazasida yurgiziladi va ma'lumot QOLDIRADI (parallel sinov commit qiladi) — prod EMAS:
    cd backend && uv run python ../scripts/oracles/mustahkamlik_oracle.py
"""

import asyncio
from datetime import date
from decimal import Decimal as D

from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.db import local_session
from app.models import Client, Order, User
from app.models.enums import OrderStatus
from app.modules.ombor.models import CatalogItem, MaterialBirlik, StockDoc
from app.modules.ombor.schemas.stock import DocIn, DocLineIn
from app.modules.ombor.services import berish, birlik, rezerv, solishtirish
from app.modules.ombor.services.stock import DocError, adjust_quantity, confirm, save_draft
from app.modules.ombor.services.storno import storno
from app.services.settings_service import OMBOR_IKKI_KALIT, set_setting

natija: list[bool] = []


def tek(nom: str, olingan: object, kutilgan: object) -> None:
    ok = olingan == kutilgan
    natija.append(ok)
    print(f"  {'OK ' if ok else 'XATO'} {nom}: olingan={olingan} kutilgan={kutilgan}")


async def rad_sql(nom: str, sql: str, bor: str) -> None:
    async with local_session() as db:
        try:
            await db.execute(text(sql))
            await db.flush()
            tek(nom, "o'tib ketdi", f"rad: {bor}")
        except DBAPIError as e:
            tek(nom, bor in str(e), True)
        finally:
            await db.rollback()


async def farqlar() -> list[str]:
    async with local_session() as db:
        return [f"{f.tur}:{f.kalit}" for f in await solishtirish.solishtir(db)]


async def sotuv(item_id: int, n: int) -> bool:
    async with local_session() as db:
        doc = await save_draft(
            db,
            DocIn(
                kind="chiqim",
                doc_date=date.today(),
                head={"client": f"Parallel {n}"},
                lines=[DocLineIn(item_id=item_id, name="x", qty=D(1), price=D(1))],
            ),
            None,
        )
        try:
            await confirm(db, doc, None)
            await db.commit()
            return True
        except DocError:
            await db.rollback()
            return False


async def skan(order_id: int, barkod: str) -> bool:
    async with local_session() as db:
        order = await db.get(Order, order_id)
        assert order is not None
        try:
            await berish.skan_birlik(db, order, barkod, None)
            await db.commit()
            return True
        except berish.BerishError:
            await db.rollback()
            return False


async def main() -> None:
    print("1) jurnal o'zgarmaydi")
    await rad_sql("harakatni UPDATE", "UPDATE stock_movement SET qty = qty + 1", "jurnal faqat qo'shiladi")
    await rad_sql("harakatni DELETE", "DELETE FROM stock_movement", "jurnal faqat qo'shiladi")
    async with local_session() as db:
        await db.execute(
            text(
                "INSERT INTO audit_log (module, action, message, meta, is_deleted, created_at) VALUES ('x','x','x','{}',false,now())"
            )
        )
        await db.commit()
    await rad_sql("auditni UPDATE", "UPDATE audit_log SET message = 'o''zgardi'", "jurnal faqat qo'shiladi")
    await rad_sql("auditni DELETE", "DELETE FROM audit_log", "jurnal faqat qo'shiladi")

    print("2) baza cheklovlari")
    await rad_sql(
        "qoldiq < 0",
        "UPDATE catalog_item SET quantity = -1 WHERE id = (SELECT min(id) FROM catalog_item)",
        "ck_catalog_item_quantity_nonneg",
    )

    print("3) solishtirish")
    tek("seeddan keyin farq yo'q", await farqlar(), [])
    async with local_session() as db:
        q = select(CatalogItem).order_by(CatalogItem.id)
        a = (await db.execute(q.where(CatalogItem.catalog == "M", CatalogItem.unit == "list").limit(1))).scalar_one()
        await adjust_quantity(db, a, D(0), None)
        doc = await save_draft(
            db,
            DocIn(
                kind="kirim",
                doc_date=date.today(),
                head={"supplier": "Sinov", "rate": "12 800"},
                lines=[DocLineIn(item_id=a.id, name=a.name, qty=D(5), price=D(10))],
            ),
            None,
        )
        await confirm(db, doc, None)
        aid = a.id
        u0 = (await db.execute(select(MaterialBirlik).where(MaterialBirlik.item_id == aid))).scalars().first()
        assert u0 is not None
        await db.commit()
    await rad_sql(
        "rulon/list qoldig'i > hajm",
        f"UPDATE material_birlik SET qoldiq = 2 WHERE id = {u0.id}",
        "ck_material_birlik_qoldiq",
    )
    await rad_sql(
        "partiya qoldig'i < 0", f"UPDATE stock_lot SET qty_left = -1 WHERE item_id = {aid}", "ck_stock_lot_qty_left"
    )
    tek("kirimdan keyin farq yo'q", await farqlar(), [])

    print("4) parallel sotuv: qoldiq 5, 10 ta so'rov")
    natijalar = await asyncio.gather(*(sotuv(aid, n) for n in range(10)))
    async with local_session() as db:
        qoldi = (await db.get(CatalogItem, aid)).quantity  # type: ignore[union-attr]
    tek("aniq 5 tasi o'tdi", sum(natijalar), 5)
    tek("qoldiq 0", qoldi, D(0))
    tek("sotuvlardan keyin farq yo'q", await farqlar(), [])

    print("5) parallel skan: bitta list ikki joyda")
    async with local_session() as db:
        a = await db.get(CatalogItem, aid)
        assert a is not None
        doc = await save_draft(
            db,
            DocIn(
                kind="kirim",
                doc_date=date.today(),
                head={"supplier": "Sinov", "rate": "12 800"},
                lines=[DocLineIn(item_id=aid, name=a.name, qty=D(3), price=D(10))],
            ),
            None,
        )
        await confirm(db, doc, None)
        client = Client(full_name="Parallel")
        db.add(client)
        await db.flush()
        o = Order(
            number="PAR-1",
            client_id=client.id,
            status=OrderStatus.TECHNICAL_REVIEW,
            amount=D(1),
            material_usage=[{"name": "P", "code": "PAR", "kind": "sheet", "count": 3, "unit": "list"}],
        )
        db.add(o)
        await db.flush()
        await rezerv.apply_mapping(db, "sheet", "PAR", aid, D(1), None)
        await rezerv.reserve_for_order(db, o)
        await rezerv.approve(db, o.id, None)
        bir = (
            (
                await db.execute(
                    select(MaterialBirlik.barkod).where(MaterialBirlik.item_id == aid, MaterialBirlik.joy == "ombor")
                )
            )
            .scalars()
            .first()
        )
        oid = o.id
        await db.commit()
    assert bir is not None
    ikki = await asyncio.gather(skan(oid, bir), skan(oid, bir))
    tek("faqat bittasi o'tdi", sorted(ikki), [False, True])
    async with local_session() as db:
        a = await db.get(CatalogItem, aid)
        assert a is not None
        tek("qoldiq 2 (3 − 1)", a.quantity, D(2))
        tek("birliklar = qoldiq", await birlik.labeled(db, aid), D(2))
    tek("skandan keyin farq yo'q", await farqlar(), [])

    print("6) jurnalsiz buzilgan qoldiq ushlanadi")
    async with local_session() as db:
        await db.execute(text(f"UPDATE catalog_item SET quantity = quantity + 1 WHERE id = {aid}"))
        f = [x for x in await solishtirish.solishtir(db) if x.tur == "jurnal"]
        tek("jurnal farqi topildi", len(f), 1)
        await db.rollback()

    print("7) storno")
    async with local_session() as db:
        q0 = (await db.get(CatalogItem, aid)).quantity  # type: ignore[union-attr]
        k1 = await kirim(db, aid, 4)
        st = await storno(db, k1, None, "xato kiritildi")
        a = await db.get(CatalogItem, aid)
        tek("kirim stornosi: qoldiq qaytdi", a.quantity, q0)  # type: ignore[union-attr]
        tek("asl hujjat storno holatida, STR raqami", (k1.status, st.no.startswith("STR-")), ("storno", True))
        tek("barkodlar yopildi", await birlik.labeled(db, aid), q0)
        try:
            await storno(db, k1, None, "yana")
            tek("takror storno rad", False, True)
        except DocError:
            tek("takror storno rad", True, True)
        await db.commit()
    tek("kirim stornosidan keyin farq yo'q", await farqlar(), [])
    async with local_session() as db:
        # Band bo'lmagan alohida pozitsiya: yagona partiyasidan sotilsa — kirim stornosi rad
        b = (
            await db.execute(
                select(CatalogItem)
                .where(CatalogItem.catalog == "M", CatalogItem.unit == "list", CatalogItem.id != aid)
                .order_by(CatalogItem.id)
                .limit(1)
            )
        ).scalar_one()
        await adjust_quantity(db, b, D(0), None)
        bid = b.id
        k2id = (await kirim(db, bid, 2)).id
        await db.commit()
    await sotuv(bid, 99)
    async with local_session() as db:
        k2 = await db.get(StockDoc, k2id)
        assert k2 is not None
        try:
            await storno(db, k2, None, "sotilgan")
            tek("sotilgan kirim stornosi rad", False, True)
        except DocError as e:
            tek("sotilgan kirim stornosi rad", "allaqachon sotilgan" in str(e), True)
        await db.rollback()
    async with local_session() as db:
        s1 = (
            await db.execute(select(StockDoc).where(StockDoc.kind == "chiqim").order_by(StockDoc.id.desc()).limit(1))
        ).scalar_one()
        q1 = (await db.get(CatalogItem, bid)).quantity  # type: ignore[union-attr]
        await storno(db, s1, None, "mijoz qaytardi")
        tek("sotuv stornosi: +1", (await db.get(CatalogItem, bid)).quantity, q1 + 1)  # type: ignore[union-attr]
        await db.commit()
    tek("sotuv stornosidan keyin farq yo'q", await farqlar(), [])

    print("8) ikki kalit")
    async with local_session() as db:
        admin = (await db.execute(select(User).limit(1))).scalar_one()
        await set_setting(db, OMBOR_IKKI_KALIT, "1", admin.id)
        d = await save_draft(
            db,
            DocIn(
                kind="kirim",
                doc_date=date.today(),
                head={"supplier": "Ikki kalit", "rate": "12 800"},
                lines=[DocLineIn(item_id=aid, name="x", qty=D(1), price=D(2))],
            ),
            admin.id,
        )
        try:
            await confirm(db, d, admin.id)
            tek("yozgan odam tasdiqlay olmaydi", False, True)
        except DocError as e:
            tek("yozgan odam tasdiqlay olmaydi", "ikki kalit" in str(e), True)
        await confirm(db, d, None)  # boshqa xodim
        tek("boshqasi tasdiqladi", d.status, "confirmed")
        await set_setting(db, OMBOR_IKKI_KALIT, "0", admin.id)
        await db.commit()
    tek("oxirida farq yo'q", await farqlar(), [])

    print(f"\nXULOSA: {sum(natija)}/{len(natija)} to'g'ri")


async def kirim(db, item_id: int, qty: int) -> StockDoc:  # type: ignore[no-untyped-def]
    d = await save_draft(
        db,
        DocIn(
            kind="kirim",
            doc_date=date.today(),
            head={"supplier": "Storno sinov", "rate": "12 800"},
            lines=[DocLineIn(item_id=item_id, name="x", qty=D(qty), price=D(2))],
        ),
        None,
    )
    await confirm(db, d, None)
    return d


asyncio.run(main())
