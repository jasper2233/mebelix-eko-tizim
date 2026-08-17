"""Materiallar ombori (TZ 4.5 kengaytmasi) — omborchi yuritadigan katalog.

TMO dan AYRIM bo'lim: TMO tayyor mahsulot qabul qiladi va u marshrutning oxirgi
posti, bu yerda esa xomashyo va furnitura qoldig'i turadi. Ekran ham boshqacha —
materiallar ombori monoblokda emas, oddiy kompyuterda ishlaydi, shuning uchun
odatdagi admin qobig'idagi jadval (sensorli kiosk emas).
"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, or_, select

from app.api.deps import SessionDep, StockUser, client_ip
from app.core.config import settings
from app.core.exceptions import DuplicateValueException, NotFoundException
from app.crud import crud_stock_items, log_action
from app.models import Client, Order, Payment, Sale, StockItem, StockMove
from app.models.enums import SaleStatus, StockCatalog, StockMoveKind
from app.models.user import User
from app.schemas.common import Message, Paginated
from app.schemas.stock import (
    PaymentCreate,
    PaymentRead,
    SaleCreate,
    SaleRead,
    SaleSummary,
    StockGroup,
    StockItemCreate,
    StockItemRead,
    StockItemUpdate,
    StockMoveRead,
    StockMoveRequest,
    StockSummary,
)

router = APIRouter(prefix="/stock", tags=["stock"])

#: "Buyurtma berish kerak" sharti — bitta joyda, ro'yxat/guruh/xulosa bir xil sanasin.
_LOW = (StockItem.min_qty > 0) & (StockItem.qty < StockItem.min_qty)
_VISIBLE = StockItem.is_deleted == False  # noqa: E712


@router.get("/", response_model=Paginated[StockItemRead], operation_id="read_stock_items")
async def read_stock_items(
    db: SessionDep,
    _: StockUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
    search: str | None = None,
    catalog: StockCatalog | None = None,
    group_code: str | None = None,
    low: bool = False,
) -> Paginated[StockItemRead]:
    """Tovarlar ro'yxati. `low=true` — faqat minimal zaxiradan pastga tushganlar."""
    query = select(StockItem).where(_VISIBLE)
    if catalog is not None:
        query = query.where(StockItem.catalog == catalog)
    if group_code:
        query = query.where(StockItem.group_code == group_code.upper())
    if low:
        query = query.where(_LOW)
    if search:
        # GURUH NOMI ham qidiriladi: jadvalda alohida "Guruh" ustuni yo'q
        # (kod prefiksi va tanlangan guruh uni allaqachon aytadi), shuning uchun
        # "petlya" deb yozgan omborchi butun guruhni topa olishi kerak.
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                StockItem.name.ilike(pattern),
                StockItem.code.ilike(pattern),
                StockItem.group_name.ilike(pattern),
            )
        )

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(StockItem.code).offset(skip).limit(limit))).scalars().all()
    return Paginated(data=[StockItemRead.model_validate(i) for i in rows], count=total)


@router.get("/summary", response_model=StockSummary, operation_id="read_stock_summary")
async def read_stock_summary(db: SessionDep, _: StockUser) -> StockSummary:
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
async def read_stock_groups(db: SessionDep, _: StockUser) -> list[StockGroup]:
    """Filtr chiplari. Guruhlar katalogdan keladi (`F-RC` = Ruchkalar), ya'ni
    alohida jadval kerak emas — 28 ta guruh tovarlarning o'zidan yig'iladi."""
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


