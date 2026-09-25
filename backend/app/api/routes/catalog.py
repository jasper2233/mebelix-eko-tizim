from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, or_, select

from app.api.deps import SessionDep, WarehouseReadUser, WarehouseUser, client_ip
from app.api.routes._shared import drop_forbidden_nulls
from app.core.config import settings
from app.crud import log_action
from app.models import CatalogItem
from app.schemas.catalog import CatalogGroup, CatalogItemRead, CatalogItemUpdate, CatalogTree
from app.schemas.common import Paginated

router = APIRouter(prefix="/catalog", tags=["catalog"])

#: PATCH da aniq `null` shu maydonlarga ruxsat — «chegara yo'q», «joyi yo'q»,
#: «narxi noma'lum» real holatlar. `quantity` va `status` NOT NULL.
_NULLABLE_FIELDS = ("min_quantity", "location", "purchase_price", "sale_price", "note")


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
    catalog: Annotated[str | None, Query(pattern=r"^[MFX]$")] = None,
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
    """Qoldiq, chegara, joylashuv, narx va holatni yangilaydi.

    Katalogning O'ZI (kod, nom, o'lcham) bu yerdan o'zgarmaydi — u varaqdan
    keladi va import uni qaytadan yozadi."""
    item = await db.get(CatalogItem, item_id)
    if item is None or item.is_deleted:
        raise HTTPException(status_code=404, detail="Pozitsiya topilmadi.")
    data = drop_forbidden_nulls(body.model_dump(exclude_unset=True), _NULLABLE_FIELDS)
    for field, value in data.items():
        setattr(item, field, value)
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
