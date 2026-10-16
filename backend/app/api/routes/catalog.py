from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, or_, select

from app.api.deps import SessionDep, WarehouseReadUser, WarehouseUser, client_ip
from app.api.routes._shared import drop_forbidden_nulls
from app.core.config import settings
from app.crud import log_action
from app.models import CatalogItem
from app.schemas.catalog import (
    CatalogBulk,
    CatalogCreated,
    CatalogGroup,
    CatalogIds,
    CatalogImport,
    CatalogItemCreate,
    CatalogItemRead,
    CatalogItemUpdate,
    CatalogRow,
    CatalogTree,
    WarehousePricing,
)
from app.schemas.common import Paginated
from app.services.settings_service import set_setting
from app.services.stock import adjust_quantity
from app.services.warehouse import SEX_GROUPS, WAREHOUSE_PRICING, abc_classes, get_pricing, reprice

router = APIRouter(prefix="/catalog", tags=["catalog"])

#: PATCH da aniq `null` shu maydonlarga ruxsat — «chegara yo'q», «joyi yo'q»,
#: «narxi noma'lum», «sinfsiz», «ustama guruhnikidek» real holatlar. `quantity` va `status` NOT NULL.
_NULLABLE_FIELDS = (
    "min_quantity",
    "location",
    "purchase_price",
    "sale_price",
    "note",
    "description",
    "purchase_usd",
    "tier",
    "markup_pct",
)


async def _all_items(db: SessionDep) -> list[CatalogItem]:
    return list(
        (
            await db.execute(
                select(CatalogItem)
                .where(CatalogItem.is_deleted == False)  # noqa: E712
                .order_by(CatalogItem.catalog, CatalogItem.group_code, CatalogItem.model_no, CatalogItem.variant_no)
            )
        ).scalars()
    )


@router.get("/all", response_model=list[CatalogRow], operation_id="read_catalog_all")
async def read_catalog_all(db: SessionDep, _: WarehouseReadUser) -> list[CatalogRow]:
    """Butun nomenklatura bitta so'rovda (≈2 700 qator) + ABC sinfi. Qidiruv va filtr brauzerda —
    dizayndagidek darhol; ABC esa butun ro'yxat bo'yicha hisoblanadi, sahifa bo'yicha emas."""
    items = await _all_items(db)
    abc = abc_classes(items)
    return [
        CatalogRow.model_validate(i).model_copy(update={"abc": None if i.catalog == "X" else abc.get(i.id, "C")})
        for i in items
    ]


@router.get("/pricing", response_model=WarehousePricing, operation_id="read_warehouse_pricing")
async def read_warehouse_pricing(db: SessionDep, _: WarehouseReadUser) -> WarehousePricing:
    return await get_pricing(db)


@router.put("/pricing", response_model=WarehousePricing, operation_id="update_warehouse_pricing")
async def update_warehouse_pricing(
    db: SessionDep, current_user: WarehouseUser, body: WarehousePricing, request: Request
) -> WarehousePricing:
    """Kurs, sinf narxlari va ustama birga saqlanadi va HAMMA pozitsiyaning narxi qayta hisoblanadi
    (`services/warehouse.reprice`) — dizayndagidek, sahifadagi har o'zgarish darhol narxga tushadi."""
    old = await get_pricing(db)
    row = await set_setting(db, WAREHOUSE_PRICING, body.model_dump_json(), current_user.id)
    await db.flush()
    n = 0
    for item in await _all_items(db):
        before = (item.purchase_price, item.sale_price)
        reprice(item, body)
        n += before != (item.purchase_price, item.sale_price)
    log_action(
        db,
        module="catalog",
        action="pricing",
        user_id=current_user.id,
        entity_type="system_setting",
        entity_id=row.id,
        message=f"Ombor narx sozlamasi o'zgardi, {n} ta pozitsiya narxi yangilandi",
        meta={"old": old.model_dump(mode="json"), "new": body.model_dump(mode="json")},
        ip=client_ip(request),
    )
    await db.commit()
    return body


