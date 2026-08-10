import contextlib
import io
import zipfile
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import defer

from app.api.deps import ManagerUser, SessionDep, StaffReadUser, TexnologUser, client_ip
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
from app.models.enums import FileKind, OrderStatus, PostCode, RouteSource, UserRole
from app.models.user import User
from app.schemas.common import Message, Paginated
from app.schemas.orders import (
    MachineAssignments,
    MatrixEdit,
    MatrixPart,
    OrderCancel,
    OrderCreate,
    OrderDetail,
    OrderFileRead,
    OrderMatrix,
    OrderRead,
    OrderSurvey,
    OrderUpdate,
    RouteCell,
)
from app.schemas.terminal import CutmapState
from app.services.giblab import ParseError, parse_project
from app.services.giblab.ingest import (
    ingest_project,
    restore_custom_routes,
    snapshot_custom_routes,
    wipe_previous_parse,
    write_and_register_scx,
)
from app.services.giblab.models import DEFAULT_PROCESS_CODE, PROCESS_POSTS

router = APIRouter(prefix="/orders", tags=["orders"])

_EDITABLE_STATUSES = (OrderStatus.DRAFT, OrderStatus.TECHNICAL_REVIEW)


def _hidden_statuses(user: User) -> set[OrderStatus]:
    """Texnolog navbatiga tushmagan holatlar: qoralama (hali tasdiqlanmagan,
    tijoriy bosqich) va bekor qilinganlar. Buyurtma texnologga confirm'dan
    keyin (TECHNICAL_REVIEW) ko'rinadi."""
    if user.role == UserRole.TEXNOLOG and not user.is_superuser:
        return {OrderStatus.DRAFT, OrderStatus.CANCELLED}
    return set()


async def _get_order(db: SessionDep, order_id: int) -> Order:
    return await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)


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
    order = await _get_order(db, order_id)
    # List'da yashiringan holat to'g'ridan ID bilan ham ochilmasin
    if order.status in _hidden_statuses(current_user):
        raise NotFoundException("Buyurtma topilmadi.")
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
    detail.files = [OrderFileRead.model_validate(f) for f in files]
    detail.parts_count = parts_count
    detail.instances_count = instances_count
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


