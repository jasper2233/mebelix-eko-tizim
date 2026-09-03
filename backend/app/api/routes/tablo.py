"""TABLO data API: orders × stages live matrix. Read-only, any authenticated device."""

from datetime import date

from fastapi import APIRouter
from sqlalchemy import func, select, text
from sqlalchemy.orm import defer

from app.api.deps import CurrentUser, SessionDep
from app.api.routes.orders._common import _get_visible_order
from app.core.config import TASHKENT_TZ
from app.models import ORDER_FAT_COLUMNS, PART_FAT_COLUMNS, PRIORITY_RANK, Order, Part, PartRoute, Post, Product, Scan
from app.models.enums import OrderStatus
from app.schemas.tablo import StageAgg, TabloMatrix, TabloOrderDetail, TabloOrderRow, TabloPartRow, TabloPostCol
from app.services.metrics import part_volume

router = APIRouter(prefix="/tablo", tags=["tablo"])

# TABLO'da FAQAT ishlab chiqarishdagi buyurtmalar ko'rinadi.
#
# Buyurtma taxtadan hamma detali TMO dan o'tgan zahoti tushadi — bu aynan
# COMPLETED holatining o'zi: oxirgi marshrut qadami TMO qabuli, va oxirgi
# qadam yopilganda `scanning.record_scan_at` statusni COMPLETED qiladi.
# Ya'ni bu yerda alohida "tayyorlarni ham ko'rsat" sharti KERAK EMAS,
# status filtri o'zi shu ma'noni beradi.
#
# Managerning "TOPSHIRILDI" tugmasi taxtaga TA'SIR QILMAYDI — u DELIVERED
# holatini va topshirish sanasini yozadi, taxta esa undan oldin tozalangan
# bo'ladi. Sabab: devordagi ekran TSEXNING ishi uchun, tsexda esa TMO dan
# o'tgan buyurtma ustida bajariladigan ish qolmaydi. Topshirish — tijoriy
# qadam, u reestrda kuzatiladi.
#
# Ilgari 30 kunlik oyna bor edi, sababi "chegarasiz qoldirilsa ekran
# sekinlashadi (100 buyurtmada 28 ms -> 1.9 s)". O'sha o'lchov keyingi
# optimizatsiyadan (ORDER_FAT_COLUMNS defer + faqat kerakli ustunlar,
# 669 ms -> 175 ms) OLDIN olingan. 2026-08-26 da qayta o'lchandi: 19 buyurtma
# uchun 84-120 ms, og'ir qism `part_route` agregatsiyasi. Oyna endi umuman
# kerak emas: ro'yxatni TMO ning o'zi cheklaydi.


