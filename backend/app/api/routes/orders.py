from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import ManagerUser, SessionDep, StaffReadUser, TexnologUser
from app.core.config import settings
from app.core.exceptions import DuplicateValueException, ForbiddenException, NotFoundException
from app.core.ws import ws_manager
from app.crud import crud_clients, crud_orders, log_action
from app.models import Client, Machine, Order, OrderFile, Part, PartInstance, PartRoute, Post, Product
from app.models.enums import FileKind, OrderStatus, PostCode, RouteSource
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
    OrderUpdate,
    RouteCell,
)
from app.schemas.terminal import CutmapState
from app.services.giblab import ParseError, parse_project
from app.services.giblab.ingest import ingest_project, wipe_previous_parse

router = APIRouter(prefix="/orders", tags=["orders"])

_EDITABLE_STATUSES = (OrderStatus.DRAFT, OrderStatus.TECHNICAL_REVIEW)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _get_order(db: SessionDep, order_id: int) -> Order:
    order = await crud_orders.get(db, id=order_id)
    if order is None:
        raise NotFoundException("Buyurtma topilmadi.")
    return order


def _order_read(order: Order, client_name: str) -> OrderRead:
    item = OrderRead.model_validate(order)
    item.client_name = client_name
    return item


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
        ip=_client_ip(request),
    )
    await db.commit()
    await db.refresh(order)
    await ws_manager.publish("order.created", {"order_id": order.id, "order_number": order.number})
    return _order_read(order, client.full_name)


@router.get("/", response_model=Paginated[OrderRead], operation_id="read_orders")
async def read_orders(
    db: SessionDep,
    _: StaffReadUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
    status: OrderStatus | None = None,
    search: str | None = None,
) -> Paginated[OrderRead]:
    query = (
        select(Order, Client.full_name).join(Client, Client.id == Order.client_id).where(Order.is_deleted == False)  # noqa: E712
    )
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


