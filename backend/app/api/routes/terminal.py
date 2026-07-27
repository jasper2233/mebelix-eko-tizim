"""Operator terminal API (TZ 8): context, badge sessions, task queue, ARRA cut map, files."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import case, func, select

from app.api.deps import SessionDep, require_roles
from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.core.ws import ws_manager
from app.crud import crud_orders, log_action
from app.models import (
    Employee,
    Machine,
    Order,
    OrderFile,
    Part,
    PartInstance,
    PartRoute,
    Post,
    Product,
    Scan,
    WorkSession,
)
from app.models.enums import (
    POST_ROLES,
    EmployeeStatus,
    OrderPriority,
    OrderStatus,
    PostCode,
    SessionStatus,
    UserRole,
)
from app.models.user import User
from app.schemas.common import Message
from app.schemas.terminal import (
    BadgeStart,
    CutmapInstanceState,
    CutmapState,
    SessionRead,
    TaskRow,
    TerminalContext,
)
from app.services.scanning import ScanRejected, active_session, latest_active_session, resolve_terminal

router = APIRouter(prefix="/terminal", tags=["terminal"])

TerminalUser = Annotated[User, Depends(require_roles(UserRole.TERMINAL, *POST_ROLES))]


async def _terminal_ctx(db: SessionDep, user: TerminalUser) -> tuple[Machine, Post]:
    """Stanok + post. Faqat shu ikkisiga muhtoj route'larga qo'yiladi — router darajasida EMAS:
    yorliq/fayl route'lari stanoksiz terminal foydalanuvchisi uchun ham ishlashi kerak."""
    try:
        return await resolve_terminal(db, user)
    except ScanRejected as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from None


TerminalCtx = Annotated[tuple[Machine, Post], Depends(_terminal_ctx)]


def _session_read(session: WorkSession, employee_name: str) -> SessionRead:
    item = SessionRead.model_validate(session)
    item.employee_name = employee_name
    return item


@router.get("/context", response_model=TerminalContext, operation_id="read_terminal_context")
async def read_terminal_context(db: SessionDep, user: TerminalUser, ctx: TerminalCtx) -> TerminalContext:
    machine, post = ctx
    out = TerminalContext(
        machine_id=machine.id,
        machine_name=machine.name,
        post_id=post.id,
        post_code=post.code,
        post_name=post.name,
    )
    session: WorkSession | None
    if UserRole(user.role) in POST_ROLES:
        # Operator role: login is the shift — session opens automatically, no badge.
        session = await active_session(db, user, machine)
        await db.commit()
        await db.refresh(session)
    else:
        session = await latest_active_session(db, machine.id)
    if session is not None:
        employee = await db.get(Employee, session.employee_id)
        out.session = _session_read(session, employee.full_name if employee else "")
    return out


