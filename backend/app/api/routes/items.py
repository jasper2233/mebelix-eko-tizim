from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.core.exceptions import ForbiddenException, NotFoundException
from app.crud.items import crud_items
from app.models.item import Item
from app.schemas.common import Message
from app.schemas.items import ItemCreate, ItemPublic, ItemsPublic, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])


async def _get_item_for_user(item_id: int, session: SessionDep, current_user: CurrentUser) -> Item:
    """Fetch an item by ID and verify the caller owns it (or is a superuser). Raises 404/403 otherwise."""
    item = await crud_items.get(db=session, id=item_id)
    if item is None:
        raise NotFoundException("Element topilmadi")
    if not current_user.is_superuser and item.owner_id != current_user.id:
        raise ForbiddenException("Yetarli huquq yo'q")
    return item


@router.get("/", response_model=ItemsPublic, operation_id="read_items")
async def read_items(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE),
) -> ItemsPublic:
    """List items. Superusers see all; everyone else sees only their own."""
    filters: dict = {} if current_user.is_superuser else {"owner_id": current_user.id}
    rows, total = await crud_items.get_multi(db=session, offset=skip, limit=limit, **filters)
    return ItemsPublic(
        data=[ItemPublic.model_validate(item) for item in rows],
        count=total,
    )


@router.get("/{id}", response_model=ItemPublic, operation_id="read_item")
async def read_item(id: int, session: SessionDep, current_user: CurrentUser) -> Item:
    return await _get_item_for_user(id, session, current_user)


@router.post("/", response_model=ItemPublic, status_code=status.HTTP_201_CREATED, operation_id="create_item")
async def create_item(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    item_in: ItemCreate,
) -> Item:
    return await crud_items.create(db=session, item_create=item_in, owner_id=current_user.id)


@router.put("/{id}", response_model=ItemPublic, operation_id="update_item")
async def update_item(
    id: int,
    item_in: ItemUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> Item:
    item = await _get_item_for_user(id, session, current_user)
    return await crud_items.update(db=session, db_item=item, item_update=item_in)


@router.delete("/{id}", response_model=Message, operation_id="delete_item")
async def delete_item(id: int, session: SessionDep, current_user: CurrentUser) -> Message:
    await _get_item_for_user(id, session, current_user)
    await crud_items.delete(db=session, id=id)
    return Message(message="Element muvaffaqiyatli o'chirildi")
