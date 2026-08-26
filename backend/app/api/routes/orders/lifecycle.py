import contextlib
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import defer

from app.api.deps import (
    ManagerOrTexnologUser,
    ManagerUser,
    SessionDep,
    StaffReadUser,
    client_ip,
)
from app.core.config import settings, upload_root
from app.core.exceptions import DuplicateValueException, ForbiddenException, NotFoundException
from app.core.ws import ws_manager
from app.crud import crud_clients, crud_orders, log_action
from app.models import (
    ORDER_FAT_COLUMNS,
    Client,
    Machine,
    Order,
    OrderFile,
    Part,
    PartInstance,
    PartRoute,
    Post,
    Product,
)
from app.models.enums import (
    MACHINE_STATUS_LABELS,
    FileKind,
    MachineStatus,
    OrderStatus,
)
from app.models.user import User
from app.schemas.common import Message, Paginated
from app.schemas.orders import (
    MachineAssignments,
    OrderCancel,
    OrderCreate,
    OrderDetail,
    OrderFileRead,
    OrderRead,
    OrderSurvey,
    OrderUpdate,
)

from ._common import (
    _ROUTE_START_POSTS,
    _edit_block_reason,
    _get_order,
    _get_visible_order,
    _hidden_statuses,
    _require_editable,
)

# Prefiks va tag PARENT routerda (`orders/__init__.py`) — bu yerda takrorlansa
# `include_router` ularni QO'SHADI, almashtirmaydi va generatsiya qilingan
# klientda metod ikki klassga nusxalanadi.
router = APIRouter()


def _order_read(order: Order, client_name: str) -> OrderRead:
    item = OrderRead.model_validate(order)
    item.client_name = client_name
    return item


async def _order_read_with_client(db: SessionDep, order: Order) -> OrderRead:
    """Javob uchun mijoz nomini qo'shib beradi (soft-deleted mijozda bo'sh satr)."""
    client = await crud_clients.get(db, id=order.client_id)
    return _order_read(order, client.full_name if client else "")


@router.post("/", response_model=OrderRead, status_code=201, operation_id="create_order")
async def create_order(db: SessionDep, current_user: ManagerUser, body: OrderCreate, request: Request) -> OrderRead:
    client = await crud_clients.get(db, id=body.client_id)
    if client is None:
        raise NotFoundException("Mijoz topilmadi.")

    # Sequential number has a race window between two managers — the partial unique
    # index is the arbiter; retry regenerates from the committed max.
    for attempt in range(3):
        order = Order(**body.model_dump(), number=await crud_orders.next_number(db), created_by_id=current_user.id)
        db.add(order)
        try:
            await db.flush()
            break
        except IntegrityError:
            await db.rollback()
            if attempt == 2:
                raise DuplicateValueException("Buyurtma raqami band. Qayta urining.") from None

    log_action(
        db,
        module="orders",
        action="created",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"Buyurtma yaratildi: {order.number}",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(order)
    await ws_manager.publish("order.created", {"order_id": order.id, "order_number": order.number})
    return _order_read(order, client.full_name)


@router.get("/", response_model=Paginated[OrderRead], operation_id="read_orders")
async def read_orders(
    db: SessionDep,
    current_user: StaffReadUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
    status: OrderStatus | None = None,
    search: str | None = None,
) -> Paginated[OrderRead]:
    query = (
        select(Order, Client.full_name)
        .join(Client, Client.id == Order.client_id)
        # Reestrda kesish xaritasi/anketa ko'rsatilmaydi (OrderRead da ular yo'q),
        # lekin ular o'qilib, uzatilib, parse qilinib tashlanardi: 284 ms -> 5 ms
        .options(*(defer(c) for c in ORDER_FAT_COLUMNS))
        .where(Order.is_deleted == False)  # noqa: E712
    )
    hidden = _hidden_statuses(current_user)
    if hidden:
        query = query.where(Order.status.not_in(hidden))
    if status is not None:
        query = query.where(Order.status == status)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Order.number.ilike(pattern),
                Order.project_name.ilike(pattern),
                Order.project_uuid.ilike(pattern),
                Client.full_name.ilike(pattern),
            )
        )

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(Order.id.desc()).offset(skip).limit(limit))).all()
    return Paginated(data=[_order_read(order, client_name) for order, client_name in rows], count=total)