async def _next_code(db: SessionDep, catalog: str, group_code: str, model: str | None) -> tuple[str, int, int]:
    """Keyingi bo'sh kod. O'chirilganlar ham hisobga olinadi — kod qayta berilmaydi (docs/14 §1)."""
    if model:
        model_no = int(model.split("-")[2])
        variant = await db.scalar(
            select(func.max(CatalogItem.variant_no)).where(
                CatalogItem.catalog == catalog, CatalogItem.group_code == group_code, CatalogItem.model_no == model_no
            )
        )
        if variant is None:
            raise HTTPException(status_code=404, detail=f"{model} modeli topilmadi.")
        variant_no = variant + 1
    else:
        model_no = (
            await db.scalar(
                select(func.max(CatalogItem.model_no)).where(
                    CatalogItem.catalog == catalog, CatalogItem.group_code == group_code
                )
            )
            or 0
        ) + 1
        variant_no = 1
    if model_no > 999 or variant_no > 99:
        raise HTTPException(status_code=409, detail="Bu guruhda bo'sh kod qolmadi.")
    return f"{catalog}-{group_code}-{model_no:03d}-{variant_no:02d}", model_no, variant_no


async def _create(db: SessionDep, body: CatalogItemCreate, cfg: WarehousePricing) -> CatalogItem:
    group_name = await db.scalar(
        select(func.min(CatalogItem.group_name)).where(
            CatalogItem.catalog == body.catalog, CatalogItem.group_code == body.group_code
        )
    )
    # Sex xo'jaligi guruhlari varaqda yo'q — nomi kodda (birinchi pozitsiya shu bilan ochiladi)
    group_name = group_name or SEX_GROUPS.get(f"{body.catalog}-{body.group_code}")
    if group_name is None:
        raise HTTPException(status_code=404, detail=f"{body.catalog}-{body.group_code} guruhi topilmadi.")
    code, model_no, variant_no = await _next_code(db, body.catalog, body.group_code, body.model)
    xizmat = body.catalog == "X"
    item = CatalogItem(
        code=code,
        catalog=body.catalog,
        group_code=body.group_code,
        group_name=group_name,
        model_no=model_no,
        variant_no=variant_no,
        name=body.name.strip(),
        description=(body.description or "").strip() or None,
        unit=body.unit,
        # Xizmat omborda saqlanmaydi — qoldiq va chegara yo'q
        quantity=body.quantity if not xizmat else 0,  # type: ignore[arg-type]
        min_quantity=None if xizmat else body.min_quantity,
        location=(body.location or "").strip() or None,
        purchase_price=body.purchase_price,
        sale_price=body.sale_price,
    )
    if body.sale_price is None:
        reprice(item, cfg)  # furnitura: sotuv ustamadan
    db.add(item)
    await db.flush()
    return item