async def _next_code(db: SessionDep, catalog: StockCatalog, group_code: str) -> str:
    """Guruhdagi keyingi bo'sh kod: `F-RC-032-01`.

    Excel katalogida "Keyingi bo'sh model kodi" ustuni bor va uni odam qo'lda
    yuritardi — bu yerda o'sha ish serverga o'tdi, ya'ni yangi tovar
    qo'shayotgan odam kod o'ylab topmaydi va ikki kishi bir vaqtda qo'shsa
    unique indeks ikkinchisini rad etadi (jimgina ustiga yozilmaydi).
    """
    prefix = f"{catalog.value}-{group_code}-"
    codes = (await db.execute(select(StockItem.code).where(StockItem.code.startswith(prefix)))).scalars().all()
    used = {int(part) for c in codes if (part := c.split("-")[2] if len(c.split("-")) > 2 else "").isdigit()}
    return f"{prefix}{max(used, default=0) + 1:03d}-01"


@router.post("/", response_model=StockItemRead, status_code=201, operation_id="create_stock_item")
async def create_stock_item(
    db: SessionDep, current_user: StockUser, body: StockItemCreate, request: Request
) -> StockItem:
    data = body.model_dump()
    group_code = data["group_code"] = data["group_code"].upper()
    code = data["code"] = data["code"] or await _next_code(db, body.catalog, group_code)
    exists = (await db.execute(select(StockItem.id).where(StockItem.code == code, _VISIBLE))).scalar_one_or_none()
    if exists is not None:
        raise DuplicateValueException(f"{code} kodi band.")
    item = StockItem(**data)
    db.add(item)
    await db.flush()
    log_action(
        db,
        module="stock",
        action="created",
        user_id=current_user.id,
        entity_type="stock_item",
        entity_id=item.id,
        message=f"Tovar qo'shildi: {item.code} — {item.name}",
        ip=client_ip(request),
    )
    await db.commit()
    return item


@router.patch("/{item_id}", response_model=StockItemRead, operation_id="update_stock_item")
async def update_stock_item(
    db: SessionDep, current_user: StockUser, item_id: int, body: StockItemUpdate, request: Request
) -> StockItem:
    item = await crud_stock_items.get_or_404(db, "Tovar topilmadi.", id=item_id)
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
        message=f"Tovar tahrirlandi: {item.code}",
        meta={"fields": sorted(changes)},
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(item)
    return item


async def _apply_move(
    db: SessionDep,
    *,
    item: StockItem,
    qty: Decimal,
    kind: StockMoveKind,
    user_id: int,
    order_id: int | None = None,
    sale_id: int | None = None,
    price_uzs: Decimal | None = None,
    note: str | None = None,
) -> StockMove:
    """Qoldiqni o'zgartiradi va harakatni yozadi — HAR DOIM birga.

    `stock_item.qty` harakatlar yig'indisining keshi: ro'yxatda 638 tovar
    uchun har safar summa hisoblash sekin bo'lardi. Kesh va manba bir joyda
    yangilanadi, aks holda ular ajralib ketardi.
    """
    after = item.qty + qty
    if after < 0:
        # `DuplicateValueException` — loyihadagi YAGONA 409. Nomi takroriy qiymat
        # deydi, lekin holat bir xil: so'rov bazaning hozirgi holatiga zid.
        raise DuplicateValueException(f"{item.code}: qoldiq yetmaydi ({item.qty} bor, {abs(qty)} so'ralyapti).")
    item.qty = after
    move = StockMove(
        stock_item_id=item.id,
        qty=qty,
        kind=kind,
        order_id=order_id,
        sale_id=sale_id,
        price_uzs=price_uzs,
        note=note,
        user_id=user_id,
    )
    db.add(move)
    await db.flush()
    return move


