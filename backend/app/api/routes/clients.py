from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import defer

from app.api.deps import ManagerUser, SessionDep, StaffReadUser, client_ip
from app.core.config import settings
from app.core.exceptions import DuplicateValueException
from app.crud import crud_clients, log_action
from app.models import ORDER_FAT_COLUMNS, Client, Order
from app.models.enums import OrderStatus
from app.schemas.clients import ClientCreate, ClientDetail, ClientOrderRow, ClientRead, ClientUpdate
from app.schemas.common import Message, Paginated

router = APIRouter(prefix="/clients", tags=["clients"])


#: "Daromad" ta'rifi: yumshoq o'chirilmagan, BEKOR QILINMAGAN va narxi kiritilgan
#: buyurtma. Bitta joyda, chunki uni ikkitasi ishlatadi — ro'yxat SARALASHI va
#: `_reyting`; ikki nusxa bo'lsa ro'yxat bir tartibda chiqib, segment boshqasini
#: ko'rsatardi.
_DAROMAD = (
    Order.is_deleted == False,  # noqa: E712
    Order.status != OrderStatus.CANCELLED,
    Order.amount.is_not(None),
)


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
    summa = (
        select(Order.client_id, func.sum(Order.amount).label("summa"))
        .where(*_DAROMAD)
        .group_by(Order.client_id)
        .subquery()
    )
    query = (
        select(Client, func.coalesce(counts.c.orders_count, 0))
        .outerjoin(counts, counts.c.client_id == Client.id)
        .outerjoin(summa, summa.c.client_id == Client.id)
        .where(Client.is_deleted == False)  # noqa: E712
    )
    if search:
        pattern = f"%{search.strip()}%"
        # `phone_alt` ham qidiriladi: unikallik (`_ensure_phone_free`) ikkala
        # ustunni qamraydi, ya'ni ikkinchi raqam bo'yicha mijoz TOPILISHI kerak.
        query = query.where(
            or_(Client.full_name.ilike(pattern), Client.phone.ilike(pattern), Client.phone_alt.ilike(pattern))
        )

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    # QIYMAT bo'yicha, "eng yangi" bo'yicha emas: ro'yxatning o'zi reyting bo'lib
    # o'qilishi kerak, aks holda ABC ustuni tasodifiy tartibda sochilib ketardi.
    # Yangi qo'shilgan mijozni qidiruv topadi.
    rows = (
        await db.execute(
            query.order_by(func.coalesce(summa.c.summa, 0).desc(), Client.id.desc()).offset(skip).limit(limit)
        )
    ).all()

    reyting = await _reyting(db)
    data = []
    for client, orders_count in rows:
        item = ClientRead.model_validate(client)
        item.orders_count = orders_count
        o = reyting.get(client.id)
        if o is not None:
            item.total_amount, item.rank, item.share_pct, item.segment = o
        data.append(item)
    return Paginated(data=data, count=total)


async def _reyting(db: SessionDep) -> dict[int, tuple[Decimal, int, float, str]]:
    """Mijoz -> (summa, o'rin, ulush %, ABC segmenti).

    HAMMA mijoz bo'yicha hisoblanadi, sahifa bo'yicha emas: o'rin va segment
    populyatsiya xossasi, ya'ni ikkinchi sahifada "1-o'rin" chiqib qolmasligi
    kerak.

    Bekor qilingan buyurtma sanalmaydi — u daromad emas.

    ABC (Pareto): mijozlar summa bo'yicha kamayish tartibida yig'iladi; A —
    aylanmaning birinchi 80% i, B — 95% gacha, C — qolgani. Chegarani KESIB
    o'tgan mijoz yuqori sinfda qoladi (standart qoida): aks holda prodda eng
    yirik mijoz (81%) yolg'iz o'zi chegaradan oshib, A sinfi bo'sh qolardi.

    ponytail: yig'ish Python'da — 21 mijozda ham, 10 mingda ham bitta agregat
    so'rov; yuz mingdan oshsa oyna funksiyalariga (`SUM() OVER`) ko'chirish kerak.
    """
    rows = (
        await db.execute(select(Order.client_id, func.sum(Order.amount)).where(*_DAROMAD).group_by(Order.client_id))
    ).all()
    jami = sum((v for _, v in rows), Decimal(0))
    if not jami:
        return {}
    out: dict[int, tuple[Decimal, int, float, str]] = {}
    kum = Decimal(0)
    for i, (cid, summa) in enumerate(sorted(rows, key=lambda r: r[1], reverse=True), start=1):
        oldingi = kum  # shu mijozdan OLDINGI yig'indi — chegara qoidasi shunga qarab
        kum += summa
        seg = "A" if oldingi < Decimal("0.80") * jami else ("B" if oldingi < Decimal("0.95") * jami else "C")
        out[cid] = (summa, i, float(summa / jami * 100), seg)
    return out


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


@router.get("/{client_id}/detail", response_model=ClientDetail, operation_id="read_client_detail")
async def read_client_detail(db: SessionDep, _: StaffReadUser, client_id: int) -> ClientDetail:
    """Ro'yxatdagi qator ustiga bosilganda: mijoz + uning buyurtmalari.

    Reestrga o'tmasdan javob berilishi kerak bo'lgan savol shu: bu mijoz nima
    buyurtma qilgan, qaysi holatda va qanchaga.
    """
    client = await crud_clients.get_or_404(db, "Mijoz topilmadi.", id=client_id)
    detail = ClientDetail.model_validate(client)
    orders = (
        (
            await db.execute(
                select(Order)
                .options(*(defer(c) for c in ORDER_FAT_COLUMNS))
                .where(
                    Order.client_id == client_id,
                    Order.is_deleted == False,  # noqa: E712
                )
                .order_by(Order.id.desc())
            )
        )
        .scalars()
        .all()
    )
    detail.orders = [ClientOrderRow.model_validate(o) for o in orders]
    detail.orders_count = len(orders)
    o = (await _reyting(db)).get(client_id)
    if o is not None:
        detail.total_amount, detail.rank, detail.share_pct, detail.segment = o
    return detail


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
    # Buyurtmasi bor mijozni o'chirib bo'lmaydi. `client_id` majburiy FK, ya'ni
    # yumshoq o'chirilgan mijozning buyurtmalari reestrda egasiz qatorga
    # aylanardi: "Mijoz" ustuni bo'sh, kimga topshirish noma'lum. Ish markazi
    # o'chirishida ham shu qoida (`machines._blockers`).
    soni = (
        await db.execute(
            select(func.count(Order.id)).where(
                Order.client_id == client_id,
                Order.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one()
    if soni:
        raise HTTPException(
            status_code=409,
            detail=(
                f"«{client.full_name}» o'chirilmadi: unga biriktirilgan {soni} ta buyurtma bor. "
                "Avval o'sha buyurtmalarni boshqa mijozga o'tkazing yoki bekor qiling."
            ),
        )
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