@router.get("/{order_id}/matrix", response_model=OrderMatrix, operation_id="read_order_matrix")
async def read_order_matrix(db: SessionDep, _: StaffReadUser, order_id: int) -> OrderMatrix:
    await _get_order(db, order_id)
    rows = (
        await db.execute(
            select(Part, Product.code)
            .join(Product, Product.id == Part.product_id)
            .where(Part.order_id == order_id, Part.is_deleted == False)  # noqa: E712
            .order_by(Product.code, Part.code)
        )
    ).all()
    routes = (
        (
            await db.execute(
                select(PartRoute).where(
                    PartRoute.order_id == order_id,
                    PartRoute.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    routes_by_part: dict[int, list[RouteCell]] = {}
    for r in routes:
        routes_by_part.setdefault(r.part_id, []).append(RouteCell.model_validate(r))

    parts = [
        MatrixPart(
            id=part.id,
            product_code=product_code,
            code=part.code,
            name=part.name,
            count=part.count,
            length=part.length,
            width=part.width,
            thickness=part.thickness,
            label_num=part.label_num,
            edges=part.edges,
            xnc_summary=part.xnc_summary,
            note=part.note,
            is_custom=part.is_custom,
            routes=sorted(routes_by_part.get(part.id, []), key=lambda c: c.seq),
        )
        for part, product_code in rows
    ]
    return OrderMatrix(order_id=order_id, parts=parts)


@router.patch("/{order_id}/matrix", response_model=OrderMatrix, operation_id="edit_order_matrix")
async def edit_order_matrix(
    db: SessionDep, current_user: TexnologUser, order_id: int, body: MatrixEdit, request: Request
) -> OrderMatrix:
    """Texnolog matrix edits (TZ 6.3.3): stage toggles, notes, rare count fixes. Pre-production only."""
    order = await _get_order(db, order_id)
    if order.status not in _EDITABLE_STATUSES:
        raise ForbiddenException("Matritsani faqat ishlab chiqarishga uzatilgunga qadar o'zgartirish mumkin.")

    posts = {p.id: p for p in (await db.execute(select(Post))).scalars()}
    # Anketadagi "Upakovka qilish" — qo'lda chizilgan marshrutga ham qadoqlash
    # qadamini qo'shadi (buyurtma qadoqlansa HAMMA detal qadoqlanadi).
    packaging = bool((order.survey or {}).get("packaging"))

    for edit in body.edits:
        part = (
            await db.execute(
                select(Part).where(Part.id == edit.part_id, Part.order_id == order_id, Part.is_deleted == False)  # noqa: E712
            )
        ).scalar_one_or_none()
        if part is None:
            raise NotFoundException(f"Detal topilmadi: {edit.part_id}")

        if edit.note is not None:
            part.note = edit.note

        if edit.count is not None and edit.count != part.count:
            await _resize_instances(db, part, edit.count)

        # Nostandart bayrog'i marshrut manbasini almashtiradi. Avtomatik qadamlar
        # o'chirilmaydi — YUMSHOQ o'chiriladi, bayroq qaytarilsa aynan tiklanadi
        # (fayl ma'lumotidan qayta hisoblash taxminiy bo'lardi).
        if edit.is_custom is not None and edit.is_custom != part.is_custom:
            part.is_custom = edit.is_custom
            drop, restore = (
                (RouteSource.AUTO, RouteSource.MANUAL) if edit.is_custom else (RouteSource.MANUAL, RouteSource.AUTO)
            )
            await db.execute(
                update(PartRoute)
                .where(PartRoute.part_id == part.id, PartRoute.source == drop, PartRoute.is_deleted == False)  # noqa: E712
                .values(is_deleted=True, deleted_at=datetime.now(UTC))
            )
            await db.execute(
                update(PartRoute)
                .where(PartRoute.part_id == part.id, PartRoute.source == restore, PartRoute.is_deleted == True)  # noqa: E712
                .values(is_deleted=False, deleted_at=None)
            )

        if edit.route_codes is not None:
            if not part.is_custom:
                raise ForbiddenException("Marshrutni faqat nostandart detalga qo'lda chizish mumkin.")
            await _set_custom_route(db, order_id, part, edit.route_codes, posts, packaging)

        for post_id, enabled in edit.stages.items():
            post = posts.get(post_id)
            if post is None:
                raise NotFoundException(f"Post topilmadi: {post_id}")
            if post.code == PostCode.ARRA and not enabled and not part.is_custom:
                raise ForbiddenException("ARRA bosqichini o'chirib bo'lmaydi — har standart detal uchun majburiy.")
            # Bitta post marshrutda takrorlanishi mumkin — bu yerdagi tugma HAMMA
            # qadamni birga yoqadi/o'chiradi (qadam-baqadam tahrir nostandart tabda).
            steps = (
                (
                    await db.execute(
                        select(PartRoute).where(
                            PartRoute.part_id == part.id,
                            PartRoute.post_id == post_id,
                            PartRoute.is_deleted == False,  # noqa: E712
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not steps and enabled:
                next_seq = (
                    await db.execute(
                        select(func.coalesce(func.max(PartRoute.seq), 0) + 1).where(
                            PartRoute.part_id == part.id,
                            PartRoute.is_deleted == False,  # noqa: E712
                        )
                    )
                ).scalar_one()
                db.add(
                    PartRoute(
                        order_id=order_id,
                        part_id=part.id,
                        post_id=post_id,
                        seq=next_seq,
                        process_code=DEFAULT_PROCESS_CODE[post.code],
                        source=RouteSource.MANUAL,
                        per_instance=1,
                        total_required=part.count,
                    )
                )
            for step in steps:
                step.is_enabled = enabled

    log_action(
        db,
        module="orders",
        action="matrix_edited",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order_id,
        message=f"Texnolog matritsani tahrirladi ({len(body.edits)} detal)",
        ip=client_ip(request),
    )
    await db.commit()
    return await read_order_matrix(db, current_user, order_id)


#: Nostandart marshrut faqat shu postlardan boshlanadi: detal yo arrada kesiladi,
#: yo roverda. Ikkalasi ham chek chiqaradi — boshqa post boshlansa detalda QR bo'lmaydi.
_ROUTE_START_POSTS = (PostCode.ARRA, PostCode.ROVER)


async def _set_custom_route(
    db: SessionDep, order_id: int, part: Part, codes: list[int], posts: dict[int, Post], packaging: bool
) -> None:
    """Nostandart detal marshrutini jarayon kodlari ro'yxatidan qayta quradi.

    Ro'yxat TARTIBLI va kod takrorlanishi mumkin ([3, 6, 3] — kromkaga qaytish).
    Kromka/oval BIRINCHI kelganda qirralar soni marta skanlanadi, takrorida bitta."""
    for code in codes:
        if code not in PROCESS_POSTS:
            raise ForbiddenException(f"Noma'lum jarayon kodi: {code}. Ruxsat etilgan: 1–14.")
    if codes and PROCESS_POSTS[codes[0]] not in _ROUTE_START_POSTS:
        raise ForbiddenException("Marshrut faqat Arra yoki Rover'dan boshlanadi — chek o'sha yerda chiqadi.")

    by_code = {p.code: p for p in posts.values()}
    # Eski QO'LDA chizilgan qadamlar BUTUNLAY o'chiriladi: ular almashtirilyapti,
    # tarix emas (tahrir faqat ishlab chiqarishgacha — bu qatorlarga skan yo'q).
    # Yumshoq o'chirilsa avlodlar to'planib qolardi va bayroq standartga qaytarilib
    # yana yoqilganda HAMMASI birdan tiklanib `(part_id, seq)` yagonaligini buzardi.
    await db.execute(delete(PartRoute).where(PartRoute.part_id == part.id, PartRoute.source == RouteSource.MANUAL))
    # Fayldan kelgan qadamlar esa yumshoq o'chadi — detal standartga qaytsa tiklanadi.
    await db.execute(
        update(PartRoute)
        .where(
            PartRoute.part_id == part.id,
            PartRoute.source == RouteSource.AUTO,
            PartRoute.is_deleted == False,  # noqa: E712
        )
        .values(is_deleted=True, deleted_at=datetime.now(UTC))
    )
    edge_count = len(part.edges) or 1
    seen: set[PostCode] = set()
    for seq, code in enumerate(codes, start=1):
        post_code = PROCESS_POSTS[code]
        post = by_code.get(post_code)
        if post is None:
            raise NotFoundException(f"Post sozlanmagan: {post_code}. Administratorga murojaat qiling.")
        first_edge_pass = post_code in (PostCode.KROMKA, PostCode.OVAL) and post_code not in seen
        seen.add(post_code)
        per_instance = edge_count if first_edge_pass else 1
        db.add(
            PartRoute(
                order_id=order_id,
                part_id=part.id,
                post_id=post.id,
                seq=seq,
                process_code=code,
                source=RouteSource.MANUAL,
                per_instance=per_instance,
                total_required=part.count * per_instance,
            )
        )
    # Qadoqlash va ombor — texnolog tanlamaydi. Qadoqlashni anketadagi bayroq
    # qo'shadi, ombor esa HAR doim oxirgi qadam bo'ladi.
    if codes:
        tail = [(15, PostCode.UPAKOVKA)] if packaging else []
        tail.append((16, PostCode.OMBOR))
        for offset, (code, post_code) in enumerate(tail):
            post = by_code.get(post_code)
            if post is None:
                raise NotFoundException(f"Post sozlanmagan: {post_code}. Administratorga murojaat qiling.")
            db.add(
                PartRoute(
                    order_id=order_id,
                    part_id=part.id,
                    post_id=post.id,
                    seq=len(codes) + 1 + offset,
                    process_code=code,
                    source=RouteSource.MANUAL,
                    per_instance=1,
                    total_required=part.count,
                )
            )


async def _resize_instances(db: SessionDep, part: Part, new_count: int) -> None:
    """Adjust physical copies + route totals when texnolog changes count (pre-production only)."""
    product_code = (await db.execute(select(Product.code).where(Product.id == part.product_id))).scalar_one()
    instances = (
        (
            await db.execute(
                select(PartInstance).where(
                    PartInstance.part_id == part.id,
                    PartInstance.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    existing = {i.instance_no: i for i in instances}
    key = f"{product_code}_{part.code}"
    # QR konvensiyasi (TZ 5.8): yagona nusxa suffikssiz, ko'p nusxada _1.._n.
    # Count o'zgarganda BARCHA tirik nusxalar qayta normallanadi (1↔N o'tishda
    # eski QR konvensiyaga zid qolib ketmasin) — bosqich pre-production,
    # yorliqlar hali chop etilmagan.
    for n in range(1, new_count + 1):
        qr = key if new_count == 1 else f"{key}_{n}"
        if n in existing:
            existing[n].qr_text = qr
        else:
            db.add(
                PartInstance(
                    order_id=part.order_id,
                    part_id=part.id,
                    instance_no=n,
                    qr_text=qr,
                )
            )
    now = datetime.now(UTC)
    for no, inst in existing.items():
        if no > new_count:
            inst.is_deleted = True
            inst.deleted_at = now

    part.count = new_count
    # YUMSHOQ o'chirilganlari ham yangilanadi: nostandart bayrog'i qaytarilganda
    # o'sha qatorlar tiklanadi va eski `total_required` bilan tirilsa navbat,
    # QOLDIQ va TABLO foizlari buzilardi.
    routes = (await db.execute(select(PartRoute).where(PartRoute.part_id == part.id))).scalars().all()
    for route in routes:
        route.total_required = new_count * route.per_instance


@router.post("/{order_id}/machines", response_model=Message, operation_id="assign_order_machines")
async def assign_order_machines(
    db: SessionDep, current_user: ManagerUser, order_id: int, body: MachineAssignments, request: Request
) -> Message:
    """Manager picks a machine per post where several exist (TZ 6.4.1)."""
    order = await _get_order(db, order_id)
    if order.status not in _EDITABLE_STATUSES:
        raise ForbiddenException("Stanok tanlovi faqat ishlab chiqarishga uzatilgunga qadar mumkin.")

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
            raise NotFoundException(f"{post_code} postida {machine_id} stanok topilmadi.")

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
    return Message(message="Stanoklar biriktirildi.")


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
    db: SessionDep, current_user: ManagerUser, order_id: int, request: Request
) -> OrderRead:
    """Manager 'Ishlab chiqarishga uzatish' (TZ 6.4.2): TECHNICAL_REVIEW → PRODUCTION."""
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
        raise ForbiddenException(f"Stanok tanlanmagan postlar: {', '.join(missing)}")

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


@router.post("/{order_id}/upload", response_model=Message, operation_id="upload_order_project")
async def upload_order_project(
    db: SessionDep, current_user: TexnologUser, order_id: int, file: UploadFile, request: Request
) -> Message:
    """Texnolog uploads the .project file (TZ 6.3). Exactly ONE file per order; re-upload
    replaces all previous parse results and is allowed only before PRODUCTION."""
    order = await _get_order(db, order_id)
    if order.status != OrderStatus.TECHNICAL_REVIEW:
        raise ForbiddenException(
            "Fayl faqat tasdiqlangan buyurtmaga yuklanadi. Avval manager buyurtmani tasdiqlashi kerak."
        )
    if not (file.filename or "").lower().endswith(".project"):
        raise HTTPException(status_code=422, detail="Faqat .project kengaytmali fayl qabul qilinadi.")

    content = await file.read()
    if len(content) > settings.MAX_PROJECT_FILE_SIZE:
        raise HTTPException(status_code=422, detail="Fayl juda katta.")

    try:
        project = parse_project(content)
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    if project.generation == "template":
        # TZ 5.3.3: TEMPLATE = not yet optimized in GibLab — reject with the exact guidance text.
        raise HTTPException(
            status_code=422,
            detail=(
                "Bu fayl GibLabda hali optimizatsiya qilinmagan. Iltimos, kesish chizmasini va "
                "kromka materiallarini belgilab, qaytadan eksport qilib yuklang."
            ),
        )

    root = upload_root()
    # Qo'lda chizilgan marshrutlar fayldan kelmaydi — qayta yuklashda ular bilan birga
    # yo'qolib ketmasligi uchun detal kodi bo'yicha saqlab turiladi.
    saved_routes = await snapshot_custom_routes(db, order)
    await wipe_previous_parse(db, order, root)
    try:
        summary = await ingest_project(db, order, project, content, file.filename or "project.project", root)
        restored, lost = await restore_custom_routes(db, order, saved_routes)
    except ParseError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from None
    if restored:
        summary["warnings"].append(f"{restored} nostandart detalning qo'lda chizilgan marshruti tiklandi.")
    if lost:
        names = ", ".join(lost[:5]) + (f" va yana {len(lost) - 5} ta" if len(lost) > 5 else "")
        summary["warnings"].append(f"Yangi faylda topilmagani uchun marshruti yo'qolgan detallar: {names}")

    log_action(
        db,
        module="orders",
        action="project_uploaded",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"Project fayl yuklandi: {file.filename}",
        meta=summary,
        ip=client_ip(request),
    )
    await db.commit()
    warnings = summary["warnings"]
    text = (
        f"Fayl qabul qilindi: {summary['products']} mahsulot, {summary['parts']} detal, {summary['instances']} nusxa."
    )
    if warnings:
        # Ogohlantirishlar avval faqat audit logga tushardi — menejer ularni ko'rmasdi.
        text += f" Diqqat ({len(warnings)}): " + " | ".join(warnings[:3])
        if len(warnings) > 3:
            text += f" | va yana {len(warnings) - 3} ta (audit logda to'liq)"
    return Message(message=text)


@router.get("/{order_id}/files/scx.zip", operation_id="download_order_scx_zip")
async def download_order_scx_zip(db: SessionDep, _: StaffReadUser, order_id: int) -> Response:
    """Barcha SCX dasturlarini bitta arxivda berish — prisadkachi stanokka bittalab emas,
    bitta ZIP ko'chiradi. Fayllar kichik (bir necha KB), xotirada yig'ish yetarli."""
    order = await _get_order(db, order_id)
    rows = (
        (
            await db.execute(
                select(OrderFile).where(
                    OrderFile.order_id == order_id,
                    OrderFile.kind == FileKind.SCX,
                    OrderFile.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        raise NotFoundException("SCX fayllar topilmadi.")
    root = upload_root()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for row in rows:
            full_path = root / row.path
            if full_path.is_file():
                zf.write(full_path, row.filename)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{order.number}_scx.zip"'},
    )


@router.post("/{order_id}/scx/regenerate", response_model=Message, operation_id="regenerate_order_scx")
async def regenerate_order_scx(db: SessionDep, current_user: TexnologUser, order_id: int, request: Request) -> Message:
    """SCX fayllarni saqlangan .project'dan qayta yaratish — eski buyurtmalarni yangi
    nomlashga (har nusxa = QR nomli fayl, Nanxing skan mosligi) o'tkazadi. Detallar,
    marshrutlar va skanlarga TEGILMAYDI."""
    order = await _get_order(db, order_id)
    root = upload_root()

    project_row = (
        await db.execute(
            select(OrderFile)
            .where(
                OrderFile.order_id == order.id,
                OrderFile.kind == FileKind.PROJECT,
                OrderFile.is_deleted == False,  # noqa: E712
            )
            .order_by(OrderFile.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if project_row is None or not (root / project_row.path).is_file():
        raise NotFoundException(".project fayli diskda topilmadi — qayta yaratib bo'lmaydi.")

    try:
        project = parse_project((root / project_row.path).read_bytes())
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=f"Fayl o'qilmadi: {exc}") from None

    # Mavjud detallar (matritsada soni o'zgargan bo'lishi mumkin — QR'lar bazadan olinadi)
    parts_by_key: dict[str, Part] = {
        f"{product_code}_{part.code}": part
        for part, product_code in (
            await db.execute(
                select(Part, Product.code)
                .join(Product, Product.id == Part.product_id)
                .where(Part.order_id == order.id, Part.is_deleted == False)  # noqa: E712
            )
        ).all()
    }
    qr_by_part: dict[int, list[str]] = {}
    for inst in (
        (
            await db.execute(
                select(PartInstance)
                .where(PartInstance.order_id == order.id, PartInstance.is_deleted == False)  # noqa: E712
                .order_by(PartInstance.part_id, PartInstance.instance_no)
            )
        )
        .scalars()
        .all()
    ):
        qr_by_part.setdefault(inst.part_id, []).append(inst.qr_text)

    # Eski SCX yozuvlari va fayllari yo'qoladi
    now = datetime.now(UTC)
    old_files = (
        (
            await db.execute(
                select(OrderFile).where(
                    OrderFile.order_id == order.id,
                    OrderFile.kind == FileKind.SCX,
                    OrderFile.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    for f in old_files:
        f.is_deleted = True
        f.deleted_at = now
        (root / f.path).unlink(missing_ok=True)

    plate_by_name = {m.name: m.thickness for m in project.materials if m.kind == "sheet" and m.thickness}
    created = 0
    for pp in project.all_parts:
        part = parts_by_key.get(pp.key)
        if part is None or not pp.xnc_ops:
            continue
        created += write_and_register_scx(
            db,
            order.id,
            part.id,
            pp,
            qr_by_part.get(part.id, []),
            root,
            plate_thickness=plate_by_name.get(pp.material_name or ""),
        )

    log_action(
        db,
        module="orders",
        action="scx_regenerated",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"SCX qayta yaratildi: {created} ta fayl ({order.number})",
        ip=client_ip(request),
    )
    await db.commit()
    return Message(message=f"{created} ta SCX fayl qayta yaratildi — endi nomlar nusxa QR'i bilan.")


@router.get("/{order_id}/files/{file_id}", operation_id="download_order_file")
async def download_order_file(db: SessionDep, _: StaffReadUser, order_id: int, file_id: int) -> FileResponse:
    """Download a stored file (project / SCX / document)."""
    row = (
        await db.execute(
            select(OrderFile).where(
                OrderFile.id == file_id,
                OrderFile.order_id == order_id,
                OrderFile.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundException("Fayl topilmadi.")
    full_path = upload_root() / row.path
    if not full_path.is_file():
        raise NotFoundException("Fayl diskda topilmadi.")
    if row.kind in (FileKind.PROJECT, FileKind.SCX):
        media_type = "application/xml"
    else:
        # anketa rasmlari <img> da ko'rsatiladi — to'g'ri turi bo'lmasa brauzer yuklab oladi
        media_type = str(row.meta.get("content_type") or "application/octet-stream")
    return FileResponse(full_path, filename=row.filename, media_type=media_type)


@router.get("/{order_id}/cutmap", response_model=CutmapState, operation_id="read_order_cutmap")
async def read_order_cutmap(db: SessionDep, _: StaffReadUser, order_id: int) -> CutmapState:
    """Kesish xaritalari (TZ 10.3): manager/texnolog view + browser-print for a paper copy."""
    from app.api.routes.terminal import build_cutmap_state

    order = await _get_order(db, order_id)
    arra_post = (await db.execute(select(Post).where(Post.code == PostCode.ARRA))).scalar_one_or_none()
    if arra_post is None:
        raise NotFoundException("ARRA posti topilmadi.")
    return await build_cutmap_state(db, order, arra_post.id)