@router.get("/{order_id}", response_model=OrderDetail, operation_id="read_order")
async def read_order(db: SessionDep, _: StaffReadUser, order_id: int) -> OrderDetail:
    order = await _get_order(db, order_id)
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
    if "client_id" in update_data and await crud_clients.get(db, id=update_data["client_id"]) is None:
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
        ip=_client_ip(request),
    )
    await db.commit()
    await db.refresh(order)
    client = await crud_clients.get(db, id=order.client_id)
    return _order_read(order, client.full_name if client else "")


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
        ip=_client_ip(request),
    )
    await db.commit()
    await db.refresh(order)
    # Terminals drop the tasks IMMEDIATELY (TZ 6.5) — real-time, all posts.
    await ws_manager.publish("order.cancelled", {"order_id": order.id, "order_number": order.number})
    client = await crud_clients.get(db, id=order.client_id)
    return _order_read(order, client.full_name if client else "")


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
        ip=_client_ip(request),
    )
    await db.commit()
    await db.refresh(order)
    await ws_manager.publish("order.delivered", {"order_id": order.id, "order_number": order.number})
    client = await crud_clients.get(db, id=order.client_id)
    return _order_read(order, client.full_name if client else "")


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
            routes=routes_by_part.get(part.id, []),
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

        for post_id, enabled in edit.stages.items():
            post = posts.get(post_id)
            if post is None:
                raise NotFoundException(f"Post topilmadi: {post_id}")
            if post.code == PostCode.ARRA and not enabled:
                raise ForbiddenException("ARRA bosqichini o'chirib bo'lmaydi — har detal uchun majburiy.")
            route = (
                await db.execute(
                    select(PartRoute).where(
                        PartRoute.part_id == part.id,
                        PartRoute.post_id == post_id,
                        PartRoute.is_deleted == False,  # noqa: E712
                    )
                )
            ).scalar_one_or_none()
            if route is None and enabled:
                db.add(
                    PartRoute(
                        order_id=order_id,
                        part_id=part.id,
                        post_id=post_id,
                        source=RouteSource.MANUAL,
                        per_instance=1,
                        total_required=part.count,
                    )
                )
            elif route is not None:
                route.is_enabled = enabled

    log_action(
        db,
        module="orders",
        action="matrix_edited",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order_id,
        message=f"Texnolog matritsani tahrirladi ({len(body.edits)} detal)",
        ip=_client_ip(request),
    )
    await db.commit()
    return await read_order_matrix(db, current_user, order_id)


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
    for n in range(1, new_count + 1):
        if n not in existing:
            db.add(
                PartInstance(
                    order_id=part.order_id,
                    part_id=part.id,
                    instance_no=n,
                    qr_text=f"{product_code}_{part.code}_{n}",
                )
            )
    now = datetime.now(UTC)
    for no, inst in existing.items():
        if no > new_count:
            inst.is_deleted = True
            inst.deleted_at = now

    part.count = new_count
    routes = (
        (
            await db.execute(
                select(PartRoute).where(
                    PartRoute.part_id == part.id,
                    PartRoute.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
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
        ip=_client_ip(request),
    )
    await db.commit()
    return Message(message="Stanoklar biriktirildi.")


@router.post("/{order_id}/submit-review", response_model=OrderRead, operation_id="submit_order_review")
async def submit_order_review(db: SessionDep, current_user: TexnologUser, order_id: int, request: Request) -> OrderRead:
    """Texnolog 'Tayyor' (TZ 6.3.4): DRAFT → TECHNICAL_REVIEW after the project file is processed."""
    order = await _get_order(db, order_id)
    if order.status != OrderStatus.DRAFT:
        raise ForbiddenException("Faqat qoralama (DRAFT) buyurtmani tasdiqlash mumkin.")
    if order.project_uuid is None:
        raise ForbiddenException("Avval .project fayl yuklanishi kerak.")
    order.status = OrderStatus.TECHNICAL_REVIEW
    log_action(
        db,
        module="orders",
        action="submitted_review",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message="Texnolog buyurtmani tasdiqlab managerga uzatdi",
        ip=_client_ip(request),
    )
    await db.commit()
    await db.refresh(order)
    client = await crud_clients.get(db, id=order.client_id)
    return _order_read(order, client.full_name if client else "")


@router.post("/{order_id}/start", response_model=OrderRead, operation_id="start_order_production")
async def start_order_production(
    db: SessionDep, current_user: ManagerUser, order_id: int, request: Request
) -> OrderRead:
    """Manager 'Ishlab chiqarishga uzatish' (TZ 6.4.2): TECHNICAL_REVIEW → PRODUCTION."""
    order = await _get_order(db, order_id)
    if order.status != OrderStatus.TECHNICAL_REVIEW:
        raise ForbiddenException("Buyurtma texnolog tasdig'idan o'tgan bo'lishi kerak.")

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
    # (event published after commit below)
    log_action(
        db,
        module="orders",
        action="production_started",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"Buyurtma ishlab chiqarishga uzatildi: {order.number}",
        ip=_client_ip(request),
    )
    await db.commit()
    await db.refresh(order)
    await ws_manager.publish("order.started", {"order_id": order.id, "order_number": order.number})
    client = await crud_clients.get(db, id=order.client_id)
    return _order_read(order, client.full_name if client else "")


@router.post("/{order_id}/upload", response_model=Message, operation_id="upload_order_project")
async def upload_order_project(
    db: SessionDep, current_user: TexnologUser, order_id: int, file: UploadFile, request: Request
) -> Message:
    """Texnolog uploads the .project file (TZ 6.3). Exactly ONE file per order; re-upload
    replaces all previous parse results and is allowed only before PRODUCTION."""
    order = await _get_order(db, order_id)
    if order.status not in _EDITABLE_STATUSES:
        raise ForbiddenException("Fayl faqat ishlab chiqarishga uzatilgunga qadar yuklanadi.")
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

    upload_root = Path(settings.UPLOAD_DIR).resolve()
    await wipe_previous_parse(db, order, upload_root)
    try:
        summary = await ingest_project(db, order, project, content, file.filename or "project.project", upload_root)
    except ParseError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from None

    log_action(
        db,
        module="orders",
        action="project_uploaded",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"Project fayl yuklandi: {file.filename}",
        meta=summary,
        ip=_client_ip(request),
    )
    await db.commit()
    return Message(
        message=(
            f"Fayl qabul qilindi: {summary['products']} mahsulot, {summary['parts']} detal, "
            f"{summary['instances']} nusxa."
        )
    )


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
    full_path = Path(settings.UPLOAD_DIR).resolve() / row.path
    if not full_path.is_file():
        raise NotFoundException("Fayl diskda topilmadi.")
    media_type = "application/xml" if row.kind in (FileKind.PROJECT, FileKind.SCX) else "application/octet-stream"
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
