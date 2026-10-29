"""Materialni sexga berish va barkodli birliklar — `/ombor/berish/...`, `/ombor/birlik/...` (TZ §4.4)."""

from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from app.api.deps import SessionDep, WarehouseReadUser, WarehouseUser, client_ip
from app.core.exceptions import NotFoundException
from app.crud import log_action
from app.models import Order
from app.modules.ombor.models import CatalogItem, MaterialBirlik, Rezerv, RezervLine
from app.modules.ombor.models.birlik import OMBOR, SEX
from app.modules.ombor.schemas.berish import BerishLine, BerishRead, BirlikRead, SkanIn, SkanNatija, YorliqIn
from app.modules.ombor.services import berish, birlik, rezerv
from app.modules.ombor.services.stock import fmt

router = APIRouter(prefix="/ombor", tags=["ombor"])


def _bad(detail: str) -> HTTPException:
    return HTTPException(status_code=400, detail=detail)


async def _order(db: SessionDep, order_id: int) -> Order:
    order = await db.get(Order, order_id)
    if order is None or order.is_deleted:
        raise NotFoundException("Buyurtma topilmadi.")
    return order


def _birlik(u: MaterialBirlik, item: CatalogItem | None) -> BirlikRead:
    return BirlikRead.model_validate(u).model_copy(
        update={
            "item_name": item.name if item else None,
            "item_code": item.code if item else None,
            "unit": item.unit if item else None,
        }
    )


