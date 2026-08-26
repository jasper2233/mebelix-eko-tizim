"""TABLO data API (TZ 9): orders × stages live matrix. Read-only, any authenticated device."""

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import defer

from app.api.deps import CurrentUser, SessionDep
from app.crud import crud_orders
from app.models import ORDER_FAT_COLUMNS, Order, Part, PartRoute, Post, Product
from app.models.enums import OrderStatus
from app.schemas.tablo import StageAgg, TabloMatrix, TabloOrderDetail, TabloOrderRow, TabloPartRow, TabloPostCol
from app.services.metrics import part_volume

router = APIRouter(prefix="/tablo", tags=["tablo"])

# TABLO'da nima ko'rinadi: ishlab chiqarishdagi VA tayyor bo'lgan buyurtmalar.
# Tayyor buyurtma taxtadan FAQAT "topshirildi" belgilangach tushadi (TMO
# `deliver_tmo_order` yoki `orders.deliver_order`) — vaqt chegarasi YO'Q.
#
# Ilgari 30 kunlik oyna bor edi, sababi "chegarasiz qoldirilsa ekran
# sekinlashadi (100 buyurtmada 28 ms -> 1.9 s)". O'sha o'lchov keyingi
# optimizatsiyadan (ORDER_FAT_COLUMNS defer + faqat kerakli ustunlar,
# 669 ms -> 175 ms) OLDIN olingan. 2026-08-26 da qayta o'lchandi: 19 buyurtma
# uchun 84-120 ms, va og'ir qism `part_route` bo'yicha agregatsiya — u BUTUN
# jadvalni skanerlaydi, ya'ni oyna uni qisqartirmasdi ham. O'sish uchun
# `ix_part_route_order_post` indeksi bor.
#
# Oyna olib tashlanishining MAQSADI ham shu: "topshirildi" bosilmagan buyurtma
# taxtada qolib ko'zga tashlanishi kerak — u to'xtab qolgan oqim belgisi.
# Oyna esa aksincha, muammo surunkali bo'lgach uni JIMGINA yashirardi.


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
                    Order.status.in_([OrderStatus.PRODUCTION, OrderStatus.COMPLETED]),
                    Order.is_deleted == False,  # noqa: E712
                )
                .order_by(Order.deadline.asc().nulls_last(), Order.id)
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
            stages={str(posts_by_id[pid].code): stage for (oid, pid), stage in agg.items() if oid == o.id},
        )
        for o in orders
    ]
    return TabloMatrix(posts=[_post_col(p) for p in posts], orders=rows)


@router.get("/orders/{order_id}", response_model=TabloOrderDetail, operation_id="read_tablo_order")
async def read_tablo_order(db: SessionDep, _: CurrentUser, order_id: int) -> TabloOrderDetail:
    """Drill-down (TZ 9.5): SONI NAZORATI — every part × stage."""
    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)
    posts = {p.id: p for p in (await db.execute(select(Post))).scalars()}
    rows = (
        await db.execute(
            select(PartRoute, Part, Product.code)
            .join(Part, Part.id == PartRoute.part_id)
            .join(Product, Product.id == Part.product_id)
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
