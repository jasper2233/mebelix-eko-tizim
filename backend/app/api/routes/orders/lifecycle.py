import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import delete, func, or_, select, update
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
    AuditLog,
    Client,
    Machine,
    Order,
    OrderFile,
    Pachka,
    PachkaItem,
    Part,
    PartInstance,
    PartRoute,
    Post,
    Product,
    Scan,
    WasteItem,
)
from app.models.enums import (
    MACHINE_STATUS_LABELS,
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
    OrderUpdate,
)

from ._common import (
    _ROUTE_START_POSTS,
    _edit_block_reason,
    _get_order,
    _get_visible_order,
    _hidden_statuses,
    _require_editable,
    stamp_route_machines,
)

# Prefiks va tag PARENT routerda (`orders/__init__.py`) — bu yerda takrorlansa
# `include_router` ularni QO'SHADI, almashtirmaydi va generatsiya qilingan
# klientda metod ikki klassga nusxalanadi.
logger = logging.getLogger(__name__)

router = APIRouter()


def _order_read(order: Order, client_name: str) -> OrderRead:
    item = OrderRead.model_validate(order)
    item.client_name = client_name
    return item


async def _order_read_with_client(db: SessionDep, order: Order) -> OrderRead:
    """Javob uchun mijoz nomini qo'shib beradi (soft-deleted mijozda bo'sh satr)."""
    client = await crud_clients.get(db, id=order.client_id)
    return _order_read(order, client.full_name if client else "")


def _first_n(items: list[str], n: int = 5) -> str:
    """Birinchi n ta nom + «va yana N ta» — xato xabari yuzlab detal bilan to'lib ketmasin."""
    return ", ".join(items[:n]) + (f" va yana {len(items) - n} ta" if len(items) > n else "")


