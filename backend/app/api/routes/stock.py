"""Materiallar ombori (TZ 4.5 kengaytmasi) — omborchi yuritadigan katalog.

TMO dan AYRIM bo'lim: TMO tayyor mahsulot qabul qiladi va u marshrutning oxirgi
posti, bu yerda esa xomashyo va furnitura qoldig'i turadi. Ekran ham boshqacha —
materiallar ombori monoblokda emas, oddiy kompyuterda ishlaydi, shuning uchun
odatdagi admin qobig'idagi jadval (sensorli kiosk emas).
"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, or_, select

from app.api.deps import ManagerUser, SessionDep, StaffReadUser, client_ip
from app.core.config import settings
from app.core.exceptions import DuplicateValueException
from app.crud import crud_stock_items, log_action
from app.models import StockItem
from app.models.enums import StockCatalog
from app.schemas.common import Message, Paginated
from app.schemas.stock import (
    StockGroup,
    StockItemCreate,
    StockItemRead,
    StockItemUpdate,
    StockMove,
    StockSummary,
)

router = APIRouter(prefix="/stock", tags=["stock"])

#: "Buyurtma berish kerak" sharti — bitta joyda, ro'yxat/guruh/xulosa bir xil sanasin.
_LOW = (StockItem.min_qty > 0) & (StockItem.qty < StockItem.min_qty)
_VISIBLE = StockItem.is_deleted == False  # noqa: E712


@router.get("/", response_model=Paginated[StockItemRead], operation_id="read_stock_items")
async def read_stock_items(
    db: SessionDep,
    _: StaffReadUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
    search: str | None = None,
    catalog: StockCatalog | None = None,
    group_code: str | None = None,
    low: bool = False,
) -> Paginated[StockItemRead]:
    """Pozitsiyalar ro'yxati. `low=true` — faqat minimal zaxiradan pastga tushganlar."""
    query = select(StockItem).where(_VISIBLE)
    if catalog is not None:
        query = query.where(StockItem.catalog == catalog)
    if group_code:
        query = query.where(StockItem.group_code == group_code.upper())
    if low:
        query = query.where(_LOW)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(StockItem.name.ilike(pattern), StockItem.code.ilike(pattern)))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(StockItem.code).offset(skip).limit(limit))).scalars().all()
    return Paginated(data=[StockItemRead.model_validate(i) for i in rows], count=total)


@router.get("/summary", response_model=StockSummary, operation_id="read_stock_summary")
async def read_stock_summary(db: SessionDep, _: StaffReadUser) -> StockSummary:
    """Sahifa tepasidagi uchta raqam. Qiymat XARID narxida — ombor qancha pul
    turibdi degan savolga sotuv narxi javob bermaydi."""
    row = (
        await db.execute(
            select(
                func.count(),
                func.count().filter(_LOW),
                func.coalesce(func.sum(StockItem.qty * func.coalesce(StockItem.purchase_uzs, 0)), 0),
            ).where(_VISIBLE)
        )
    ).one()
    return StockSummary(items=row[0], low=row[1], value_uzs=Decimal(row[2]))


@router.get("/groups", response_model=list[StockGroup], operation_id="read_stock_groups")
async def read_stock_groups(db: SessionDep, _: StaffReadUser) -> list[StockGroup]:
    """Filtr chiplari. Guruhlar katalogdan keladi (`F-RC` = Ruchkalar), ya'ni
    alohida jadval kerak emas — 28 ta guruh pozitsiyalarning o'zidan yig'iladi."""
    rows = (
        await db.execute(
            select(
                StockItem.catalog,
                StockItem.group_code,
                func.min(StockItem.group_name),
                func.count(),
                func.count().filter(_LOW),
            )
            .where(_VISIBLE)
            .group_by(StockItem.catalog, StockItem.group_code)
            .order_by(StockItem.catalog, StockItem.group_code)
        )
    ).all()
    return [
        StockGroup(catalog=c, group_code=code, group_name=name, items=items, low=low)
        for c, code, name, items, low in rows
    ]


@router.post("/", response_model=StockItemRead, status_code=201, operation_id="create_stock_item")
async def create_stock_item(
    db: SessionDep, current_user: ManagerUser, body: StockItemCreate, request: Request
) -> StockItem:
    exists = (await db.execute(select(StockItem.id).where(StockItem.code == body.code, _VISIBLE))).scalar_one_or_none()
    if exists is not None:
        raise DuplicateValueException(f"{body.code} kodi band.")
    item = StockItem(**body.model_dump())
    db.add(item)
    await db.flush()
    log_action(
        db,
        module="stock",
        action="created",
        user_id=current_user.id,
        entity_type="stock_item",
        entity_id=item.id,
        message=f"Pozitsiya qo'shildi: {item.code} — {item.name}",
        ip=client_ip(request),
    )
    await db.commit()
    return item


@router.patch("/{item_id}", response_model=StockItemRead, operation_id="update_stock_item")
async def update_stock_item(
    db: SessionDep, current_user: ManagerUser, item_id: int, body: StockItemUpdate, request: Request
) -> StockItem:
    item = await crud_stock_items.get_or_404(db, "Pozitsiya topilmadi.", id=item_id)
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(item, field, value)
    log_action(
        db,
        module="stock",
        action="updated",
        user_id=current_user.id,
        entity_type="stock_item",
        entity_id=item.id,
        message=f"Pozitsiya tahrirlandi: {item.code}",
        meta={"fields": sorted(changes)},
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/{item_id}/move", response_model=StockItemRead, operation_id="move_stock_item")
async def move_stock_item(
    db: SessionDep, current_user: ManagerUser, item_id: int, body: StockMove, request: Request
) -> StockItem:
    """KIRIM / CHIQIM. Alohida harakatlar jadvali YO'Q — har o'zgarish audit logga
    tushadi (`module=stock, action=move`), ya'ni "kim, qachon, qancha" savoliga
    javob bor. To'liq ombor kartochkasi kerak bo'lganda shu loglardan quriladi."""
    item = await crud_stock_items.get_or_404(db, "Pozitsiya topilmadi.", id=item_id)
    before = item.qty
    after = before + body.delta
    if after < 0:
        # `DuplicateValueException` — loyihadagi YAGONA 409. Nomi takroriy qiymat
        # deydi, lekin holat bir xil: so'rov bazaning hozirgi holatiga zid.
        raise DuplicateValueException(f"Qoldiq manfiy bo'lib qoladi: {before} - {abs(body.delta)}.")
    item.qty = after
    log_action(
        db,
        module="stock",
        action="move",
        user_id=current_user.id,
        entity_type="stock_item",
        entity_id=item.id,
        message=f"{'Kirim' if body.delta > 0 else 'Chiqim'}: {item.code} {before} -> {after}",
        meta={"delta": str(body.delta), "before": str(before), "after": str(after), "note": body.note},
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", response_model=Message, operation_id="delete_stock_item")
async def delete_stock_item(db: SessionDep, current_user: ManagerUser, item_id: int, request: Request) -> Message:
    item = await crud_stock_items.get_or_404(db, "Pozitsiya topilmadi.", id=item_id)
    log_action(
        db,
        module="stock",
        action="deleted",
        user_id=current_user.id,
        entity_type="stock_item",
        entity_id=item.id,
        message=f"Pozitsiya o'chirildi: {item.code} — {item.name}",
        ip=client_ip(request),
    )
    await crud_stock_items.delete(db, id=item_id)
    return Message(message=f"{item.code} o'chirildi.")