async def _varaqa(db: SessionDep, order: Order) -> BerishRead:
    rez = (
        await db.execute(
            select(Rezerv)
            .where(Rezerv.order_id == order.id, Rezerv.is_deleted == False, Rezerv.holat != rezerv.BEKOR)  # noqa: E712
            .order_by(Rezerv.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if rez is None:
        return BerishRead(
            order_id=order.id,
            order_number=order.number,
            holat=None,
            tosiq=await rezerv.production_block_reason(db, order),
            lines=[],
        )
    rows = (
        await db.execute(
            select(RezervLine, CatalogItem)
            .outerjoin(CatalogItem, CatalogItem.id == RezervLine.item_id)
            .where(RezervLine.rezerv_id == rez.id, RezervLine.is_deleted == False)  # noqa: E712
            .order_by(RezervLine.kind, RezervLine.tashqi_nom)
        )
    ).all()
    ids = [it.id for _, it in rows if it is not None]
    sexda: dict[int, list[MaterialBirlik]] = {}
    omborda: dict[int, int] = {}
    if ids:
        for u in (
            await db.execute(
                select(MaterialBirlik)
                .where(
                    MaterialBirlik.item_id.in_(ids),
                    MaterialBirlik.joy == SEX,
                    MaterialBirlik.qoldiq > 0,
                    MaterialBirlik.is_deleted == False,  # noqa: E712
                )
                .order_by(MaterialBirlik.qoldiq)  # eng kichik qoldiq birinchi — avval o'sha tugatilsin
            )
        ).scalars():
            sexda.setdefault(u.item_id, []).append(u)
        omborda = dict(
            (
                await db.execute(
                    select(MaterialBirlik.item_id, func.count())
                    .where(
                        MaterialBirlik.item_id.in_(ids),
                        MaterialBirlik.joy == OMBOR,
                        MaterialBirlik.qoldiq > 0,
                        MaterialBirlik.is_deleted == False,  # noqa: E712
                    )
                    .group_by(MaterialBirlik.item_id)
                )
            ).all()  # type: ignore[arg-type]
        )
    lines = []
    for ln, it in rows:
        lines.append(
            BerishLine(
                line_id=ln.id,
                item_id=ln.item_id,
                nom=it.name if it else ln.tashqi_nom,
                code=it.code if it else None,
                unit=it.unit if it else ln.fayl_birlik,
                birlikli=bool(it and birlik.tracked(it)),
                rulon=bool(it and birlik.tracked(it) and birlik.is_roll(it)),
                kerak=ln.kerak_qty if it else ln.fayl_qty,
                berilgan=ln.berilgan_qty,
                qoldi=max(ln.kerak_qty - ln.berilgan_qty, Decimal(0)) if it else ln.fayl_qty,
                sexda=[_birlik(u, it) for u in sexda.get(it.id, [])] if it else [],
                omborda=omborda.get(it.id, 0) if it else 0,
                yorliqsiz=await birlik.unlabeled(db, it) if it and birlik.tracked(it) else Decimal(0),
            )
        )
    return BerishRead(
        order_id=order.id,
        order_number=order.number,
        holat=rez.holat,
        tosiq=await rezerv.production_block_reason(db, order),
        lines=lines,
    )


@router.get("/berish/{order_id}", response_model=BerishRead, operation_id="read_berish_varaqa")
async def read_berish_varaqa(db: SessionDep, _: WarehouseReadUser, order_id: int) -> BerishRead:
    """Berish varaqasi: buyurtmaga nima kerak, qanchasi berilgan, sexda qaysi ochiq rulonlar bor."""
    return await _varaqa(db, await _order(db, order_id))


@router.post("/berish/{order_id}/skan", response_model=SkanNatija, operation_id="berish_skan")
async def berish_skan(
    db: SessionDep, current_user: WarehouseUser, order_id: int, body: SkanIn, request: Request
) -> SkanNatija:
    """Skanerlangan kod bo'yicha buyurtmaga material beradi: tizim barkodi (list/rulon) yoki
    furnitura uchun katalog kodi / ishlab chiqaruvchi shtrix-kodi + son."""
    order = await _order(db, order_id)
    kod = body.kod.strip()
    try:
        if await birlik.find(db, kod) is not None:
            natija = await berish.skan_birlik(db, order, kod, current_user.id)
        else:
            item = await berish.find_item(db, kod)
            if item is None:
                raise berish.BerishError(f"{kod}: na barkod, na katalog kodi topildi.")
            natija = await berish.ber_dona(db, order, item.id, body.qty or Decimal(1), current_user.id)
    except berish.BerishError as e:
        await db.rollback()
        raise _bad(str(e)) from e
    log_action(
        db,
        module="ombor",
        action="sarf",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message=natija.xabar[:500],
        ip=client_ip(request),
    )
    await db.commit()
    return SkanNatija(xabar=natija.xabar, ogohlantirish=natija.ogohlantirish, varaqa=await _varaqa(db, order))


@router.get("/birlik/{barkod}", response_model=BirlikRead, operation_id="read_birlik")
async def read_birlik(db: SessionDep, _: WarehouseReadUser, barkod: str) -> BirlikRead:
    u = await birlik.find(db, barkod)
    if u is None or u.is_deleted:
        raise NotFoundException("Bunday barkod yo'q.")
    return _birlik(u, await db.get(CatalogItem, u.item_id))


@router.get("/birliklar", response_model=list[BirlikRead], operation_id="list_birliklar")
async def list_birliklar(
    db: SessionDep, _: WarehouseReadUser, item_id: int | None = None, joy: str | None = None
) -> list[BirlikRead]:
    """Barkodli birliklar: pozitsiya bo'yicha yoki joy bo'yicha (`sex` — sexdagi rulon qoldiqlari)."""
    if item_id is None and joy is None:
        raise _bad("item_id yoki joy kerak.")
    q = select(MaterialBirlik, CatalogItem).join(CatalogItem, CatalogItem.id == MaterialBirlik.item_id)
    q = q.where(MaterialBirlik.is_deleted == False, MaterialBirlik.qoldiq > 0)  # noqa: E712
    if item_id is not None:
        q = q.where(MaterialBirlik.item_id == item_id)
    if joy is not None:
        q = q.where(MaterialBirlik.joy == joy)
    rows = (await db.execute(q.order_by(CatalogItem.name, MaterialBirlik.id).limit(2000))).all()
    return [_birlik(u, it) for u, it in rows]


@router.post("/birlik/yorliq", response_model=list[BirlikRead], operation_id="yorliq_birlik")
async def yorliq_birlik(
    db: SessionDep, current_user: WarehouseUser, body: YorliqIn, request: Request
) -> list[BirlikRead]:
    """Barkodsiz eski qoldiqni yorliqlash: `soni` ta birlik yaratadi (yorliqlarni chop etish uchun)."""
    item = await db.get(CatalogItem, body.item_id, with_for_update=True)
    if item is None or item.is_deleted:
        raise NotFoundException("Pozitsiya topilmadi.")
    if not birlik.tracked(item):
        raise _bad(f"«{item.name}» barkodli birlik bilan yuritilmaydi (furnitura kodi bo'yicha beriladi).")
    hajm = (body.hajm or item.birlik_hajm) if birlik.is_roll(item) else Decimal(1)
    if hajm is None:
        raise _bad("Bitta rulon necha metr — kiriting.")
    jami = hajm * body.soni
    bor = await birlik.unlabeled(db, item)
    if jami > bor:
        raise _bad(f"«{item.name}»: yorliqsiz qoldiq {fmt(bor)} {item.unit or ''}, {fmt(jami)} yorliqlanmoqda.")
    units = await birlik.create(db, item, [hajm] * body.soni)
    for u in units:
        u.ishlab_kod = body.ishlab_kod
    log_action(
        db,
        module="ombor",
        action="yorliq",
        user_id=current_user.id,
        entity_type="catalog_item",
        entity_id=item.id,
        message=f"{item.code}: {body.soni} ta yorliq × {fmt(hajm)} {item.unit or ''}"[:500],
        ip=client_ip(request),
    )
    await db.commit()
    return [_birlik(u, item) for u in units]


@router.post("/birlik/{barkod}/tugadi", response_model=BirlikRead, operation_id="birlik_tugadi")
async def birlik_tugadi(db: SessionDep, current_user: WarehouseUser, barkod: str, request: Request) -> BirlikRead:
    """Sexdagi rulon amalda tugadi — hisobdagi qoldig'i hisobdan chiqariladi."""
    try:
        q = await berish.rulon_tugadi(db, barkod, current_user.id)
    except berish.BerishError as e:
        await db.rollback()
        raise _bad(str(e)) from e
    u = await birlik.find(db, barkod)
    assert u is not None
    log_action(
        db,
        module="ombor",
        action="rulon_tugadi",
        user_id=current_user.id,
        entity_type="material_birlik",
        entity_id=u.id,
        message=f"{u.barkod}: rulon tugadi, {fmt(q)} hisobdan chiqdi",
        ip=client_ip(request),
    )
    await db.commit()
    return _birlik(u, await db.get(CatalogItem, u.item_id))


@router.post("/birlik/{barkod}/omborga", response_model=BirlikRead, operation_id="birlik_omborga")
async def birlik_omborga(db: SessionDep, current_user: WarehouseUser, barkod: str, request: Request) -> BirlikRead:
    """Sexdagi rulonni omborga qaytaradi."""
    try:
        u = await berish.omborga_qaytar(db, barkod)
    except berish.BerishError as e:
        await db.rollback()
        raise _bad(str(e)) from e
    log_action(
        db,
        module="ombor",
        action="omborga",
        user_id=current_user.id,
        entity_type="material_birlik",
        entity_id=u.id,
        message=f"{u.barkod}: sexdan omborga qaytdi, {fmt(u.qoldiq)}",
        ip=client_ip(request),
    )
    await db.commit()
    return _birlik(u, await db.get(CatalogItem, u.item_id))