@router.post("/", response_model=OrderRead, status_code=201, operation_id="create_order")
async def create_order(db: SessionDep, current_user: ManagerUser, body: OrderCreate, request: Request) -> OrderRead:
    client = await crud_clients.get(db, id=body.client_id)
    if client is None:
        raise NotFoundException("Mijoz topilmadi.")

    # Rollback (expire_on_rollback default True) sessiyadagi HAMMA obyektni expire
    # qiladi, shu sababli retry'dan keyin kerak bo'ladigan qiymatlar oldindan olinadi.
    user_id = current_user.id
    client_name = client.full_name

    # Sequential number has a race window between two managers — the partial unique
    # index is the arbiter; retry regenerates from the committed max.
    for attempt in range(3):
        order = Order(**body.model_dump(), number=await crud_orders.next_number(db), created_by_id=user_id)
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
        user_id=user_id,
        entity_type="order",
        entity_id=order.id,
        message=f"Buyurtma yaratildi: {order.number}",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(order)
    await ws_manager.publish("order.created", {"order_id": order.id, "order_number": order.number})
    return _order_read(order, client_name)


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
    items = [_order_read(order, client_name) for order, client_name in rows]
    # Bekor qilinganlar ro'yxati: har qatorga tirik skan soni — superuser qaysi
    # birini o'chira olishini sahifaga kirmasdan ko'rsin. Bitta guruhlangan so'rov.
    cancelled_ids = [o.id for o in items if o.status == OrderStatus.CANCELLED]
    if cancelled_ids:
        live: dict[int, int] = {}
        for order_id, n in (
            await db.execute(
                select(Scan.order_id, func.count(Scan.id))
                .where(
                    Scan.order_id.in_(cancelled_ids),
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .group_by(Scan.order_id)
            )
        ).all():
            live[order_id] = n
        for o in items:
            if o.status == OrderStatus.CANCELLED:
                o.live_scans = int(live.get(o.id, 0))
    return Paginated(data=items, count=total)


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
    # Oxirgi amal — audit logning shu buyurtmaga tegishli eng yangi yozuvi
    # (kim + nima + qachon). Bitta so'rov; log bo'lmasa maydonlar None.
    last = (
        await db.execute(
            select(AuditLog, User)
            .outerjoin(User, User.id == AuditLog.user_id)
            .where(AuditLog.module == "orders", AuditLog.entity_id == order_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(1)
        )
    ).first()
    if last is not None:
        entry, actor = last
        detail.last_action = entry.action
        detail.last_action_at = entry.created_at
        detail.last_action_by_name = (actor.name or actor.username) if actor else None
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


@router.post("/{order_id}/cancel", response_model=OrderRead, operation_id="cancel_order")
async def cancel_order(
    db: SessionDep, current_user: ManagerUser, order_id: int, body: OrderCancel, request: Request
) -> OrderRead:
    """any stage; scans/history stay for audit; terminals are notified in real time."""
    order = await _get_order(db, order_id)
    if order.status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        raise ForbiddenException("Bu buyurtmani bekor qilib bo'lmaydi.")
    if order.status == OrderStatus.DRAFT:
        # Qoralamada bekor qilish ma'nosiz (tijoriy ahamiyat yo'q) va u «Bekor
        # qilingan» ro'yxatini xato ochilgan qoralamalar bilan to'ldirardi.
        raise ForbiddenException("Qoralama bekor qilinmaydi — uni o'chiring.")
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
    # Terminals drop the tasks IMMEDIATELY — real-time, all posts.
    await ws_manager.publish("order.cancelled", {"order_id": order.id, "order_number": order.number})
    return await _order_read_with_client(db, order)


@router.delete("/{order_id}", response_model=Message, operation_id="delete_order")
async def delete_order(db: SessionDep, current_user: ManagerUser, order_id: int, request: Request) -> Message:
    """Buyurtmani o'chirish — IKKI yo'l, ikkalasida ham buyurtma qatori TOSHBITIK
    bo'lib qoladi (`is_deleted`, ro'yxatlarda ko'rinmaydi): raqam qayta
    berilmaydi (`next_number` maksimumni shu qatorlar bilan hisoblaydi) va
    `audit_log.entity_id` yetim qolmaydi.

    1. QORALAMA — menejer o'zi o'chiradi, sababsiz: hali tijoriy ahamiyati yo'q
       (tasdiqlanmagan, fayl yo'q, tsexda ish yo'q). Ilgari yagona yo'l «bekor
       qilish» edi va xato ochilgan qoralamalar «Bekor qilingan» ro'yxatini
       to'ldirardi.
    2. BEKOR QILINGAN — faqat superuser: bolalar (detallar, nusxalar, marshrut,
       skanlar, qadoqlar) va diskdagi fayllar butunlay o'chadi. Bekor qilinmagan
       skani bor buyurtma o'chirilmaydi: skan — bajarilgan ish, ish haqiga
       kiradi (`reports.py`); bunday buyurtma arxivda qoladi.
    Boshqa holatlar (texnologda, jarayonda, tayyor, topshirilgan) o'chirilmaydi —
    avval bekor qilinadi (sabab bilan), tarix saqlanadi.
    """
    order = await _get_order(db, order_id)
    if order.status == OrderStatus.DRAFT:
        order.is_deleted = True
        order.deleted_at = datetime.now(UTC)
        log_action(
            db,
            module="orders",
            action="deleted",
            user_id=current_user.id,
            entity_type="order",
            entity_id=order_id,
            message=f"Qoralama o'chirildi: {order.number}",
            ip=client_ip(request),
        )
        await db.commit()
        await ws_manager.publish("order.deleted", {"order_id": order_id, "order_number": order.number})
        return Message(message=f"Qoralama o'chirildi: {order.number}")
    if order.status != OrderStatus.CANCELLED:
        raise ForbiddenException(
            "Faqat qoralama yoki bekor qilingan buyurtma o'chiriladi. Avval bekor qiling — tarix saqlanadi."
        )
    if not current_user.is_superuser:
        raise ForbiddenException("Bekor qilingan buyurtmani faqat superuser o'chiradi.")

    live_scans = (
        await db.execute(
            select(func.count(Scan.id)).where(
                Scan.order_id == order_id,
                Scan.is_cancelled == False,  # noqa: E712
                Scan.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one()
    if live_scans:
        raise ForbiddenException(
            f"Bu buyurtmada {live_scans} ta bekor qilinmagan skan bor — ish haqi hisobiga kiradi. "
            "O'chirish uchun avval o'sha skanlarni bekor qiling."
        )

    number = order.number
    # Fayl yo'llari qator o'chishidan OLDIN olinadi.
    paths = (await db.execute(select(OrderFile.path).where(OrderFile.order_id == order_id))).scalars().all()

    # FK'larda `ON DELETE` yo'q — tartib qo'lda. Bolalardan ota-onalarga.
    instances = select(PartInstance.id).where(PartInstance.order_id == order_id)
    pachkas = select(Pachka.id).where(Pachka.order_id == order_id)
    await db.execute(
        delete(PachkaItem).where(or_(PachkaItem.pachka_id.in_(pachkas), PachkaItem.instance_id.in_(instances)))
    )
    await db.execute(delete(Pachka).where(Pachka.order_id == order_id))
    await db.execute(delete(Scan).where(Scan.order_id == order_id))
    await db.execute(delete(WasteItem).where(WasteItem.order_id == order_id))
    await db.execute(delete(OrderFile).where(OrderFile.order_id == order_id))
    await db.execute(delete(PartRoute).where(PartRoute.order_id == order_id))
    await db.execute(delete(PartInstance).where(PartInstance.order_id == order_id))
    # `part.assembly_parent_id` o'ziga qaraydi: bitta DELETE da qatorlar tartibi
    # kafolatlanmaydi, shuning uchun avval bog'lam uziladi.
    await db.execute(update(Part).where(Part.order_id == order_id).values(assembly_parent_id=None))
    await db.execute(delete(Part).where(Part.order_id == order_id))
    await db.execute(delete(Product).where(Product.order_id == order_id))
    # Buyurtma qatori TOSHBITIK: raqam band qoladi, audit izi butun.
    order.is_deleted = True
    order.deleted_at = datetime.now(UTC)

    log_action(
        db,
        module="orders",
        action="deleted",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order_id,
        message=f"Bekor qilingan buyurtma bazadan o'chirildi: {number} ({len(paths)} fayl)",
        ip=client_ip(request),
    )
    await db.commit()

    root = upload_root()
    for path in paths:
        try:
            (root / path).unlink(missing_ok=True)
        except OSError:
            logger.warning("Buyurtma faylini o'chirib bo'lmadi: %s", path)

    return Message(message=f"Buyurtma o'chirildi: {number}")


@router.post("/{order_id}/deliver", response_model=OrderRead, operation_id="deliver_order")
async def deliver_order(db: SessionDep, current_user: ManagerUser, order_id: int, request: Request) -> OrderRead:
    """TOPSHIRILDI — only from COMPLETED; date recorded automatically."""
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
    """Ish markazi tanlovi: bir postda bir nechta markaz bo'lsa qaysi biri.

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
    # Ishlab chiqarishdagi buyurtmada tanlov o'zgarsa marshrut muhri ham
    # yangilanishi shart, aks holda buyurtma eski stanokda qolib ketadi.
    if order.status == OrderStatus.PRODUCTION:
        await stamp_route_machines(db, order)
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
    """'Ishlab chiqarishga uzatish': TECHNICAL_REVIEW → PRODUCTION.

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
        names = _first_n([f"{pc}_{code}" for pc, code in routeless])
        raise ForbiddenException(f"Marshruti berilmagan detallar bor: {names}. Texnologga qaytaring.")

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
        raise ForbiddenException(
            f"Marshruti Arra yoki Rover'dan boshlanmagan detallar bor: {_first_n(bad_start)}. Ularga chek chiqmaydi."
        )

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
    # Tanlov TALAB qilinadigan post: aktiv stanok BITTA bo'lsa tanlaydigan narsa
    # yo'q — o'zi biriktiriladi (UI ham bitta variantli selectni ko'rsatmaydi).
    # Ikki va undan ko'p bo'lsa odam tanlashi shart — avvalgidek 403.
    assignments = dict(order.machine_assignments)
    for pid in used_post_ids:
        post = posts[pid]
        if not post.requires_assignment_choice or str(post.code) in assignments:
            continue
        active = (
            (
                await db.execute(
                    select(Machine.id).where(
                        Machine.post_id == pid,
                        Machine.status == MachineStatus.ACTIVE,
                        Machine.is_deleted == False,  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        )
        if len(active) == 1:
            assignments[str(post.code)] = active[0]
    if assignments != order.machine_assignments:
        order.machine_assignments = assignments  # JSONB: yangi dict — o'zgarish aniqlansin
    missing = [
        posts[pid].code
        for pid in used_post_ids
        if posts[pid].requires_assignment_choice and str(posts[pid].code) not in assignments
    ]
    if missing:
        raise ForbiddenException(f"Ish markazi tanlanmagan postlar: {', '.join(missing)}")

    # Tanlangan stanokni marshrut qatorlariga muhrlash — terminal shu bo'yicha filtrlaydi.
    await stamp_route_machines(db, order)

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