# NOTE: /{order_id} dan OLDIN turishi shart — aks holda "status-counts" order_id deb o'qiladi.
@router.get("/status-counts", response_model=dict[str, int], operation_id="read_order_status_counts")
async def read_order_status_counts(db: SessionDep, current_user: StaffReadUser) -> dict[str, int]:
    """Reestr tablari uchun har holatdagi buyurtmalar soni."""
    query = (
        select(Order.status, func.count(Order.id))
        .where(Order.is_deleted == False)  # noqa: E712
        .group_by(Order.status)
    )
    hidden = _hidden_statuses(current_user)
    if hidden:
        query = query.where(Order.status.not_in(hidden))
    rows = (await db.execute(query)).all()
    return {str(s): c for s, c in rows}


@router.get("/{order_id}", response_model=OrderDetail, operation_id="read_order")
async def read_order(db: SessionDep, current_user: StaffReadUser, order_id: int) -> OrderDetail:
    order = await _get_visible_order(db, current_user, order_id)
    client = await db.get(Client, order.client_id)  # include soft-deleted: history must render
    files = (
        (
            await db.execute(
                select(OrderFile).where(OrderFile.order_id == order_id, OrderFile.is_deleted == False)  # noqa: E712
            )
        )
        .scalars()
        .all()
    )
    parts_count = (
        await db.execute(
            select(func.count(Part.id)).where(Part.order_id == order_id, Part.is_deleted == False)  # noqa: E712
        )
    ).scalar_one()
    instances_count = (
        await db.execute(
            select(func.count(PartInstance.id)).where(
                PartInstance.order_id == order_id,
                PartInstance.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one()

    detail = OrderDetail.model_validate(order)
    detail.client_name = client.full_name if client else ""
    # Faqat bekor qilingan buyurtmada — qo'shimcha so'rov behuda ketmasin
    if order.cancelled_by_id is not None:
        canceller = await db.get(User, order.cancelled_by_id)
        detail.cancelled_by_name = (canceller.name or canceller.username) if canceller else None
    detail.files = [OrderFileRead.model_validate(f) for f in files]
    detail.parts_count = parts_count
    detail.instances_count = instances_count
    # Tahrirlash mumkinmi — frontend tugmalarni shunga qarab yoqadi va SABABINI
    # ko'rsatadi. Qoida bitta joyda (`_require_editable`) bo'lishi uchun shu
    # yerda ham aynan o'sha helper chaqiriladi.
    detail.edit_blocked_reason = await _edit_block_reason(db, order)
    detail.can_edit = detail.edit_blocked_reason is None
    return detail


@router.patch("/{order_id}", response_model=OrderRead, operation_id="update_order")
async def update_order(
    db: SessionDep, current_user: ManagerUser, order_id: int, body: OrderUpdate, request: Request
) -> OrderRead:
    order = await _get_order(db, order_id)
    if order.status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        raise ForbiddenException("Yakunlangan yoki bekor qilingan buyurtmani o'zgartirib bo'lmaydi.")
    update_data = body.model_dump(exclude_unset=True)
    if "client_id" in update_data:
        if order.status != OrderStatus.DRAFT and update_data["client_id"] != order.client_id:
            raise ForbiddenException("Mijozni faqat qoralama (DRAFT) holatida almashtirish mumkin.")
        if await crud_clients.get(db, id=update_data["client_id"]) is None:
            raise NotFoundException("Mijoz topilmadi.")
    for field, value in update_data.items():
        setattr(order, field, value)
    log_action(
        db,
        module="orders",
        action="updated",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(order)
    return await _order_read_with_client(db, order)


@router.put("/{order_id}/survey", response_model=Message, operation_id="save_order_survey")
async def save_order_survey(
    db: SessionDep, current_user: ManagerUser, order_id: int, body: OrderSurvey, request: Request
) -> Message:
    """Mijoz anketasi va o'lchov varag'ini saqlaydi (TZ 6.2, qog'oz forma o'rniga).

    Butun anketa bir butun sifatida yoziladi — menejer to'ldirib boradi, texnolog o'qiydi.
    """
    order = await _get_order(db, order_id)
    if order.status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        raise ForbiddenException("Yakunlangan yoki bekor qilingan buyurtma anketasini o'zgartirib bo'lmaydi.")
    order.survey = body.model_dump(mode="json")

    # Xona o'chirilsa uning rasmlari yetim qolmasin (diskda ham, bazada ham)
    live_rooms = {r.id for r in body.rooms}
    orphans = (
        (
            await db.execute(
                select(OrderFile).where(
                    OrderFile.order_id == order_id,
                    OrderFile.kind == FileKind.DOCUMENT,
                    OrderFile.meta.has_key("room_id"),  # noqa: W601 — JSONB operatori, dict.has_key emas
                    OrderFile.meta["room_id"].astext.not_in(live_rooms or {""}),
                    OrderFile.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    for f in orphans:
        with contextlib.suppress(OSError):
            (upload_root() / f.path).unlink()
        f.is_deleted = True
        f.deleted_at = datetime.now(UTC)

    log_action(
        db,
        module="orders",
        action="survey_saved",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"Anketa saqlandi: {len(body.rooms)} ta xona",
        ip=client_ip(request),
    )
    await db.commit()
    return Message(message="Anketa saqlandi.")


_ROOM_PHOTO_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_ROOM_PHOTO_SIZE = 5 * 1024 * 1024  # telefon surati odatda 2-4 MB
MAX_ROOM_PHOTOS = 6


@router.post(
    "/{order_id}/survey/photos", response_model=OrderFileRead, status_code=201, operation_id="upload_room_photo"
)
async def upload_room_photo(
    db: SessionDep,
    current_user: ManagerUser,
    order_id: int,
    room_id: Annotated[str, Form(max_length=40)],
    file: UploadFile,
    request: Request,
) -> OrderFileRead:
    """Xona uchun taxminiy ko'rinish rasmi (anketa, mijoz ko'rsatgan namuna).

    Rasm SurveyRoom.id ga bog'lanadi — xona ro'yxatdagi o'rni o'zgarsa ham yo'qolmaydi.
    """
    order = await _get_order(db, order_id)
    if order.status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        raise ForbiddenException("Yakunlangan yoki bekor qilingan buyurtmaga rasm qo'shib bo'lmaydi.")

    ext = _ROOM_PHOTO_TYPES.get(file.content_type or "")
    if ext is None:
        raise HTTPException(status_code=422, detail="Faqat JPG, PNG yoki WEBP rasm qabul qilinadi.")
    content = await file.read()
    if len(content) > MAX_ROOM_PHOTO_SIZE:
        raise HTTPException(status_code=422, detail=f"Rasm {MAX_ROOM_PHOTO_SIZE // 1024**2} MB dan katta bo'lmasin.")

    existing = (
        await db.execute(
            select(func.count(OrderFile.id)).where(
                OrderFile.order_id == order_id,
                OrderFile.kind == FileKind.DOCUMENT,
                OrderFile.meta["room_id"].astext == room_id,
                OrderFile.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one()
    if existing >= MAX_ROOM_PHOTOS:
        raise HTTPException(
            status_code=422, detail=f"Bitta xonaga {MAX_ROOM_PHOTOS} tadan ko'p rasm qo'shib bo'lmaydi."
        )

    rel = f"survey/{order_id}/{uuid4().hex}{ext}"
    full = upload_root() / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(content)

    row = OrderFile(
        order_id=order_id,
        kind=FileKind.DOCUMENT,
        path=rel,
        filename=(file.filename or "rasm")[:255],
        size=len(content),
        meta={"room_id": room_id, "content_type": file.content_type},
    )
    db.add(row)
    await db.flush()
    log_action(
        db,
        module="orders",
        action="survey_photo_added",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order_id,
        message=f"Anketaga rasm qo'shildi: {row.filename}",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(row)
    return OrderFileRead.model_validate(row)


@router.delete("/{order_id}/survey/photos/{file_id}", response_model=Message, operation_id="delete_room_photo")
async def delete_room_photo(
    db: SessionDep, current_user: ManagerUser, order_id: int, file_id: int, request: Request
) -> Message:
    row = (
        await db.execute(
            select(OrderFile).where(
                OrderFile.id == file_id,
                OrderFile.order_id == order_id,
                OrderFile.kind == FileKind.DOCUMENT,
                OrderFile.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundException("Rasm topilmadi.")
    # Diskdagi fayl ham o'chadi — anketa rasmlari tarix uchun saqlanmaydi
    with contextlib.suppress(OSError):
        (upload_root() / row.path).unlink()
    row.is_deleted = True
    row.deleted_at = datetime.now(UTC)
    log_action(
        db,
        module="orders",
        action="survey_photo_deleted",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order_id,
        message=f"Anketa rasmi o'chirildi: {row.filename}",
        ip=client_ip(request),
    )
    await db.commit()
    return Message(message="Rasm o'chirildi.")


@router.post("/{order_id}/cancel", response_model=OrderRead, operation_id="cancel_order")
async def cancel_order(
    db: SessionDep, current_user: ManagerUser, order_id: int, body: OrderCancel, request: Request
) -> OrderRead:
    """TZ 6.5: any stage; scans/history stay for audit; terminals are notified in real time."""
    order = await _get_order(db, order_id)
    if order.status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        raise ForbiddenException("Bu buyurtmani bekor qilib bo'lmaydi.")
    order.status = OrderStatus.CANCELLED
    order.cancelled_at = datetime.now(UTC)
    order.cancel_reason = body.reason
    order.cancelled_by_id = current_user.id
    log_action(
        db,
        module="orders",
        action="cancelled",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"Buyurtma bekor qilindi: {body.reason}",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(order)
    # Terminals drop the tasks IMMEDIATELY (TZ 6.5) — real-time, all posts.
    await ws_manager.publish("order.cancelled", {"order_id": order.id, "order_number": order.number})
    return await _order_read_with_client(db, order)


@router.post("/{order_id}/deliver", response_model=OrderRead, operation_id="deliver_order")
async def deliver_order(db: SessionDep, current_user: ManagerUser, order_id: int, request: Request) -> OrderRead:
    """TZ 10.3: TOPSHIRILDI — only from COMPLETED; date recorded automatically."""
    order = await _get_order(db, order_id)
    if order.status != OrderStatus.COMPLETED:
        raise ForbiddenException("Faqat tayyor (COMPLETED) buyurtmani topshirish mumkin.")
    order.status = OrderStatus.DELIVERED
    order.delivered_at = datetime.now(UTC)
    log_action(
        db,
        module="orders",
        action="delivered",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"Buyurtma topshirildi: {order.number}",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(order)
    await ws_manager.publish("order.delivered", {"order_id": order.id, "order_number": order.number})
    return await _order_read_with_client(db, order)


@router.post("/{order_id}/machines", response_model=Message, operation_id="assign_order_machines")
async def assign_order_machines(
    db: SessionDep, current_user: ManagerOrTexnologUser, order_id: int, body: MachineAssignments, request: Request
) -> Message:
    """Ish markazi tanlovi (TZ 6.4.1): bir postda bir nechta markaz bo'lsa qaysi biri.

    Texnolog ham tanlaydi: marshrutni u chizadi va qaysi stanok qaysi ishni
    bajarishini menejerdan ko'ra yaxshiroq biladi. Tsexda ish boshlangach
    ikkalasiga ham yopiq (`_require_editable`).
    """
    order = await _get_order(db, order_id)
    await _require_editable(db, order, "Ish markazi tanlovini o'zgartirib bo'lmaydi")

    posts_by_code = {p.code: p for p in (await db.execute(select(Post))).scalars()}
    for post_code, machine_id in body.assignments.items():
        post = posts_by_code.get(post_code)
        if post is None:
            raise NotFoundException(f"Post topilmadi: {post_code}")
        machine = (
            await db.execute(
                select(Machine).where(
                    Machine.id == machine_id,
                    Machine.post_id == post.id,
                    Machine.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if machine is None:
            raise NotFoundException(f"{post_code} postida {machine_id} ish markazi topilmadi.")
        # Yangi ish faqat AKTIV ish markaziga: ta'mirdagi stanokka biriktirilgan
        # buyurtma terminalda ko'rinadi-yu, bajariladigan joyi yo'q
        if machine.status != MachineStatus.ACTIVE:
            raise HTTPException(
                status_code=409,
                detail=f"{machine.name} — {MACHINE_STATUS_LABELS[machine.status]}. Yangi ishni biriktirib bo'lmaydi.",
            )

    order.machine_assignments = {str(k): v for k, v in body.assignments.items()}
    log_action(
        db,
        module="orders",
        action="machines_assigned",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        meta={"assignments": order.machine_assignments},
        ip=client_ip(request),
    )
    await db.commit()
    return Message(message="Ish markazlari biriktirildi.")


@router.post("/{order_id}/confirm", response_model=OrderRead, operation_id="confirm_order")
async def confirm_order(db: SessionDep, current_user: ManagerUser, order_id: int, request: Request) -> OrderRead:
    """Manager 'Tasdiqlash': DRAFT → TECHNICAL_REVIEW — buyurtma texnologga o'tadi.
    Tasdiqlanmaganlar DRAFT holatda qoladi; texnolog ularga fayl biriktira olmaydi."""
    order = await _get_order(db, order_id)
    if order.status != OrderStatus.DRAFT:
        raise ForbiddenException("Faqat qoralama (DRAFT) buyurtmani tasdiqlash mumkin.")
    if order.amount is None:
        raise ForbiddenException("Tasdiqlashdan oldin buyurtma narxi kiritilishi kerak.")
    order.status = OrderStatus.TECHNICAL_REVIEW
    log_action(
        db,
        module="orders",
        action="confirmed",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message="Manager buyurtmani tasdiqlab texnologga uzatdi",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(order)
    return await _order_read_with_client(db, order)


@router.post("/{order_id}/start", response_model=OrderRead, operation_id="start_order_production")
async def start_order_production(
    db: SessionDep, current_user: ManagerOrTexnologUser, order_id: int, request: Request
) -> OrderRead:
    """'Ishlab chiqarishga uzatish' (TZ 6.4.2): TECHNICAL_REVIEW → PRODUCTION.

    Menejer ham, TEXNOLOG ham uzata oladi. TZ da bu faqat menejer amali edi, lekin
    tayyorlikni texnolog birinchi biladi: `.project` faylni u yuklaydi va nostandart
    detallarning marshrutini u chizadi — menejerni kutish bekorga to'siq edi.
    """
    order = await _get_order(db, order_id)
    if order.status != OrderStatus.TECHNICAL_REVIEW:
        raise ForbiddenException("Buyurtma avval tasdiqlangan bo'lishi kerak.")
    if order.project_uuid is None:
        raise ForbiddenException("Texnolog hali .project fayl biriktirmagan.")

    # Marshrutsiz detal jimgina ishlab chiqarilmay qolardi: u terminalda ham, TABLOda ham
    # ko'rinmaydi va buyurtma usiz "tayyor" bo'ladi. Shuning uchun bu yerda to'xtatiladi.
    routeless = (
        (
            await db.execute(
                select(Product.code, Part.code)
                .join(Product, Product.id == Part.product_id)
                .outerjoin(
                    PartRoute,
                    (PartRoute.part_id == Part.id)
                    & (PartRoute.is_enabled == True)  # noqa: E712
                    & (PartRoute.is_deleted == False),  # noqa: E712
                )
                .where(Part.order_id == order_id, Part.is_deleted == False)  # noqa: E712
                .group_by(Product.code, Part.code)
                .having(func.count(PartRoute.id) == 0)
                .order_by(Product.code, Part.code)
            )
        )
        .tuples()
        .all()
    )
    if routeless:
        names = ", ".join(f"{pc}_{code}" for pc, code in routeless[:5])
        more = f" va yana {len(routeless) - 5} ta" if len(routeless) > 5 else ""
        raise ForbiddenException(f"Marshruti berilmagan detallar bor: {names}{more}. Texnologga qaytaring.")

    # Marshrutning BIRINCHI qadami arra yoki roverda bo'lishi shart — chek o'sha
    # postda chiqadi. Boshqa postdan boshlansa detalga QR chiqmaydi va u butun
    # oqimdan tushib qoladi (matritsadagi tugma bilan ham shunday holat yasash mumkin).
    steps = (
        (
            await db.execute(
                select(Product.code, Part.code, PartRoute.seq, Post.code)
                .join(Product, Product.id == Part.product_id)
                .join(PartRoute, PartRoute.part_id == Part.id)
                .join(Post, Post.id == PartRoute.post_id)
                .where(
                    Part.order_id == order_id,
                    Part.is_deleted == False,  # noqa: E712
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                )
                .order_by(Product.code, Part.code, PartRoute.seq)
            )
        )
        .tuples()
        .all()
    )
    first_post: dict[str, str] = {}
    for product_code, part_code, _seq, post_code in steps:  # seq bo'yicha saralangan — birinchisi qoladi
        first_post.setdefault(f"{product_code}_{part_code}", post_code)
    bad_start = [name for name, post_code in first_post.items() if post_code not in _ROUTE_START_POSTS]
    if bad_start:
        names = ", ".join(bad_start[:5]) + (f" va yana {len(bad_start) - 5} ta" if len(bad_start) > 5 else "")
        raise ForbiddenException(
            f"Marshruti Arra yoki Rover'dan boshlanmagan detallar bor: {names}. Ularga chek chiqmaydi."
        )

    # Posts with several machines and requires_assignment_choice must be assigned.
    posts = {p.id: p for p in (await db.execute(select(Post))).scalars()}
    used_post_ids = (
        (
            await db.execute(
                select(PartRoute.post_id)
                .where(
                    PartRoute.order_id == order_id,
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                )
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    missing = [
        posts[pid].code
        for pid in used_post_ids
        if posts[pid].requires_assignment_choice and str(posts[pid].code) not in order.machine_assignments
    ]
    if missing:
        raise ForbiddenException(f"Ish markazi tanlanmagan postlar: {', '.join(missing)}")

    # Stamp the chosen machine on route rows so terminals filter by machine.
    for pid in used_post_ids:
        machine_id = order.machine_assignments.get(str(posts[pid].code))
        if machine_id is not None:
            routes = (
                (
                    await db.execute(
                        select(PartRoute).where(
                            PartRoute.order_id == order_id,
                            PartRoute.post_id == pid,
                            PartRoute.is_deleted == False,  # noqa: E712
                        )
                    )
                )
                .scalars()
                .all()
            )
            for route in routes:
                route.machine_id = machine_id

    order.status = OrderStatus.PRODUCTION
    order.production_started_at = datetime.now(UTC)
    log_action(
        db,
        module="orders",
        action="production_started",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"Buyurtma ishlab chiqarishga uzatildi: {order.number}",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(order)
    await ws_manager.publish("order.started", {"order_id": order.id, "order_number": order.number})
    return await _order_read_with_client(db, order)
