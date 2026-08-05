from typing import Annotated

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, or_, select

from app.api.deps import ManagerUser, SessionDep, StaffReadUser, client_ip
from app.core.config import settings
from app.core.exceptions import DuplicateValueException
from app.crud import crud_clients, log_action
from app.models import Client, Order
from app.schemas.clients import ClientCreate, ClientRead, ClientUpdate
from app.schemas.common import Message, Paginated

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("/", response_model=Paginated[ClientRead], operation_id="read_clients")
async def read_clients(
    db: SessionDep,
    _: StaffReadUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
    search: str | None = None,
) -> Paginated[ClientRead]:
    counts = (
        select(Order.client_id, func.count(Order.id).label("orders_count"))
        .where(Order.is_deleted == False)  # noqa: E712
        .group_by(Order.client_id)
        .subquery()
    )
    query = (
        select(Client, func.coalesce(counts.c.orders_count, 0))
        .outerjoin(counts, counts.c.client_id == Client.id)
        .where(Client.is_deleted == False)  # noqa: E712
    )
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(Client.full_name.ilike(pattern), Client.phone.ilike(pattern)))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(Client.id.desc()).offset(skip).limit(limit))).all()

    data = []
    for client, orders_count in rows:
        item = ClientRead.model_validate(client)
        item.orders_count = orders_count
        data.append(item)
    return Paginated(data=data, count=total)


async def _ensure_phone_free(db: SessionDep, phone: str | None, exclude_id: int | None = None) -> None:
    """One phone — one client (live rows). Checks both phone and phone_alt columns."""
    if not phone:
        return
    query = select(Client).where(
        or_(Client.phone == phone, Client.phone_alt == phone),
        Client.is_deleted == False,  # noqa: E712
    )
    if exclude_id is not None:
        query = query.where(Client.id != exclude_id)
    existing = (await db.execute(query.limit(1))).scalar_one_or_none()
    if existing is not None:
        raise DuplicateValueException(f"Bu raqam boshqa mijozga kiritilgan: {existing.full_name}")


@router.post("/", response_model=ClientRead, status_code=201, operation_id="create_client")
async def create_client(db: SessionDep, current_user: ManagerUser, body: ClientCreate, request: Request) -> Client:
    await _ensure_phone_free(db, body.phone)
    if body.phone_alt and body.phone_alt != body.phone:
        await _ensure_phone_free(db, body.phone_alt)
    client = Client(**body.model_dump())
    db.add(client)
    await db.flush()
    log_action(
        db,
        module="clients",
        action="created",
        user_id=current_user.id,
        entity_type="client",
        entity_id=client.id,
        message=f"Mijoz yaratildi: {client.full_name}",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientRead, operation_id="read_client")
async def read_client(db: SessionDep, _: StaffReadUser, client_id: int) -> ClientRead:
    client = await crud_clients.get_or_404(db, "Mijoz topilmadi.", id=client_id)
    orders_count = (
        await db.execute(
            select(func.count(Order.id)).where(Order.client_id == client_id, Order.is_deleted == False)  # noqa: E712
        )
    ).scalar_one()
    item = ClientRead.model_validate(client)
    item.orders_count = orders_count
    return item


@router.patch("/{client_id}", response_model=ClientRead, operation_id="update_client")
async def update_client(
    db: SessionDep, current_user: ManagerUser, client_id: int, body: ClientUpdate, request: Request
) -> Client:
    client = await crud_clients.get_or_404(db, "Mijoz topilmadi.", id=client_id)
    updates = body.model_dump(exclude_unset=True)
    for key in ("phone", "phone_alt"):
        if updates.get(key):
            await _ensure_phone_free(db, updates[key], exclude_id=client_id)
    for field, value in updates.items():
        setattr(client, field, value)
    log_action(
        db,
        module="clients",
        action="updated",
        user_id=current_user.id,
        entity_type="client",
        entity_id=client.id,
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(client)
    return client


@router.delete("/{client_id}", response_model=Message, operation_id="delete_client")
async def delete_client(db: SessionDep, current_user: ManagerUser, client_id: int, request: Request) -> Message:
    client = await crud_clients.get_or_404(db, "Mijoz topilmadi.", id=client_id)
    log_action(
        db,
        module="clients",
        action="deleted",
        user_id=current_user.id,
        entity_type="client",
        entity_id=client.id,
        message=f"Mijoz o'chirildi: {client.full_name}",
        ip=client_ip(request),
    )
    await crud_clients.delete(db, id=client_id)
    return Message(message="Mijoz o'chirildi.")