@router.post("/items", response_model=CatalogItemRead, operation_id="create_catalog_item")
async def create_catalog_item(
    db: SessionDep, current_user: WarehouseUser, body: CatalogItemCreate, request: Request
) -> CatalogItemRead:
    item = await _create(db, body, await get_pricing(db))
    log_action(
        db,
        module="catalog",
        action="create",
        user_id=current_user.id,
        entity_type="catalog_item",
        entity_id=item.id,
        message=f"{item.code} · {item.name}",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(item)
    return CatalogItemRead.model_validate(item)


@router.post("/import", response_model=CatalogCreated, operation_id="import_catalog_items")
async def import_catalog_items(
    db: SessionDep, current_user: WarehouseUser, body: CatalogImport, request: Request
) -> CatalogCreated:
    """Shablon bo'yicha yangi pozitsiyalar — hammasi yoki hech biri (bitta tranzaksiya)."""
    cfg = await get_pricing(db)
    codes = [(await _create(db, row, cfg)).code for row in body.rows]
    log_action(
        db,
        module="catalog",
        action="import",
        user_id=current_user.id,
        entity_type="catalog_item",
        message=f"{len(codes)} ta yangi pozitsiya yuklandi",
        meta={"codes": codes[:200]},
        ip=client_ip(request),
    )
    await db.commit()
    return CatalogCreated(codes=codes)


@router.post("/items/delete", response_model=CatalogCreated, operation_id="delete_catalog_items")
async def delete_catalog_items(
    db: SessionDep, current_user: WarehouseUser, body: CatalogIds, request: Request
) -> CatalogCreated:
    """Yumshoq o'chirish: pozitsiya ro'yxatdan chiqadi, KODI esa band qoladi va qayta berilmaydi."""
    items = list(
        (
            await db.execute(
                select(CatalogItem).where(CatalogItem.id.in_(body.ids), CatalogItem.is_deleted == False)  # noqa: E712
            )
        ).scalars()
    )
    now = datetime.now(UTC)
    for item in items:
        item.is_deleted, item.deleted_at = True, now
    log_action(
        db,
        module="catalog",
        action="delete",
        user_id=current_user.id,
        entity_type="catalog_item",
        message=f"{len(items)} ta pozitsiya o'chirildi",
        meta={"codes": [i.code for i in items][:200], "qoldiqli": [i.code for i in items if i.quantity > 0][:200]},
        ip=client_ip(request),
    )
    await db.commit()
    return CatalogCreated(codes=[i.code for i in items])


@router.post("/items/bulk", response_model=CatalogCreated, operation_id="bulk_update_catalog_items")
async def bulk_update_catalog_items(
    db: SessionDep, current_user: WarehouseUser, body: CatalogBulk, request: Request
) -> CatalogCreated:
    """Belgilanganlarga birdan: dekor sinfi (faqat LDSP/LMDF) yoki «zaxiraga olish» (material)."""
    cfg = await get_pricing(db)
    items = list(
        (
            await db.execute(
                select(CatalogItem).where(CatalogItem.id.in_(body.ids), CatalogItem.is_deleted == False)  # noqa: E712
            )
        ).scalars()
    )
    touched = []
    for item in items:
        if body.tier is not None and item.catalog == "M" and item.group_code in ("LD", "LM"):
            item.tier = body.tier or None
            reprice(item, cfg)
            touched.append(item.code)
        if body.tracked is not None and item.catalog == "M":
            item.tracked = body.tracked
            touched.append(item.code)
    log_action(
        db,
        module="catalog",
        action="bulk",
        user_id=current_user.id,
        entity_type="catalog_item",
        message=f"{len(set(touched))} ta pozitsiya: "
        + ("sinf " + (body.tier or "olib tashlandi") if body.tier is not None else "")
        + (("zaxiraga olindi" if body.tracked else "zaxiradan chiqarildi") if body.tracked is not None else ""),
        ip=client_ip(request),
    )
    await db.commit()
    return CatalogCreated(codes=sorted(set(touched)))


@router.get("/groups", response_model=CatalogTree, operation_id="read_catalog_groups")
async def read_catalog_groups(db: SessionDep, _: WarehouseReadUser) -> CatalogTree:
    """Kategoriya daraxti: katalog (M/F/X) → guruh, har birida nechta pozitsiya.

    Guruh nomi pozitsiyaning o'zida yotadi (alohida `catalog_group` jadvali YO'Q):
    guruh 33 ta va nomi kod bilan birga varaqdan keladi. Alohida jadval bo'lsa
    import har safar ikkita jadvalni sinxronlashi kerak bo'lardi, foydasi esa —
    faqat nomning takrorlanmasligi."""
    rows = (
        (
            await db.execute(
                select(
                    CatalogItem.catalog,
                    CatalogItem.group_code,
                    func.min(CatalogItem.group_name),
                    func.count(CatalogItem.id),
                )
                .where(CatalogItem.is_deleted == False)  # noqa: E712
                .group_by(CatalogItem.catalog, CatalogItem.group_code)
                .order_by(CatalogItem.catalog, CatalogItem.group_code)
            )
        )
        .tuples()
        .all()
    )
    groups = [CatalogGroup(catalog=c, group_code=g, group_name=n or g, count=k) for c, g, n, k in rows]
    totals: dict[str, int] = {}
    for gr in groups:
        totals[gr.catalog] = totals.get(gr.catalog, 0) + gr.count
    return CatalogTree(groups=groups, totals=totals)


@router.get("/items", response_model=Paginated[CatalogItemRead], operation_id="read_catalog_items")
async def read_catalog_items(
    db: SessionDep,
    _: WarehouseReadUser,
    catalog: Annotated[str | None, Query(pattern=r"^[MFXS]$")] = None,
    group_code: Annotated[str | None, Query(pattern=r"^[A-Z]{2}$")] = None,
    status: Annotated[Literal["Aktiv", "Arxiv"] | None, Query()] = None,
    low_stock: Annotated[bool, Query()] = False,
    search: str | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
) -> Paginated[CatalogItemRead]:
    """Katalog ro'yxati — kategoriya, holat va qidiruv bo'yicha.

    Qidiruv KOD, nom, artikul va dekor nomi bo'ylab: omborchi qo'lidagi qog'ozda
    ularning qaysi biri bo'lishi oldindan ma'lum emas."""
    query = select(CatalogItem).where(CatalogItem.is_deleted == False)  # noqa: E712
    if catalog:
        query = query.where(CatalogItem.catalog == catalog)
    if group_code:
        query = query.where(CatalogItem.group_code == group_code)
    if status:
        query = query.where(CatalogItem.status == status)
    if low_stock:
        # Chegara belgilangan va qoldiq shundan past — buyurtma qilish kerak
        query = query.where(CatalogItem.min_quantity.is_not(None), CatalogItem.quantity < CatalogItem.min_quantity)
    if search:
        naqsh = f"%{search.strip()}%"
        query = query.where(
            or_(
                CatalogItem.code.ilike(naqsh),
                CatalogItem.name.ilike(naqsh),
                CatalogItem.article.ilike(naqsh),
                CatalogItem.decor_name.ilike(naqsh),
            )
        )
    count = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = (
        (
            await db.execute(
                query.order_by(
                    CatalogItem.catalog,
                    CatalogItem.group_code,
                    CatalogItem.model_no,
                    CatalogItem.variant_no,
                )
                .offset(skip)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return Paginated(data=[CatalogItemRead.model_validate(i) for i in items], count=count)


@router.patch("/items/{item_id}", response_model=CatalogItemRead, operation_id="update_catalog_item")
async def update_catalog_item(
    db: SessionDep,
    current_user: WarehouseUser,
    request: Request,
    item_id: int,
    body: CatalogItemUpdate,
) -> CatalogItemRead:
    """Qoldiq, chegara, joylashuv, nom, tavsif, narx, sinf, ustama, zaxira va holatni yangilaydi.

    Kod va guruh o'zgarmaydi. Narxga ta'sir qiluvchi maydon o'zgarsa narx qoidalar bo'yicha qayta
    hisoblanadi (`services/warehouse.reprice`): furniturada ustama, dekorda sinf narxi ustun."""
    item = await db.get(CatalogItem, item_id)
    if item is None or item.is_deleted:
        raise HTTPException(status_code=404, detail="Pozitsiya topilmadi.")
    data = drop_forbidden_nulls(body.model_dump(exclude_unset=True), _NULLABLE_FIELDS)
    if "quantity" in data:
        # Qoldiq faqat harakat bilan o'zgaradi: qo'lda tuzatish ham partiya/FIFO va izi bilan (docs/14 §9)
        await adjust_quantity(db, item, data.pop("quantity"), current_user.id)
    for field, value in data.items():
        setattr(item, field, value)
    if "purchase_price" in data and "purchase_usd" not in data:
        item.purchase_usd = None  # so'mda qo'lda kiritildi — dollar narxi endi amal qilmaydi
    if data.keys() & {"purchase_price", "purchase_usd", "tier", "markup_pct"}:
        reprice(item, await get_pricing(db))
    log_action(
        db,
        module="catalog",
        action="update",
        user_id=current_user.id,
        entity_type="catalog_item",
        entity_id=item.id,
        message=item.code,
        meta={k: str(v) for k, v in data.items()},
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(item)
    return CatalogItemRead.model_validate(item)
