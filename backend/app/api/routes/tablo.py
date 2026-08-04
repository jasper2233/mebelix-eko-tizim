"""TABLO data API (TZ 9): orders × stages live matrix. Read-only, any authenticated device."""

from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import defer

from app.api.deps import CurrentUser, SessionDep
from app.crud import crud_orders
from app.models import ORDER_FAT_COLUMNS, Order, Part, PartRoute, Post, Product
from app.models.enums import OrderStatus
from app.services.metrics import part_volume

router = APIRouter(prefix="/tablo", tags=["tablo"])

# Yakunlangan buyurtma taxtada shuncha kun turadi. Chegarasiz qoldirilsa
# "topshirildi" bosilmagan har bir buyurtma abadiy qolib, sex ekrani yildan
# yilga sekinlashardi (o'lchov: 100 buyurtmada 28 ms -> 1.9 s).
COMPLETED_WINDOW = timedelta(days=30)


class StageAgg(BaseModel):
    post_id: int
    done: int
    total: int
    volume_total: float  # unit amount (m² / meter / dona) per post unit
    volume_done: float


class TabloOrderRow(BaseModel):
    id: int
    number: str
    name: str | None
    deadline: date | None
    status: str
    stages: dict[str, StageAgg]  # keyed by post code


class TabloMatrix(BaseModel):
    posts: list[dict[str, Any]]
    orders: list[TabloOrderRow]


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
                    or_(
                        Order.status == OrderStatus.PRODUCTION,
                        Order.completed_at >= datetime.now(UTC) - COMPLETED_WINDOW,
                    ),
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
        return TabloMatrix(posts=[_post_dict(p) for p in posts], orders=[])

    order_ids = [o.id for o in orders]
    # ORM obyektlari emas, faqat kerakli ustunlar: butun sex bo'yicha o'n minglab
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
    return TabloMatrix(posts=[_post_dict(p) for p in posts], orders=rows)


class TabloPartRow(BaseModel):
    part_id: int
    code: str
    name: str
    count: int
    stages: dict[str, StageAgg]


class TabloOrderDetail(BaseModel):
    id: int
    number: str
    name: str | None
    parts: list[TabloPartRow]


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
        row.stages[str(posts[route.post_id].code)] = StageAgg(
            post_id=route.post_id,
            done=route.total_done,
            total=route.total_required,
            volume_total=float(route.total_required),
            volume_done=float(route.total_done),
        )
    return TabloOrderDetail(id=order.id, number=order.number, name=order.project_name, parts=list(parts.values()))


def _post_dict(p: Post) -> dict[str, Any]:
    return {
        "id": p.id,
        "code": str(p.code),
        "name": p.name,
        "unit": str(p.unit),
        "color": p.color,
        "order_index": p.order_index,
    }
