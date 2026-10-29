"""Sex ↔ ombor: terminaldan material so'rash, sexdagi rulonni tugatish, omborchining so'rovlar ro'yxati
(EKO TZ §4.4, 2.3b). Terminal foydalanuvchisi (arrachi, kromkachi, umumiy terminal) ham kiradi."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from app.api.deps import SessionDep, WarehouseReadUser, WarehouseUser, client_ip, require_roles
from app.core.exceptions import NotFoundException
from app.crud import log_action
from app.models import Order, User
from app.models.enums import POST_ROLES, UserRole
from app.modules.ombor.models import MaterialSorov
from app.modules.ombor.models.sorov import YANGI
from app.modules.ombor.routes.berish import _birlik, _order, _varaqa
from app.modules.ombor.schemas.berish import BirlikRead, SexMaterial, SorovIn, SorovRead
from app.modules.ombor.services import berish, birlik, sorov
from app.modules.ombor.services.stock import fmt
from app.services.scanning import ScanRejected, resolve_terminal

router = APIRouter(prefix="/ombor", tags=["ombor"])

#: Sex hodimi: terminal, post operatorlari, shuningdek omborchi va menejer (nazorat uchun)
SexUser = Annotated[
    User,
    Depends(require_roles(UserRole.TERMINAL, *POST_ROLES, UserRole.SKLADCHI, UserRole.MANAGER)),
]


def _sorov_read(s: MaterialSorov, order_number: str | None, by: str | None) -> SorovRead:
    return SorovRead(
        id=s.id,
        order_id=s.order_id,
        order_number=order_number,
        post=s.post,
        izoh=s.izoh,
        holat=s.holat,
        created_at=s.created_at,
        created_by=by,
    )


async def _by(db: SessionDep, user_id: int | None) -> str | None:
    if user_id is None:
        return None
    u = await db.get(User, user_id)
    return (u.name or u.username) if u else None


@router.get("/sex/{order_id}", response_model=SexMaterial, operation_id="read_sex_material")
async def read_sex_material(db: SessionDep, _: SexUser, order_id: int, post: str) -> SexMaterial:
    """Shu postga kerakli material: nima, qancha berilgan, sexda qaysi rulonlar bor; ochiq so'rov."""
    order = await _order(db, order_id)
    v = await _varaqa(db, order)
    kinds = sorov.POST_KINDS.get(post, ())
    s = await sorov.ochiq(db, order.id, post)
    return SexMaterial(
        order_id=order.id,
        order_number=order.number,
        holat=v.holat,
        tosiq=v.tosiq,
        lines=[ln for ln in v.lines if ln.kind in kinds],
        sorov=_sorov_read(s, order.number, await _by(db, s.created_by_id)) if s else None,
    )


@router.post("/sex/{order_id}/sorov", response_model=SorovRead, operation_id="create_material_sorov")
async def create_material_sorov(
    db: SessionDep, current_user: SexUser, order_id: int, body: SorovIn, request: Request
) -> SorovRead:
    """«Material so'rash»: omborchiga so'rov. Ochig'i bo'lsa — o'sha qaytadi (takror bosish xavfsiz)."""
    order = await _order(db, order_id)
    try:
        machine, _post = await resolve_terminal(db, current_user)
        machine_id: int | None = machine.id
    except ScanRejected:
        machine_id = None  # omborchi/menejer — ish markazisiz
    s = await sorov.sora(db, order.id, body.post, machine_id, body.izoh.strip(), current_user.id)
    log_action(
        db,
        module="ombor",
        action="sorov",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"{body.post}: material so'raldi {body.izoh}".strip()[:500],
        ip=client_ip(request),
    )
    await db.commit()
    return _sorov_read(s, order.number, await _by(db, s.created_by_id))


@router.post("/sex/rulon/{barkod}/tugadi", response_model=BirlikRead, operation_id="sex_rulon_tugadi")
async def sex_rulon_tugadi(db: SessionDep, current_user: SexUser, barkod: str, request: Request) -> BirlikRead:
    """Kromkachi: rulon stanokda amalda tugadi — hisobdagi qoldig'i hisobdan chiqadi."""
    try:
        q = await berish.rulon_tugadi(db, barkod, current_user.id)
    except berish.BerishError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    u = await birlik.find(db, barkod)
    assert u is not None
    log_action(
        db,
        module="ombor",
        action="rulon_tugadi",
        user_id=current_user.id,
        entity_type="material_birlik",
        entity_id=u.id,
        message=f"{u.barkod}: sexda rulon tugadi, {fmt(q)} hisobdan chiqdi",
        ip=client_ip(request),
    )
    await db.commit()
    return _birlik(u, None)


@router.get("/sorovlar", response_model=list[SorovRead], operation_id="list_material_sorovlar")
async def list_material_sorovlar(db: SessionDep, _: WarehouseReadUser) -> list[SorovRead]:
    """Ochiq so'rovlar — eng eskisi birinchi."""
    rows = (
        await db.execute(
            select(MaterialSorov, Order.number, User.name, User.username)
            .join(Order, Order.id == MaterialSorov.order_id)
            .outerjoin(User, User.id == MaterialSorov.created_by_id)
            .where(MaterialSorov.holat == YANGI, MaterialSorov.is_deleted == False)  # noqa: E712
            .order_by(MaterialSorov.created_at)
        )
    ).all()
    return [_sorov_read(s, num, fn or un) for s, num, fn, un in rows]


@router.post("/sorov/{sorov_id}/yopish", response_model=SorovRead, operation_id="close_material_sorov")
async def close_material_sorov(
    db: SessionDep, current_user: WarehouseUser, sorov_id: int, request: Request
) -> SorovRead:
    """Omborchi so'rovni qo'lda yopadi (masalan, material oldindan yetkazilgan yoki boshqa yo'l bilan)."""
    s = await db.get(MaterialSorov, sorov_id)
    if s is None or s.is_deleted:
        raise NotFoundException("So'rov topilmadi.")
    sorov.yop(s, current_user.id)
    log_action(
        db,
        module="ombor",
        action="sorov_yopildi",
        user_id=current_user.id,
        entity_type="order",
        entity_id=s.order_id,
        message=f"{s.post}: so'rov yopildi",
        ip=client_ip(request),
    )
    await db.commit()
    order = await db.get(Order, s.order_id)
    return _sorov_read(s, order.number if order else None, await _by(db, s.created_by_id))