@router.post("/session", response_model=SessionRead, operation_id="start_terminal_session")
async def start_terminal_session(
    db: SessionDep, user: TerminalUser, ctx: TerminalCtx, body: BadgeStart, request: Request
) -> SessionRead:
    """Badge scan opens the shift (TZ 8.2.2)."""
    machine, post = ctx
    employee = (
        await db.execute(
            select(Employee).where(
                Employee.badge_id == body.badge_id.strip(),
                Employee.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if employee is None:
        raise HTTPException(status_code=422, detail={"code": "E006", "message": "Beyjik topilmadi."})
    if employee.status != EmployeeStatus.ACTIVE:
        raise HTTPException(
            status_code=422, detail={"code": "E006", "message": "Beyjik nofaol. Adminga murojaat qiling."}
        )
    if post.id not in employee.assigned_post_ids:
        raise HTTPException(
            status_code=422,
            detail={"code": "E006", "message": f"{employee.full_name} bu postda ishlay olmaydi ({post.name})."},
        )

    # One active session per terminal: a new badge closes the previous shift.
    previous = await latest_active_session(db, machine.id)
    if previous is not None:
        previous.status = SessionStatus.ENDED
        previous.ended_at = datetime.now(UTC)

    session = WorkSession(employee_id=employee.id, user_id=user.id, machine_id=machine.id, post_id=post.id)
    db.add(session)
    await db.flush()
    log_action(
        db,
        module="sessions",
        action="started",
        user_id=user.id,
        employee_id=employee.id,
        entity_type="session",
        entity_id=session.id,
        message=f"Smena boshlandi: {employee.full_name} — {machine.name}",
        ip=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(session)
    await ws_manager.publish(
        "session.started",
        {"session_id": session.id, "employee": employee.full_name, "machine_id": machine.id, "post_id": post.id},
    )
    return _session_read(session, employee.full_name)


@router.post("/session/end", response_model=Message, operation_id="end_terminal_session")
async def end_terminal_session(db: SessionDep, user: TerminalUser, ctx: TerminalCtx, request: Request) -> Message:
    machine, _post = ctx
    session = await latest_active_session(db, machine.id)
    if session is None:
        raise NotFoundException("Aktiv sessiya yo'q.")
    session.status = SessionStatus.ENDED
    session.ended_at = datetime.now(UTC)
    log_action(
        db,
        module="sessions",
        action="ended",
        user_id=user.id,
        employee_id=session.employee_id,
        entity_type="session",
        entity_id=session.id,
        ip=request.client.host if request.client else None,
    )
    await db.commit()
    await ws_manager.publish("session.ended", {"session_id": session.id, "machine_id": machine.id})
    return Message(message="Sessiya yakunlandi.")


@router.get("/tasks", response_model=list[TaskRow], operation_id="read_terminal_tasks")
async def read_terminal_tasks(db: SessionDep, ctx: TerminalCtx) -> list[TaskRow]:
    """NAVBATDAGI VAZIFALAR (TZ 8.3.2): deadline order, QOLDIQ > 0, this post/machine only."""
    machine, post = ctx
    rows = (
        await db.execute(
            select(PartRoute, Part, Order, Product.code)
            .join(Part, Part.id == PartRoute.part_id)
            .join(Order, Order.id == PartRoute.order_id)
            .join(Product, Product.id == Part.product_id)
            .where(
                PartRoute.post_id == post.id,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
                PartRoute.total_done < PartRoute.total_required,
                Order.status == OrderStatus.PRODUCTION,
                Order.is_deleted == False,  # noqa: E712
                (PartRoute.machine_id == machine.id) | (PartRoute.machine_id.is_(None)),
            )
            .order_by(Order.deadline.asc().nulls_last(), Order.id, Part.code)
        )
    ).all()

    return [
        TaskRow(
            part_id=part.id,
            order_id=order.id,
            order_number=order.number,
            deadline=order.deadline,
            code=f"{product_code}_{part.code}",
            name=part.name,
            length=part.length,
            width=part.width,
            thickness=part.thickness,
            qoldiq=route.total_required - route.total_done,
            total=route.total_required,
            edges=part.edges,
        )
        for route, part, order, product_code in rows
    ]


@router.get("/orders", response_model=list[dict], operation_id="read_terminal_orders")
async def read_terminal_orders(db: SessionDep, ctx: TerminalCtx) -> list[dict]:
    """Active orders relevant to this terminal (for the ARRA map order picker)."""
    machine, post = ctx
    # SHOSHILINCH tepada tursin: prioritet birinchi, keyin deadline (nulls oxirida)
    priority_rank = case(
        (Order.priority == OrderPriority.URGENT, 0),
        (Order.priority == OrderPriority.HIGH, 1),
        (Order.priority == OrderPriority.MEDIUM, 2),
        else_=3,
    )
    rows = (
        await db.execute(
            select(
                Order,
                func.sum(PartRoute.total_done),
                func.sum(PartRoute.total_required),
            )
            .join(PartRoute, PartRoute.order_id == Order.id)
            .where(
                Order.status == OrderStatus.PRODUCTION,
                Order.is_deleted == False,  # noqa: E712
                PartRoute.post_id == post.id,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
                # boshqa stanokka biriktirilgan yo'nalishlar bu terminalda ko'rinmasin (/tasks bilan bir xil)
                (PartRoute.machine_id == machine.id) | (PartRoute.machine_id.is_(None)),
            )
            .group_by(Order.id)
            .order_by(priority_rank, Order.deadline.asc().nulls_last(), Order.id)
        )
    ).all()
    return [
        {
            "id": o.id,
            "number": o.number,
            "project_name": o.project_name,
            "deadline": o.deadline,
            "priority": o.priority,
            "done": int(done or 0),
            "total": int(total or 0),
            # karta uchun: arrachi plita bo'yicha partiyalab kesadi
            "materials": [m["name"] for m in o.material_usage if m.get("kind") == "sheet"],
            "sheets_total": sum(
                int(s.get("mult") or 1) for mat in (o.cutmap or {}).get("materials", []) for s in mat.get("sheets", [])
            ),
            "has_cutmap": o.cutmap is not None,
        }
        for o, done, total in rows
    ]


@router.get("/orders/{order_id}/cutmap", response_model=CutmapState, operation_id="read_terminal_cutmap")
async def read_terminal_cutmap(db: SessionDep, ctx: TerminalCtx, order_id: int) -> CutmapState:
    """ARRA cut-map screen (TZ 7.1.7). Cell state survives terminal restarts — it lives here."""
    _machine, post = ctx
    if post.code != PostCode.ARRA:
        raise HTTPException(status_code=403, detail="Kesish xaritasi faqat ARRA postida ko'rsatiladi.")

    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)
    return await build_cutmap_state(db, order, post.id)


async def build_cutmap_state(db: SessionDep, order: Order, arra_post_id: int) -> CutmapState:
    """Shared by the ARRA terminal (7.1.7) and the admin panel view (10.3)."""
    instances = (
        (
            await db.execute(
                select(PartInstance).where(
                    PartInstance.order_id == order.id,
                    PartInstance.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    done_ids = set(
        (
            await db.execute(
                select(Scan.instance_id).where(
                    Scan.order_id == order.id,
                    Scan.post_id == arra_post_id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    return CutmapState(
        order_id=order.id,
        order_number=order.number,
        model=order.cutmap,
        instances=[
            CutmapInstanceState(
                instance_id=i.id,
                instance_no=i.instance_no,
                qr_text=i.qr_text,
                pattern_no=i.pattern_no,
                cell_index=i.cell_index,
                done=i.id in done_ids,
                label_printed_at=i.label_printed_at,
            )
            for i in instances
        ],
    )


@router.post("/labels/{instance_id}", response_model=Message, operation_id="print_instance_label")
async def print_instance_label(db: SessionDep, user: TerminalUser, instance_id: int) -> Message:
    """YORLIQ CHOP ETISH (TZ 7.1.4): on-demand, per selected cell. Queued to the bridge-agent."""
    instance = await db.get(PartInstance, instance_id)
    if instance is None or instance.is_deleted:
        raise NotFoundException("Nusxa topilmadi.")
    instance.label_printed_at = datetime.now(UTC)
    await db.commit()

    from app.core.utils import queue

    if queue.pool is not None:
        await queue.pool.enqueue_job("print_label", instance_id)
    await ws_manager.publish("label.printed", {"instance_id": instance_id, "qr_text": instance.qr_text})
    return Message(message=f"Yorliq chop etishga yuborildi: {instance.qr_text}")


@router.get("/labels/{instance_id}.png", operation_id="render_instance_label")
async def render_instance_label(db: SessionDep, user: TerminalUser, instance_id: int) -> Response:
    """Yorliqning PNG ko'rinishi — brauzerdan istalgan printerga chop etish uchun (GoDEX shart emas)."""
    from app.services.labels import load_label_data, render_label_png

    data = await load_label_data(db, instance_id)
    if data is None:
        raise NotFoundException("Nusxa topilmadi.")
    return Response(content=render_label_png(data), media_type="image/png")


@router.get("/files/{file_id}", operation_id="download_terminal_file")
async def download_terminal_file(db: SessionDep, user: TerminalUser, file_id: int) -> FileResponse:
    """SCX download at the machine browser (TZ 12.5) — served fresh on every scan."""
    row = (
        await db.execute(
            select(OrderFile).where(OrderFile.id == file_id, OrderFile.is_deleted == False)  # noqa: E712
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundException("Fayl topilmadi.")
    full_path = Path(settings.UPLOAD_DIR).resolve() / row.path
    if not full_path.is_file():
        raise NotFoundException("Fayl diskda topilmadi.")
    return FileResponse(full_path, filename=row.filename, media_type="application/xml")