@router.get("/matrix", response_model=TabloMatrix, operation_id="read_tablo_matrix")
async def read_tablo_matrix(db: SessionDep, _: CurrentUser) -> TabloMatrix:
    posts = (
        (await db.execute(select(Post).where(Post.is_deleted == False).order_by(Post.order_index)))  # noqa: E712
        .scalars()
        .all()
    )
    posts_by_id = {p.id: p for p in posts}

    orders = (
        (
            await db.execute(
                select(Order)
                .options(*(defer(c) for c in ORDER_FAT_COLUMNS))
                .where(
                    Order.status == OrderStatus.PRODUCTION,
                    Order.is_deleted == False,  # noqa: E712
                )
                # Terminal ro'yxati bilan AYNAN bir xil tartib (`PRIORITY_RANK`):
                # ishchi o'z postida ko'rgan navbat devordagi taxta bilan
                # mos tushsin.
                .order_by(PRIORITY_RANK, Order.deadline.asc().nulls_last(), Order.id)
            )
        )
        .scalars()
        .all()
    )
    if not orders:
        return TabloMatrix(posts=[_post_col(p) for p in posts], orders=[])

    order_ids = [o.id for o in orders]
    # ORM obyektlari emas, faqat kerakli ustunlar: butun tsex bo'yicha o'n minglab
    # marshrut yig'iladi, natija esa har postga bir nechta raqam (669 ms -> 175 ms)
    routes = (
        await db.execute(
            select(
                PartRoute.order_id,
                PartRoute.post_id,
                PartRoute.total_done,
                PartRoute.total_required,
                Part.length,
                Part.width,
                Part.count.label("part_count"),  # Row.count band — Sequence metodi
                Part.edges,
            )
            .join(Part, Part.id == PartRoute.part_id)
            .where(
                PartRoute.order_id.in_(order_ids),
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
            )
        )
    ).all()

    # Oxirgi harakat: bitta agregat, faqat ro'yxatdagi buyurtmalar bo'yicha.
    # `ix_scan_order_post` shu filtrga tushadi (prodda 39 484 skan bilan
    # ishlatilgan indeks). Bekor qilingan skan hisobga olinmaydi — u qaytarilgan
    # ish, ya'ni "harakat" emas.
    kun = func.date(func.timezone(TASHKENT_TZ.key, Scan.created_at))
    last_day: dict[int, date] = dict(
        (
            await db.execute(
                select(Scan.order_id, func.max(kun))
                .where(
                    Scan.order_id.in_(order_ids),
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .group_by(Scan.order_id)
            )
        ).all()
    )
    # TSEX ishlagan kunlar — buyurtma filtrisiz: bir buyurtma turgan paytda
    # boshqasi ishlagan bo'lsa, o'sha kun "ish kuni" sanaladi. Oxirgi 60 kun
    # yetarli: undan uzoq turgan buyurtma baribir chegaradan oshgan.
    ish_kunlari = sorted(
        (
            await db.execute(
                select(kun)
                .where(
                    Scan.created_at > func.now() - text("interval '60 days'"),
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .group_by(kun)
            )
        )
        .scalars()
        .all()
    )

    agg: dict[tuple[int, int], StageAgg] = {}
    for row in routes:
        key = (row.order_id, row.post_id)
        post = posts_by_id[row.post_id]
        entry = agg.get(key)
        if entry is None:
            entry = StageAgg(post_id=row.post_id, done=0, total=0, volume_total=0.0, volume_done=0.0)
            agg[key] = entry
        entry.done += row.total_done
        entry.total += row.total_required
        vol = part_volume(str(post.code), length=row.length, width=row.width, count=row.part_count, edges=row.edges)
        entry.volume_total += vol
        if row.total_required:
            entry.volume_done += vol * (row.total_done / row.total_required)

    rows = [
        TabloOrderRow(
            id=o.id,
            number=o.number,
            name=o.project_name,
            deadline=o.deadline,
            status=str(o.status),
            priority=str(o.priority),
            stages={str(posts_by_id[pid].code): stage for (oid, pid), stage in agg.items() if oid == o.id},
            idle_days=(sum(1 for d in ish_kunlari if d > last_day[o.id]) if o.id in last_day else None),
        )
        for o in orders
    ]
    return TabloMatrix(posts=[_post_col(p) for p in posts], orders=rows)


@router.get("/orders/{order_id}", response_model=TabloOrderDetail, operation_id="read_tablo_order")
async def read_tablo_order(db: SessionDep, current_user: CurrentUser, order_id: int) -> TabloOrderDetail:
    """Drill-down: SONI NAZORATI — every part × stage."""
    # Reestrdagi o'qish yo'li bilan bir xil ko'rinuvchanlik: texnologdan
    # yashiringan buyurtma (DRAFT/CANCELLED) bu yerdan ham ochilmasin.
    order = await _get_visible_order(db, current_user, order_id)
    posts = {p.id: p for p in (await db.execute(select(Post))).scalars()}
    rows = (
        await db.execute(
            select(PartRoute, Part, Product.code)
            .join(Part, Part.id == PartRoute.part_id)
            .join(Product, Product.id == Part.product_id)
            # Faqat id/code/name/count o'qiladi — `xnc_summary` JSONB bekorga uzatilardi
            .options(*(defer(c) for c in PART_FAT_COLUMNS))
            .where(
                PartRoute.order_id == order_id,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
            )
            .order_by(Product.code, Part.code)
        )
    ).all()

    parts: dict[int, TabloPartRow] = {}
    for route, part, product_code in rows:
        row = parts.get(part.id)
        if row is None:
            row = TabloPartRow(
                part_id=part.id, code=f"{product_code}_{part.code}", name=part.name, count=part.count, stages={}
            )
            parts[part.id] = row
        # Bitta post marshrutda takrorlanishi mumkin (kromka -> prisadka -> kromka).
        # Katakcha post bo'yicha bo'lgani uchun qadamlar QO'SHILADI — aks holda
        # oxirgi qadam oldingisining ustiga yozilib, bajarilgan ish yo'qolardi.
        key = str(posts[route.post_id].code)
        agg = row.stages.get(key)
        if agg is None:
            row.stages[key] = StageAgg(
                post_id=route.post_id,
                done=route.total_done,
                total=route.total_required,
                volume_total=float(route.total_required),
                volume_done=float(route.total_done),
            )
        else:
            agg.done += route.total_done
            agg.total += route.total_required
            agg.volume_total += float(route.total_required)
            agg.volume_done += float(route.total_done)
    return TabloOrderDetail(id=order.id, number=order.number, name=order.project_name, parts=list(parts.values()))


def _post_col(p: Post) -> TabloPostCol:
    return TabloPostCol(
        id=p.id,
        code=str(p.code),
        name=p.name,
        unit=str(p.unit),
        order_index=p.order_index,
    )