@router.post("/{item_id}/move", response_model=StockItemRead, operation_id="move_stock_item")
async def move_stock_item(
    db: SessionDep, current_user: StockUser, item_id: int, body: StockMoveRequest, request: Request
) -> StockItem:
    """KIRIM / BUYURTMAGA BERISH / HISOBDAN CHIQIM.

    SOTUV bu yerda emas — u `POST /stock/sales` orqali, chunki sotuvda hujjat,
    mijoz va to'lov bo'ladi va ular bitta tranzaksiyada yozilishi kerak.
    """
    if body.kind == StockMoveKind.SOTUV:
        raise HTTPException(status_code=422, detail="Sotuv `/stock/sales` orqali rasmiylashtiriladi.")
    item = await crud_stock_items.get_or_404(db, "Tovar topilmadi.", id=item_id)

    order_id = None
    if body.kind == StockMoveKind.BUYURTMA:
        if body.order_id is None:
            raise HTTPException(status_code=422, detail="Buyurtma tanlanmagan.")
        order = await db.get(Order, body.order_id)
        if order is None or order.is_deleted:
            raise NotFoundException("Buyurtma topilmadi.")
        order_id = order.id
        if body.delta > 0:
            raise HTTPException(status_code=422, detail="Buyurtmaga berish CHIQIM: miqdor manfiy bo'lishi kerak.")

    before = item.qty
    # Narx harakat paytida muzlatiladi: buyurtmada TANNARX (xarid), kirimda ham xarid
    price = body.price_uzs if body.price_uzs is not None else item.purchase_uzs
    move = await _apply_move(
        db,
        item=item,
        qty=body.delta,
        kind=body.kind,
        user_id=current_user.id,
        order_id=order_id,
        price_uzs=price,
        note=body.note,
    )
    log_action(
        db,
        module="stock",
        action="move",
        user_id=current_user.id,
        entity_type="stock_item",
        entity_id=item.id,
        message=f"{body.kind.value}: {item.code} {before} -> {item.qty}",
        meta={"move_id": move.id, "kind": body.kind.value, "order_id": order_id, "note": body.note},
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", response_model=Message, operation_id="delete_stock_item")
async def delete_stock_item(db: SessionDep, current_user: StockUser, item_id: int, request: Request) -> Message:
    item = await crud_stock_items.get_or_404(db, "Tovar topilmadi.", id=item_id)
    log_action(
        db,
        module="stock",
        action="deleted",
        user_id=current_user.id,
        entity_type="stock_item",
        entity_id=item.id,
        message=f"Tovar o'chirildi: {item.code} — {item.name}",
        ip=client_ip(request),
    )
    await crud_stock_items.delete(db, id=item_id)
    return Message(message=f"{item.code} o'chirildi.")


# ---------- Harakatlar tarixi ----------


async def _move_reads(db: SessionDep, moves: list[StockMove]) -> list[StockMoveRead]:
    """Harakatlarga o'qiladigan nom qo'shadi — bitta so'rovda.

    N ta harakat uchun N ta `db.get` qilish ro'yxatni sekinlashtirardi.
    """
    if not moves:
        return []
    items = {
        i.id: i
        for i in (await db.execute(select(StockItem).where(StockItem.id.in_({m.stock_item_id for m in moves}))))
        .scalars()
        .all()
    }
    order_ids = {m.order_id for m in moves if m.order_id}
    orders: dict[int, str] = {}
    if order_ids:
        orders = {
            o.id: o.number for o in (await db.execute(select(Order).where(Order.id.in_(order_ids)))).scalars().all()
        }
    user_ids = {m.user_id for m in moves if m.user_id}
    users: dict[int, str] = {}
    if user_ids:
        users = {
            u.id: (u.name or u.username or "")
            for u in (await db.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        }
    out = []
    for m in moves:
        row = StockMoveRead.model_validate(m)
        item = items.get(m.stock_item_id)
        row.item_code = item.code if item else ""
        row.item_name = item.name if item else ""
        row.order_number = orders.get(m.order_id or 0)
        row.user_name = users.get(m.user_id or 0)
        out.append(row)
    return out


@router.get("/moves", response_model=list[StockMoveRead], operation_id="read_stock_moves")
async def read_stock_moves(
    db: SessionDep,
    _: StockUser,
    item_id: int | None = None,
    order_id: int | None = None,
    kind: StockMoveKind | None = None,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
) -> list[StockMoveRead]:
    """Ombor harakatlari — tovar kartochkasi (`item_id`) yoki buyurtmaga
    berilganlar (`order_id`). Buyurtma sahifasidagi "Ombordan berilgan" bloki
    shu yerdan oziqlanadi."""
    query = select(StockMove).where(StockMove.is_deleted == False)  # noqa: E712
    if item_id is not None:
        query = query.where(StockMove.stock_item_id == item_id)
    if order_id is not None:
        query = query.where(StockMove.order_id == order_id)
    if kind is not None:
        query = query.where(StockMove.kind == kind)
    moves = list((await db.execute(query.order_by(StockMove.id.desc()).limit(limit))).scalars().all())
    return await _move_reads(db, moves)


# ---------- Sotuv ----------


def _sale_status(total: Decimal, paid: Decimal) -> SaleStatus:
    if paid >= total:
        return SaleStatus.PAID
    return SaleStatus.PARTIAL if paid > 0 else SaleStatus.DEBT


async def _sale_read(db: SessionDep, sale: Sale, *, full: bool = False) -> SaleRead:
    row = SaleRead.model_validate(sale)
    row.debt_uzs = sale.total_uzs - sale.paid_uzs
    if sale.client_id:
        client = await db.get(Client, sale.client_id)
        row.client_name = client.full_name if client else None
    if sale.user_id:
        user = await db.get(User, sale.user_id)
        row.user_name = (user.name or user.username) if user else None
    if full:
        moves = list(
            (await db.execute(select(StockMove).where(StockMove.sale_id == sale.id).order_by(StockMove.id)))
            .scalars()
            .all()
        )
        row.lines = await _move_reads(db, moves)
        payments = list(
            (
                await db.execute(
                    select(Payment)
                    .where(Payment.sale_id == sale.id, Payment.is_deleted == False)  # noqa: E712
                    .order_by(Payment.id)
                )
            )
            .scalars()
            .all()
        )
        row.payments = [PaymentRead.model_validate(p) for p in payments]
    return row


@router.post("/sales", response_model=SaleRead, status_code=201, operation_id="create_sale")
async def create_sale(db: SessionDep, current_user: StockUser, body: SaleCreate, request: Request) -> SaleRead:
    """Ombordan sotuv: satrlar + ixtiyoriy to'lov.

    To'lanmagan qism QARZ bo'lib qoladi va qarzdorlar ro'yxatiga tushadi —
    shuning uchun qarzli sotuvda MIJOZ majburiy: kimdan undirishni bilmasak,
    yozuvning ma'nosi yo'q. Naqd to'langan sotuvda mijoz shart emas (o'tkinchi
    xaridor).
    """
    if body.paid_uzs == 0 and body.client_id is None:
        raise HTTPException(status_code=422, detail="Qarzga sotishda mijoz tanlanishi shart.")
    if body.client_id is not None:
        client = await db.get(Client, body.client_id)
        if client is None or client.is_deleted:
            raise NotFoundException("Mijoz topilmadi.")

    sale = Sale(client_id=body.client_id, note=body.note, user_id=current_user.id)
    db.add(sale)
    await db.flush()

    total = Decimal(0)
    for line in body.lines:
        item = await crud_stock_items.get_or_404(db, f"Tovar topilmadi: {line.item_id}", id=line.item_id)
        price = line.price_uzs if line.price_uzs is not None else (item.sale_uzs or Decimal(0))
        total += price * line.qty
        await _apply_move(
            db,
            item=item,
            qty=-line.qty,
            kind=StockMoveKind.SOTUV,
            user_id=current_user.id,
            sale_id=sale.id,
            price_uzs=price,
        )

    if body.paid_uzs > total:
        raise HTTPException(status_code=422, detail=f"To'lov jamidan katta: {body.paid_uzs} > {total}.")
    sale.total_uzs = total
    sale.paid_uzs = body.paid_uzs
    sale.status = _sale_status(total, body.paid_uzs)
    if body.paid_uzs > 0:
        db.add(Payment(sale_id=sale.id, amount_uzs=body.paid_uzs, method=body.method, user_id=current_user.id))

    log_action(
        db,
        module="stock",
        action="sale",
        user_id=current_user.id,
        entity_type="sale",
        entity_id=sale.id,
        message=f"Sotuv #{sale.id}: {total} so'm, to'landi {body.paid_uzs}",
        meta={"lines": len(body.lines), "status": sale.status.value, "client_id": body.client_id},
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(sale)
    return await _sale_read(db, sale, full=True)


@router.get("/sales", response_model=list[SaleRead], operation_id="read_sales")
async def read_sales(
    db: SessionDep,
    _: StockUser,
    status: SaleStatus | None = None,
    client_id: int | None = None,
    debts: bool = False,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
) -> list[SaleRead]:
    """Sotuvlar. `debts=true` — faqat to'lanmaganlar, ya'ni qarzdorlar ro'yxati."""
    query = select(Sale).where(Sale.is_deleted == False)  # noqa: E712
    if debts:
        query = query.where(Sale.status != SaleStatus.PAID)
    if status is not None:
        query = query.where(Sale.status == status)
    if client_id is not None:
        query = query.where(Sale.client_id == client_id)
    sales = list((await db.execute(query.order_by(Sale.id.desc()).limit(limit))).scalars().all())
    return [await _sale_read(db, s) for s in sales]


@router.get("/sales/summary", response_model=SaleSummary, operation_id="read_sales_summary")
async def read_sales_summary(db: SessionDep, _: StockUser) -> SaleSummary:
    """Sotuv sahifasining tepasi: nechta sotuv, jami savdo, tushgan pul, qarz."""
    row = (
        await db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(Sale.total_uzs), 0),
                func.coalesce(func.sum(Sale.paid_uzs), 0),
            ).where(Sale.is_deleted == False)  # noqa: E712
        )
    ).one()
    total, paid = Decimal(row[1]), Decimal(row[2])
    return SaleSummary(sales=row[0], total_uzs=total, paid_uzs=paid, debt_uzs=total - paid)


