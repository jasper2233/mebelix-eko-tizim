"""Operator terminal API (TZ 8): context, badge sessions, task queue, ARRA cut map, files."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import case, func, select

from app.api.deps import SessionDep, client_ip, require_roles
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
    FileKind,
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
    KromkaInstance,
    KromkaOrderState,
    KromkaPartRow,
    SessionRead,
    TaskRow,
    TerminalContext,
)
from app.services.scanning import (
    ScanRejected,
    active_session,
    finalize_scan,
    latest_active_session,
    record_scan_at,
    resolve_terminal,
)

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
        ip=client_ip(request),
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
        ip=client_ip(request),
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

    # Agregatlar faqat ro'yxatdagi buyurtmalar bo'yicha — filtrisiz butun bazadagi
    # BARCHA nusxa/skan tarixi har so'rovda qayta hisoblanardi
    order_ids = [o.id for o, *_ in rows]

    # ARRA'da "bajarildi" = chek chiqarilgan YOKI skan qilingan nusxa (kartadagi
    # foiz xarita bilan bir xil o'lchov bo'lsin). Boshqa postlarda faqat skan.
    printed_by_order: dict[int, int] = {}
    if post.code == PostCode.ARRA and order_ids:
        printed_by_order = dict(
            (
                await db.execute(
                    select(PartInstance.order_id, func.count(func.distinct(PartInstance.id)))
                    .outerjoin(
                        Scan,
                        (Scan.instance_id == PartInstance.id)
                        & (Scan.post_id == post.id)
                        & (Scan.is_cancelled == False)  # noqa: E712
                        & (Scan.is_deleted == False),  # noqa: E712
                    )
                    .where(
                        PartInstance.order_id.in_(order_ids),
                        PartInstance.is_deleted == False,  # noqa: E712
                        (PartInstance.label_printed_at.isnot(None)) | (Scan.id.isnot(None)),
                    )
                    .group_by(PartInstance.order_id)
                )
            )
            .tuples()
            .all()
        )
    # KROMKA kartasida hisob DETAL bo'yicha (tomon emas): nusxaning hamma tomoni
    # skan qilingan bo'lsa — qilingan; jami = kromkali nusxalar soni
    kromka_counts: dict[int, tuple[int, int]] = {}
    if post.code == PostCode.KROMKA and order_ids:
        scans_sq = (
            select(Scan.instance_id, func.count(Scan.id).label("cnt"))
            .where(
                Scan.order_id.in_(order_ids),
                Scan.post_id == post.id,
                Scan.is_cancelled == False,  # noqa: E712
                Scan.is_deleted == False,  # noqa: E712
            )
            .group_by(Scan.instance_id)
            .subquery()
        )
        kromka_counts = {
            oid: (int(d or 0), int(t or 0))
            for oid, t, d in (
                await db.execute(
                    select(
                        PartInstance.order_id,
                        func.count(PartInstance.id),
                        func.sum(case((func.coalesce(scans_sq.c.cnt, 0) >= PartRoute.per_instance, 1), else_=0)),
                    )
                    .join(
                        PartRoute,
                        (PartRoute.part_id == PartInstance.part_id)
                        & (PartRoute.post_id == post.id)
                        & (PartRoute.is_enabled == True)  # noqa: E712
                        & (PartRoute.is_deleted == False),  # noqa: E712
                    )
                    .outerjoin(scans_sq, scans_sq.c.instance_id == PartInstance.id)
                    .where(
                        PartInstance.order_id.in_(order_ids),
                        PartInstance.is_deleted == False,  # noqa: E712
                    )
                    .group_by(PartInstance.order_id)
                )
            ).all()
        }
    result = []
    for o, done, total in rows:
        done_val = printed_by_order.get(o.id, 0) if post.code == PostCode.ARRA else int(done or 0)
        total_val = int(total or 0)
        if post.code == PostCode.KROMKA:
            done_val, total_val = kromka_counts.get(o.id, (0, 0))
        # Hamma detali chiqarilgan proyekt arrachi ro'yxatini band qilmasin —
        # kesish tugagan, qolgani keyingi postlarning ishi
        if post.code == PostCode.ARRA and total_val > 0 and done_val >= total_val:
            continue
        result.append(
            {
                "id": o.id,
                "number": o.number,
                "project_name": o.project_name,
                "deadline": o.deadline,
                "priority": o.priority,
                "done": done_val,
                "total": total_val,
                # karta uchun: arrachi plita bo'yicha partiyalab kesadi
                "materials": [m["name"] for m in o.material_usage if m.get("kind") == "sheet"],
                "sheets_total": sum(
                    int(s.get("mult") or 1)
                    for mat in (o.cutmap or {}).get("materials", [])
                    for s in mat.get("sheets", [])
                ),
                "has_cutmap": o.cutmap is not None,
            }
        )
    return result


@router.get("/qr/{qr_text}/order", response_model=dict, operation_id="resolve_terminal_qr")
async def resolve_terminal_qr(db: SessionDep, user: TerminalUser, qr_text: str) -> dict:
    """Proyekt ro'yxatida turib QR skan qilinsa — qaysi buyurtmaga tegishli ekanini topadi
    (terminal o'sha proyekt sahifasini ochib yuboradi)."""
    qr = qr_text.strip()
    row = None
    # Eski yorliqlar: migratsiyadan oldin yagona nusxa ham `_1` bilan chop etilgan
    for cand in [qr, qr[:-2]] if qr.endswith("_1") else [qr]:
        row = (
            await db.execute(
                select(PartInstance.order_id, Order.number)
                .join(Order, Order.id == PartInstance.order_id)
                .where(
                    PartInstance.qr_text == cand,
                    PartInstance.is_deleted == False,  # noqa: E712
                    Order.is_deleted == False,  # noqa: E712
                    Order.status == OrderStatus.PRODUCTION,
                )
                .order_by(Order.id.desc())
                .limit(1)
            )
        ).first()
        if row is not None:
            break
    if row is None:
        raise NotFoundException("Bu QR uchun aktiv buyurtma topilmadi.")
    return {"order_id": row.order_id, "order_number": row.number}


@router.get("/orders/{order_id}/kromka", response_model=KromkaOrderState, operation_id="read_terminal_kromka")
async def read_terminal_kromka(db: SessionDep, ctx: TerminalCtx, order_id: int) -> KromkaOrderState:
    """KROMKA/OVAL sahifasi: buyurtmaning shu postdagi detallari, har nusxada tomon-progress
    (OVAL'da 0/1) va arradan o'tganlik (chek chiqarilgan yoki ARRA skan bor)."""
    machine, post = ctx
    if post.code not in (PostCode.KROMKA, PostCode.OVAL):
        raise HTTPException(status_code=403, detail="Bu sahifa faqat KROMKA yoki OVAL postida ko'rsatiladi.")

    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)

    rows = (
        await db.execute(
            select(PartRoute, Part, Product.code)
            .join(Part, Part.id == PartRoute.part_id)
            .join(Product, Product.id == Part.product_id)
            .where(
                PartRoute.order_id == order.id,
                PartRoute.post_id == post.id,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
                (PartRoute.machine_id == machine.id) | (PartRoute.machine_id.is_(None)),
            )
            .order_by(Part.code)
        )
    ).all()

    instances = (
        (
            await db.execute(
                select(PartInstance)
                .where(
                    PartInstance.order_id == order.id,
                    PartInstance.is_deleted == False,  # noqa: E712
                )
                .order_by(PartInstance.part_id, PartInstance.instance_no)
            )
        )
        .scalars()
        .all()
    )

    kromka_done: dict[int, int] = dict(
        (
            await db.execute(
                select(Scan.instance_id, func.count(Scan.id))
                .where(
                    Scan.order_id == order.id,
                    Scan.post_id == post.id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .group_by(Scan.instance_id)
            )
        )
        .tuples()
        .all()
    )

    arra_post_id = (
        await db.execute(select(Post.id).where(Post.code == PostCode.ARRA, Post.is_deleted == False))  # noqa: E712
    ).scalar_one_or_none()
    arra_scanned: set[int] = set()
    if arra_post_id is not None:
        arra_scanned = set(
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

    by_part: dict[int, list[PartInstance]] = {}
    for i in instances:
        by_part.setdefault(i.part_id, []).append(i)

    return KromkaOrderState(
        order_id=order.id,
        order_number=order.number,
        parts=[
            KromkaPartRow(
                part_id=part.id,
                code=f"{product_code}_{part.code}",
                name=part.name,
                length=part.length,
                width=part.width,
                thickness=part.thickness,
                sides=route.per_instance,
                edges=part.edges,
                total_done=route.total_done,
                total_required=route.total_required,
                instances=[
                    KromkaInstance(
                        instance_id=i.id,
                        instance_no=i.instance_no,
                        qr_text=i.qr_text,
                        done=int(kromka_done.get(i.id, 0)),
                        arra_passed=i.label_printed_at is not None or i.id in arra_scanned,
                    )
                    for i in by_part.get(part.id, [])
                ],
            )
            for route, part, product_code in rows
        ],
    )


@router.get("/orders/{order_id}/prisadka", response_model=dict, operation_id="read_terminal_prisadka")
async def read_terminal_prisadka(db: SessionDep, ctx: TerminalCtx, order_id: int) -> dict:
    """CNC post sahifasi (PRISADKA/PAZ/ROVER): shu postga tegishli detallar +
    SCX fayllari (stanok kompyuteriga yuklab olish uchun, TZ 12.5). ROVER'da
    jarayon arradan EMAS, roverdan boshlanishi ham mumkin — shunday detallarga
    QR chekni shu sahifadan chiqarish uchun arra_route belgisi ham beriladi."""
    machine, post = ctx
    if post.code not in (PostCode.PRISADKA, PostCode.PAZ, PostCode.ROVER):
        raise HTTPException(status_code=403, detail="Bu sahifa faqat CNC postlarida (PRISADKA/PAZ/ROVER) ko'rsatiladi.")

    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)

    rows = (
        await db.execute(
            select(PartRoute, Part, Product.code)
            .join(Part, Part.id == PartRoute.part_id)
            .join(Product, Product.id == Part.product_id)
            .where(
                PartRoute.order_id == order.id,
                PartRoute.post_id == post.id,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
                (PartRoute.machine_id == machine.id) | (PartRoute.machine_id.is_(None)),
            )
            .order_by(Part.code)
        )
    ).all()

    files_by_part: dict[int, list[dict]] = {}
    for f in (
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
    ):
        if f.part_id is not None:
            files_by_part.setdefault(f.part_id, []).append({"id": f.id, "filename": f.filename})

    # Har nusxaning shu postdagi holati: 2/4 ko'rsatishning o'zi QAYSI nusxalar
    # qolganini aytmaydi — fayl (nomi = nusxa QR'i) yashil/kulrang bo'lib ko'rsatadi
    scan_counts = dict(
        (
            await db.execute(
                select(Scan.instance_id, func.count(Scan.id))
                .where(
                    Scan.order_id == order.id,
                    Scan.post_id == post.id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .group_by(Scan.instance_id)
            )
        )
        .tuples()
        .all()
    )
    insts_by_part: dict[int, list[PartInstance]] = {}
    for inst in (
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
    ):
        insts_by_part.setdefault(inst.part_id, []).append(inst)

    # ROVER'da jarayon arradan boshlanmasligi mumkin: marshrutida ARRA yo'q
    # detalning QR cheki shu sahifadan chiqariladi. ARRA'li detalga bu yerdan
    # chek chiqarish TAQIQ — arra statistikasi ("chek chiqarilgan = kesilgan")
    # buzilardi, chek arrachi tomonidan chiqadi.
    arra_part_ids = {
        pid
        for (pid,) in (
            await db.execute(
                select(PartRoute.part_id)
                .join(Post, Post.id == PartRoute.post_id)
                .where(
                    PartRoute.order_id == order.id,
                    Post.code == PostCode.ARRA,
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                )
            )
        ).all()
    }

    return {
        "order_id": order.id,
        "order_number": order.number,
        "project_name": order.project_name,
        "parts": [
            {
                "part_id": part.id,
                "code": f"{product_code}_{part.code}",
                "name": part.name,
                "length": part.length,
                "width": part.width,
                "thickness": part.thickness,
                "done": route.total_done,
                "total": route.total_required,
                "files": files_by_part.get(part.id, []),
                "arra_route": part.id in arra_part_ids,
                # Skan tugagan nusxalar QR'lari (fayl nomi bilan mos) — UI rang beradi
                "done_qrs": [
                    i.qr_text for i in insts_by_part.get(part.id, []) if scan_counts.get(i.id, 0) >= route.per_instance
                ],
                # Nusxa darajasi: QR chiqarish tugmasi va holat uchun
                "instances": [
                    {
                        "instance_id": i.id,
                        "qr_text": i.qr_text,
                        "label_printed": i.label_printed_at is not None,
                        "done": scan_counts.get(i.id, 0) >= route.per_instance,
                    }
                    for i in sorted(insts_by_part.get(part.id, []), key=lambda i: i.instance_no)
                ],
            }
            for route, part, product_code in rows
        ],
    }


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
    log_action(
        db,
        module="print",
        action="label_sent",
        user_id=user.id,
        entity_type="part_instance",
        entity_id=instance.id,
        message=f"Chek chop etishga yuborildi: {instance.qr_text}",
    )
    await db.commit()

    from app.core.utils import queue

    if queue.pool is not None:
        await queue.pool.enqueue_job("print_label", instance_id)
    await ws_manager.publish("label.printed", {"instance_id": instance_id, "qr_text": instance.qr_text})

    # ROVER oqimi: marshrutida ARRA bo'lmagan detal roverning O'ZIDA kesiladi —
    # chop etish ish bajarildi degani (ARRA'dagi "chek = kesildi" bilan bir xil),
    # alohida skan qadami ortiqcha. Skan yozuvi ham yoziladi: statistika, tablo
    # va ish haqi hisoblari oddiy oqim bilan bir xil qoladi. Rad etilsa (masalan
    # qat'iy tartibda oldingi bosqich tugamagan) chek baribir chiqqan bo'ladi —
    # operator keyin skan bilan yakunlaydi.
    if POST_ROLES.get(UserRole(user.role)) == PostCode.ROVER:
        arra_route = (
            await db.execute(
                select(PartRoute.id)
                .join(Post, Post.id == PartRoute.post_id)
                .where(
                    PartRoute.part_id == instance.part_id,
                    Post.code == PostCode.ARRA,
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                )
            )
        ).first()
        if arra_route is None:
            try:
                machine, post = await resolve_terminal(db, user)
                session = await active_session(db, user, machine)
                outcome = await record_scan_at(
                    db,
                    machine=machine,
                    post=post,
                    session=session,
                    qr_text=instance.qr_text,
                    client_event_id=f"rvprint-{instance.id}",
                )
                await finalize_scan(db, outcome, user_id=user.id, source=" (rover, chop etish bilan)")
            except ScanRejected:
                await db.rollback()

    return Message(message=f"Yorliq chop etishga yuborildi: {instance.qr_text}")


# Bekor qilishga admin webdagi xarita egalari ham kiradi: proyekt ro'yxatdan
# tushib bo'lgach arrachi xaritani ocholmaydi — oxirgi xato chekni texnolog tuzatadi
LabelCancelUser = Annotated[
    User, Depends(require_roles(UserRole.TERMINAL, *POST_ROLES, UserRole.MANAGER, UserRole.TEXNOLOG))
]


@router.delete("/labels/{instance_id}", response_model=Message, operation_id="cancel_instance_label")
async def cancel_instance_label(db: SessionDep, user: LabelCancelUser, instance_id: int) -> Message:
    """Chekni bekor qilish (long press / admin xarita): noto'g'ri chiqarilgan yorliq
    katakni chop etilmagan holatga qaytaradi. Skan qilingan (kesilgan) nusxaga ta'sir qilmaydi."""
    instance = await db.get(PartInstance, instance_id)
    if instance is None or instance.is_deleted:
        raise NotFoundException("Nusxa topilmadi.")
    instance.label_printed_at = None
    log_action(
        db,
        module="print",
        action="label_cancelled",
        user_id=user.id,
        entity_type="part_instance",
        entity_id=instance.id,
        message=f"Chek bekor qilindi: {instance.qr_text}",
    )
    await db.commit()
    await ws_manager.publish("label.cancelled", {"instance_id": instance_id, "qr_text": instance.qr_text})
    return Message(message=f"Yorliq bekor qilindi: {instance.qr_text}")


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
