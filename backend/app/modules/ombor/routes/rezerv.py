"""Rezerv, ta'minot ehtiyoji va material moslash — `/ombor/...` (TZ §4.3)."""

from decimal import Decimal

from fastapi import APIRouter, Request
from sqlalchemy import select

from app.api.deps import DirectorUser, ManagerOrTexnologUser, SessionDep, WarehouseReadUser, WarehouseUser, client_ip
from app.core.exceptions import NotFoundException
from app.crud import log_action
from app.models import Order
from app.modules.ombor.models import CatalogItem, Rezerv, RezervLine
from app.modules.ombor.schemas.rezerv import MaterialMapIn, RezervLineRead, RezervRead, ShortageRead
from app.modules.ombor.services import rezerv

router = APIRouter(prefix="/ombor", tags=["ombor"])


async def _order(db: SessionDep, order_id: int) -> Order:
    order = await db.get(Order, order_id)
    if order is None or order.is_deleted:
        raise NotFoundException("Buyurtma topilmadi.")
    return order


async def _read(db: SessionDep, order: Order) -> RezervRead:
    rez = (
        await db.execute(
            select(Rezerv)
            .where(Rezerv.order_id == order.id, Rezerv.is_deleted == False)  # noqa: E712
            .order_by(Rezerv.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if rez is None:
        raise NotFoundException("Bu buyurtmada rezerv yo'q.")
    rows = await db.execute(
        select(RezervLine, CatalogItem.name, CatalogItem.unit)
        .outerjoin(CatalogItem, CatalogItem.id == RezervLine.item_id)
        .where(RezervLine.rezerv_id == rez.id, RezervLine.is_deleted == False)  # noqa: E712
        .order_by(RezervLine.kind, RezervLine.tashqi_nom)
    )
    lines = [
        RezervLineRead.model_validate(line).model_copy(update={"item_name": name, "item_unit": unit})
        for line, name, unit in rows.all()
    ]
    paid, required = await rezerv.paid_and_required(db, order)
    return RezervRead(
        id=rez.id,
        order_id=order.id,
        holat=rez.holat,
        muddat=rez.muddat,
        yechilgan_at=rez.yechilgan_at,
        tasdiq_at=rez.tasdiq_at,
        tolangan=paid,
        chegara=required,
        tosiq=await rezerv.production_block_reason(db, order),
        lines=lines,
    )


@router.get("/rezerv/{order_id}", response_model=RezervRead, operation_id="read_order_rezerv")
async def read_order_rezerv(db: SessionDep, _: WarehouseReadUser, order_id: int) -> RezervRead:
    return await _read(db, await _order(db, order_id))


@router.post("/rezerv/{order_id}/qayta", response_model=RezervRead, operation_id="rebuild_order_rezerv")
async def rebuild_order_rezerv(
    db: SessionDep, current_user: ManagerOrTexnologUser, order_id: int, request: Request
) -> RezervRead:
    """Rezervni qaytadan quradi (masalan, moslash yoki to'lovdan keyin, eski buyurtmalar uchun)."""
    order = await _order(db, order_id)
    await rezerv.reserve_for_order(db, order)
    log_action(
        db,
        module="rezerv",
        action="rezerv_qayta",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message="Material rezervi qayta hisoblandi",
        ip=client_ip(request),
    )
    await db.commit()
    return await _read(db, order)


@router.post("/rezerv/{order_id}/tasdiq", response_model=RezervRead, operation_id="approve_order_rezerv")
async def approve_order_rezerv(
    db: SessionDep, current_user: DirectorUser, order_id: int, request: Request
) -> RezervRead:
    """Direktor ruxsati: to'lov chegarasi yoki kredit limiti bajarilmagan buyurtma ishlab chiqarishga o'tadi (Q22)."""
    order = await _order(db, order_id)
    if await rezerv.approve(db, order.id, current_user.id) is None:
        raise NotFoundException("Bu buyurtmada rezerv yo'q — avval rezervni hisoblang.")
    log_action(
        db,
        module="rezerv",
        action="rezerv_tasdiq",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message="Direktor to'lovsiz ishlab chiqarishga ruxsat berdi",
        ip=client_ip(request),
    )
    await db.commit()
    return await _read(db, order)


@router.get("/taminot", response_model=list[ShortageRead], operation_id="read_supply_needs")
async def read_supply_needs(db: SessionDep, _: WarehouseReadUser) -> list[ShortageRead]:
    """Ta'minot ehtiyoji: rezervlarda yetmayotgan materiallar va hali katalogga moslanmaganlari."""
    return [
        ShortageRead(
            item_id=s.item_id,
            kind=s.kind,
            tashqi_kalit=s.tashqi_kalit,
            nom=s.nom,
            birlik=s.birlik,
            kerak=s.kerak,
            qoplangan=s.qoplangan,
            yetmaydi=s.kerak - s.qoplangan,
            buyurtmalar=s.buyurtmalar,
        )
        for s in await rezerv.shortages(db)
    ]


@router.post("/moslash", response_model=list[ShortageRead], operation_id="map_project_material")
async def map_project_material(
    db: SessionDep, current_user: WarehouseUser, body: MaterialMapIn, request: Request
) -> list[ShortageRead]:
    """Loyiha fayli materialini katalog pozitsiyasiga bog'laydi (Q23); javob — yangilangan ta'minot ro'yxati."""
    item = await db.get(CatalogItem, body.item_id)
    if item is None or item.is_deleted:
        raise NotFoundException("Katalog pozitsiyasi topilmadi.")
    await rezerv.apply_mapping(db, body.kind, body.tashqi_kalit, item.id, Decimal(body.koef), current_user.id)
    log_action(
        db,
        module="rezerv",
        action="moslash",
        user_id=current_user.id,
        entity_type="catalog_item",
        entity_id=item.id,
        message=f"«{body.tashqi_kalit}» → {item.code} × {body.koef}"[:500],
        ip=client_ip(request),
    )
    await db.commit()
    return await read_supply_needs(db, current_user)