@router.get("/sales/{sale_id}", response_model=SaleRead, operation_id="read_sale")
async def read_sale(db: SessionDep, _: StockUser, sale_id: int) -> SaleRead:
    sale = await db.get(Sale, sale_id)
    if sale is None or sale.is_deleted:
        raise NotFoundException("Sotuv topilmadi.")
    return await _sale_read(db, sale, full=True)


@router.post("/sales/{sale_id}/payments", response_model=SaleRead, operation_id="add_sale_payment")
async def add_sale_payment(
    db: SessionDep, current_user: StockUser, sale_id: int, body: PaymentCreate, request: Request
) -> SaleRead:
    """Qarzni to'lash — to'liq yoki qisman.

    To'lov AYRIM yozuv: `sale.paid_uzs` ni shunchaki yangilash "qachon va qanday
    to'ladi" degan savolni yo'qotardi.
    """
    sale = await db.get(Sale, sale_id)
    if sale is None or sale.is_deleted:
        raise NotFoundException("Sotuv topilmadi.")
    debt = sale.total_uzs - sale.paid_uzs
    if body.amount_uzs > debt:
        raise HTTPException(status_code=422, detail=f"To'lov qarzdan katta: {body.amount_uzs} > {debt}.")

    db.add(
        Payment(
            sale_id=sale.id,
            amount_uzs=body.amount_uzs,
            method=body.method,
            note=body.note,
            user_id=current_user.id,
        )
    )
    sale.paid_uzs += body.amount_uzs
    sale.status = _sale_status(sale.total_uzs, sale.paid_uzs)
    log_action(
        db,
        module="stock",
        action="payment",
        user_id=current_user.id,
        entity_type="sale",
        entity_id=sale.id,
        message=f"To'lov #{sale.id}: {body.amount_uzs} so'm ({body.method.value})",
        meta={"amount": str(body.amount_uzs), "method": body.method.value, "status": sale.status.value},
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(sale)
    return await _sale_read(db, sale, full=True)
