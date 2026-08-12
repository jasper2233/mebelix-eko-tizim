"""Operator terminal API (TZ 8): context, badge sessions, task queue, ARRA cut map, files."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import Row, case, func, select, update

from app.api.deps import SessionDep, client_ip, require_roles
from app.core.config import upload_root
from app.core.exceptions import ForbiddenException, NotFoundException
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
    PostQueueRow,
    PostQueueState,
    PrisadkaFile,
    PrisadkaInstance,
    PrisadkaOrderState,
    PrisadkaPartRow,
    QrOrderRef,
    SessionRead,
    TerminalContext,
    TerminalOrderCard,
)
from app.services.scanning import (
    ScanRejected,
    active_session,
    finalize_scan,
    latest_active_session,
    record_scan,
    resolve_terminal,
)

router = APIRouter(prefix="/terminal", tags=["terminal"])

TerminalUser = Annotated[User, Depends(require_roles(UserRole.TERMINAL, *POST_ROLES))]


def _scan_error(code: str, message: str) -> HTTPException:
    """TZ 8.5 xato dialogi shakli: {code, message} — ScanRejected bilan bir xil JSON payload."""
    return HTTPException(status_code=422, detail={"code": code, "message": message})


async def _terminal_ctx(db: SessionDep, user: TerminalUser) -> tuple[Machine, Post]:
    """Stanok + post. Faqat shu ikkisiga muhtoj route'larga qo'yiladi — router darajasida EMAS:
    yorliq/fayl route'lari stanoksiz terminal foydalanuvchisi uchun ham ishlashi kerak."""
    try:
        return await resolve_terminal(db, user)
    except ScanRejected as exc:
        raise _scan_error(exc.code, exc.message) from None


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
        raise _scan_error("E006", "Beyjik topilmadi.")
    if employee.status != EmployeeStatus.ACTIVE:
        raise _scan_error("E006", "Beyjik nofaol. Adminga murojaat qiling.")
    if post.id not in employee.assigned_post_ids:
        raise _scan_error("E006", f"{employee.full_name} bu postda ishlay olmaydi ({post.name}).")

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


def _own_sheets(order: Order, own_nos: set[int] | None) -> int:
    """Kartadagi "N list" — SHU postniki. `mult` (bir naqsh necha marta kesiladi) sanaladi.

    `own_nos=None` — post kesish posti emas (kromka, prisadka...), hamma list sanaladi.
    """
    return sum(
        int(s.get("mult") or 1)
        for mat in (order.cutmap or {}).get("materials", [])
        for s in mat.get("sheets", [])
        if own_nos is None or s.get("no") in own_nos
    )


@router.get("/orders", response_model=list[TerminalOrderCard], operation_id="read_terminal_orders")
async def read_terminal_orders(db: SessionDep, ctx: TerminalCtx) -> list[TerminalOrderCard]:
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
                    # Faqat ARRA marshruti BOR detallar: aks holda arradan o'tmaydigan
                    # detalning cheki (masalan roverchi o'zi chiqargani) arra hisobini
                    # shishirib, jami'dan oshib ketardi va proyekt arrachi ro'yxatidan
                    # yo'qolardi — listlar hali kesilmagan bo'lsa ham.
                    .join(
                        PartRoute,
                        (PartRoute.part_id == PartInstance.part_id)
                        & (PartRoute.post_id == post.id)
                        & (PartRoute.is_enabled == True)  # noqa: E712
                        & (PartRoute.is_deleted == False),  # noqa: E712
                    )
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
    # Kartadagi "N list" faqat SHU postnikini sanashi kerak. Giyotina kesimi listni
    # chetdan chetgacha kesadi, ya'ni listning egasi bitta: yo arra (detallar
    # marshrutida ARRA qadami bor), yo rover (butun listni frezer kesadi).
    # Ilgari hamma list sanalardi — arrachi kartada "7 list" ko'rar, o'ziniki esa
    # 3 ta bo'lar va reja noto'g'ri chamalanardi.
    own_sheet_nos: dict[int, set[int]] | None = None
    if post.code in (PostCode.ARRA, PostCode.ROVER) and order_ids:
        arra_parts = (
            select(PartRoute.part_id)
            .join(Post, Post.id == PartRoute.post_id)
            .where(
                PartRoute.order_id.in_(order_ids),
                Post.code == PostCode.ARRA,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
            )
            .scalar_subquery()
        )
        seen: dict[int, dict[int, set[bool]]] = {}
        for oid, pattern_no, has_arra in (
            await db.execute(
                select(
                    PartInstance.order_id,
                    PartInstance.pattern_no,
                    PartInstance.part_id.in_(arra_parts),
                ).where(
                    PartInstance.order_id.in_(order_ids),
                    PartInstance.pattern_no.isnot(None),
                    PartInstance.is_deleted == False,  # noqa: E712
                )
            )
        ).all():
            seen.setdefault(oid, {}).setdefault(pattern_no, set()).add(bool(has_arra))
        mine = post.code == PostCode.ARRA
        own_sheet_nos = {oid: {no for no, flags in sheets.items() if flags == {mine}} for oid, sheets in seen.items()}

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
        # Kromka marshrutda ikki marta bo'lishi mumkin (kromka -> prisadka -> kromka):
        # detalga to'g'ridan-to'g'ri JOIN qilinsa nusxa ikki marta sanalardi. Shuning
        # uchun avval qadamlar detal bo'yicha yig'iladi — bitta detal, bitta qator.
        need_sq = (
            select(PartRoute.part_id.label("part_id"), func.sum(PartRoute.per_instance).label("need"))
            .where(
                PartRoute.post_id == post.id,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
            )
            .group_by(PartRoute.part_id)
            .subquery()
        )
        kromka_counts = {
            oid: (int(d or 0), int(t or 0))
            for oid, t, d in (
                await db.execute(
                    select(
                        PartInstance.order_id,
                        func.count(PartInstance.id),
                        func.sum(case((func.coalesce(scans_sq.c.cnt, 0) >= need_sq.c.need, 1), else_=0)),
                    )
                    .join(need_sq, need_sq.c.part_id == PartInstance.part_id)
                    .outerjoin(scans_sq, scans_sq.c.instance_id == PartInstance.id)
                    .where(
                        PartInstance.order_id.in_(order_ids),
                        PartInstance.is_deleted == False,  # noqa: E712
                    )
                    .group_by(PartInstance.order_id)
                )
            ).all()
        }
    result: list[TerminalOrderCard] = []
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
            TerminalOrderCard(
                id=o.id,
                number=o.number,
                project_name=o.project_name,
                deadline=o.deadline,
                priority=o.priority,
                done=done_val,
                total=total_val,
                # karta uchun: arrachi plita bo'yicha partiyalab kesadi
                materials=[m["name"] for m in o.material_usage if m.get("kind") == "sheet"],
                sheets_total=_own_sheets(o, own_sheet_nos.get(o.id) if own_sheet_nos is not None else None),
                has_cutmap=o.cutmap is not None,
            )
        )
    return result


@router.get("/qr/{qr_text}/order", response_model=QrOrderRef, operation_id="resolve_terminal_qr")
async def resolve_terminal_qr(db: SessionDep, user: TerminalUser, qr_text: str) -> QrOrderRef:
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
    return QrOrderRef(order_id=row.order_id, order_number=row.number)


async def _post_route_rows(
    db: SessionDep, order_id: int, post_id: int, machine_id: int
) -> Sequence[Row[tuple[PartRoute, Part, str]]]:
    """Buyurtmaning shu post(+stanok)dagi marshrutlari: (PartRoute, Part, product_code) qatorlar.
    KROMKA va CNC sahifalari bir xil so'rovni ishlatadi."""
    return (
        await db.execute(
            select(PartRoute, Part, Product.code)
            .join(Part, Part.id == PartRoute.part_id)
            .join(Product, Product.id == Part.product_id)
            .where(
                PartRoute.order_id == order_id,
                PartRoute.post_id == post_id,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
                (PartRoute.machine_id == machine_id) | (PartRoute.machine_id.is_(None)),
            )
            .order_by(Part.code, PartRoute.seq)
        )
    ).all()


async def _post_scan_counts(db: SessionDep, order_id: int, post_id: int) -> dict[tuple[int, int], int]:
    """Har nusxaning shu postdagi haqiqiy skanlari QADAM bo'yicha: {(instance_id, route_id): count}.

    Kalit qadam (route_id) — post emas: bitta post marshrutda ikki marta bo'lsa
    (kromka -> prisadka -> yana kromka) birinchi o'tishning skanlari ikkinchisini
    ham "bajarildi" qilib ko'rsatardi va operator qaytib kelmasdi."""
    rows = (
        (
            await db.execute(
                select(Scan.instance_id, Scan.route_id, func.count(Scan.id))
                .where(
                    Scan.order_id == order_id,
                    Scan.post_id == post_id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .group_by(Scan.instance_id, Scan.route_id)
            )
        )
        .tuples()
        .all()
    )
    return {(instance_id, route_id): count for instance_id, route_id, count in rows}


async def _order_instances_by_part(db: SessionDep, order_id: int) -> dict[int, list[PartInstance]]:
    """Buyurtmaning jonli nusxalari detal bo'yicha guruhlangan, instance_no tartibida."""
    by_part: dict[int, list[PartInstance]] = {}
    for inst in (
        (
            await db.execute(
                select(PartInstance)
                .where(
                    PartInstance.order_id == order_id,
                    PartInstance.is_deleted == False,  # noqa: E712
                )
                .order_by(PartInstance.part_id, PartInstance.instance_no)
            )
        )
        .scalars()
        .all()
    ):
        by_part.setdefault(inst.part_id, []).append(inst)
    return by_part


@router.get("/orders/{order_id}/kromka", response_model=KromkaOrderState, operation_id="read_terminal_kromka")
async def read_terminal_kromka(db: SessionDep, ctx: TerminalCtx, order_id: int) -> KromkaOrderState:
    """KROMKA/OVAL sahifasi: buyurtmaning shu postdagi detallari, har nusxada tomon-progress
    (OVAL'da 0/1) va arradan o'tganlik (chek chiqarilgan yoki ARRA skan bor)."""
    machine, post = ctx
    if post.code not in (PostCode.KROMKA, PostCode.OVAL):
        raise ForbiddenException("Bu sahifa faqat KROMKA yoki OVAL postida ko'rsatiladi.")

    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)

    rows = await _post_route_rows(db, order.id, post.id, machine.id)
    kromka_done = await _post_scan_counts(db, order.id, post.id)

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

    by_part = await _order_instances_by_part(db, order.id)

    return KromkaOrderState(
        order_id=order.id,
        order_number=order.number,
        parts=[
            KromkaPartRow(
                part_id=part.id,
                route_id=route.id,
                code=f"{product_code}_{part.code}",
                name=part.name,
                length=part.length,
                width=part.width,
                thickness=part.thickness,
                sides=route.per_instance,
                edges=part.edges,
                process_code=route.process_code,
                total_done=route.total_done,
                total_required=route.total_required,
                instances=[
                    KromkaInstance(
                        instance_id=i.id,
                        instance_no=i.instance_no,
                        qr_text=i.qr_text,
                        done=int(kromka_done.get((i.id, route.id), 0)),
                        arra_passed=i.label_printed_at is not None or i.id in arra_scanned,
                    )
                    for i in by_part.get(part.id, [])
                ],
            )
            for route, part, product_code in rows
        ],
    )


@router.get("/orders/{order_id}/prisadka", response_model=PrisadkaOrderState, operation_id="read_terminal_prisadka")
async def read_terminal_prisadka(db: SessionDep, ctx: TerminalCtx, order_id: int) -> PrisadkaOrderState:
    """CNC post sahifasi (PRISADKA/ROVER): shu postga tegishli detallar +
    SCX fayllari (stanok kompyuteriga yuklab olish uchun, TZ 12.5). ROVER'da
    jarayon arradan EMAS, roverdan boshlanishi ham mumkin — shunday detallarga
    QR chekni shu sahifadan chiqarish uchun arra_route belgisi ham beriladi."""
    machine, post = ctx
    if post.code not in (PostCode.PRISADKA, PostCode.ROVER):
        raise ForbiddenException("Bu sahifa faqat CNC postlarida (PRISADKA/ROVER) ko'rsatiladi.")

    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)

    rows = await _post_route_rows(db, order.id, post.id, machine.id)

    files_by_part: dict[int, list[PrisadkaFile]] = {}
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
            files_by_part.setdefault(f.part_id, []).append(PrisadkaFile(id=f.id, filename=f.filename))

    # Har nusxaning shu postdagi holati: 2/4 ko'rsatishning o'zi QAYSI nusxalar
    # qolganini aytmaydi — fayl (nomi = nusxa QR'i) yashil/kulrang bo'lib ko'rsatadi
    scan_counts = await _post_scan_counts(db, order.id, post.id)
    insts_by_part = await _order_instances_by_part(db, order.id)

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

    return PrisadkaOrderState(
        order_id=order.id,
        order_number=order.number,
        project_name=order.project_name,
        parts=[
            PrisadkaPartRow(
                part_id=part.id,
                route_id=route.id,
                code=f"{product_code}_{part.code}",
                name=part.name,
                length=part.length,
                width=part.width,
                thickness=part.thickness,
                done=route.total_done,
                total=route.total_required,
                files=files_by_part.get(part.id, []),
                arra_route=part.id in arra_part_ids,
                # Skan tugagan nusxalar QR'lari (fayl nomi bilan mos) — UI rang beradi
                done_qrs=[
                    i.qr_text
                    for i in insts_by_part.get(part.id, [])
                    if scan_counts.get((i.id, route.id), 0) >= route.per_instance
                ],
                # Nusxa darajasi: QR chiqarish tugmasi va holat uchun (helper instance_no bo'yicha saralaydi)
                instances=[
                    PrisadkaInstance(
                        instance_id=i.id,
                        qr_text=i.qr_text,
                        label_printed=i.label_printed_at is not None,
                        done=scan_counts.get((i.id, route.id), 0) >= route.per_instance,
                    )
                    for i in insts_by_part.get(part.id, [])
                ],
            )
            for route, part, product_code in rows
        ],
    )


@router.get("/orders/{order_id}/cutmap", response_model=CutmapState, operation_id="read_terminal_cutmap")
async def read_terminal_cutmap(db: SessionDep, ctx: TerminalCtx, order_id: int) -> CutmapState:
    """Kesish xaritasi (TZ 7.1.7). Katak holati serverda — terminal qayta yonganda saqlanadi.

    ROVER ham ochadi: marshruti arradan boshlanmagan detallar butun listni frezerda
    kesish bilan chiqadi, ya'ni roverchiga ham joylashuv kerak. Har post O'Z skanlarini
    ko'radi (`done`), listlarni esa frontend `arra_route` bo'yicha ajratadi.
    """
    _machine, post = ctx
    if post.code not in (PostCode.ARRA, PostCode.ROVER):
        raise ForbiddenException("Kesish xaritasi faqat arra va rover postida ko'rsatiladi.")

    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)
    return await build_cutmap_state(db, order, post.id)


@router.get("/orders/{order_id}/queue", response_model=PostQueueState, operation_id="read_terminal_post_queue")
async def read_terminal_post_queue(db: SessionDep, ctx: TerminalCtx, order_id: int) -> PostQueueState:
    """Post navbati NUSXA darajasida (BOYOQ): kelganlar, kutilayotganlar, bajarilganlar.

    Umumiy "Navbatdagi vazifalar" ro'yxati detal darajasida agregat berardi
    ("qoldiq 6/6") — bo'yoqchi qaysi buyumni bo'yaganini undan bilib bo'lmasdi.
    Bu yerda har nusxa alohida qator: skan qilinganda o'sha qator ro'yxatdan
    chiqadi. Material ham beriladi — bo'yoqchi uchun bu RANG.
    """
    from .pachka import instance_stages

    _machine, post = ctx
    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)
    stages = await instance_stages(db, order, post)

    rows = (
        await db.execute(
            select(PartInstance, Part, Product.code, PartRoute)
            .join(Part, Part.id == PartInstance.part_id)
            .join(Product, Product.id == Part.product_id)
            .join(
                PartRoute,
                (PartRoute.part_id == Part.id)
                & (PartRoute.post_id == post.id)
                & (PartRoute.is_enabled == True)  # noqa: E712
                & (PartRoute.is_deleted == False),  # noqa: E712
            )
            .where(
                PartInstance.order_id == order.id,
                PartInstance.is_deleted == False,  # noqa: E712
            )
            .order_by(Product.code, Part.code, PartInstance.instance_no)
        )
    ).all()
    if not rows:
        return PostQueueState(
            order_id=order.id,
            order_number=order.number,
            project_name=order.project_name,
            post_code=post.code,
            rows=[],
        )

    counts = {
        (instance_id, route_id): n
        for instance_id, route_id, n in (
            await db.execute(
                select(Scan.instance_id, Scan.route_id, func.count())
                .where(
                    Scan.order_id == order.id,
                    Scan.post_id == post.id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .group_by(Scan.instance_id, Scan.route_id)
            )
        ).all()
    }
    children: dict[int, list[str]] = {}
    for child, product_code in (
        await db.execute(
            select(Part, Product.code)
            .join(Product, Product.id == Part.product_id)
            .where(
                Part.assembly_parent_id.in_({p.id for _i, p, _pc, _r in rows}),
                Part.is_deleted == False,  # noqa: E712
            )
            .order_by(Part.code)
        )
    ).all():
        assert child.assembly_parent_id is not None
        children.setdefault(child.assembly_parent_id, []).append(f"{product_code}_{child.code} ×{child.count}")

    out = [
        PostQueueRow(
            instance_id=instance.id,
            qr_text=instance.qr_text,
            part_code=f"{product_code}_{part.code}",
            part_name=part.name,
            length=part.length,
            width=part.width,
            thickness=part.thickness,
            material=part.material_name,
            note=part.note,
            process_code=route.process_code,
            ready=stages.get(instance.id, (False, ""))[0],
            stage=stages.get(instance.id, (False, ""))[1],
            done=counts.get((instance.id, route.id), 0) >= route.per_instance,
            assembly=children.get(part.id, []),
        )
        for instance, part, product_code, route in rows
    ]
    # Ishga tayyorlari tepada, bajarilganlari pastda — bo'yoqchi tepadan ishlaydi.
    out.sort(key=lambda r: (r.done, not r.ready, r.part_code, r.qr_text))
    return PostQueueState(
        order_id=order.id,
        order_number=order.number,
        project_name=order.project_name,
        post_code=post.code,
        rows=out,
    )


async def build_cutmap_state(db: SessionDep, order: Order, post_id: int) -> CutmapState:
    """ARRA terminali (7.1.7), ROVER terminali va admin paneldagi ko'rinish (10.3) uchun umumiy.

    `done` — SHU postdagi skanlar bo'yicha: roverchi o'z listida o'zi kesganini ko'radi.
    """
    # Nostandart detallar — marshrutini texnolog qo'lda chizgan. Ular xaritada
    # boshqa rang bilan turadi: arrachi ularni odatdagi detal deb o'ylab qo'ymasin
    # (marshruti arradan boshlanmasligi ham mumkin, o'shanda skan qabul qilinmaydi).
    custom_parts = set(
        (
            await db.execute(
                select(Part.id).where(
                    Part.order_id == order.id,
                    Part.is_custom == True,  # noqa: E712
                    Part.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
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
                    Scan.post_id == post_id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    # Marshrutida ARRA qadami bor detallar — listning egasini shundan aniqlaymiz
    arra_parts = set(
        (
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
                custom=i.part_id in custom_parts,
                arra_route=i.part_id in arra_parts,
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

    # Post aniqlanmasa (stanoksiz terminal) tekshiruvsiz chiqadi — yorliq ko'rish uchun
    try:
        _, print_post = await resolve_terminal(db, user)
    except ScanRejected:
        print_post = None
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
    # Marshruti arradan boshlanmagan detal arrachiga TEGISHLI EMAS: uning listini
    # frezer butunlay o'zi kesadi. Ilgari chek jimgina chiqar, skan esa E001 bilan
    # yutilar edi — katak "kesildi" bo'lib yashil qolar, roverchining chek tugmasi
    # esa `label_printed` sababli yo'qolardi va u qo'lda skanerlashga majbur bo'lardi.
    if print_post is not None and print_post.code == PostCode.ARRA and arra_route is None:
        raise _scan_error("E001", "Bu detal roverda kesiladi — chekni rover terminalidan chiqaring.")

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

    # "CHEK = ISH BAJARILDI" — kesish postlarida chop etishning o'zi bosqichni yopadi.
    # ARRA'da arrachi xaritada katakni bosib chek chiqaradi va alohida skan qilmaydi
    # (xarita ochiqda terminalning skan maydoni ham yashirin). ROVER'da esa marshruti
    # arradan boshlanmagan detal roverning O'ZIDA kesiladi.
    #
    # Skan yozuvisiz `PartRoute.total_done` hech qachon o'smaydi: buyurtma COMPLETED
    # bo'lmaydi va qat'iy tartibda KEYINGI postlarning hammasi E004 bilan rad etiladi.
    # Shuning uchun chop etish shu yerda skan ham yozadi — "bajarildi" ta'rifi
    # hamma joyda (total_done, TABLO, ish haqi, tartib nazorati) bitta bo'lsin.
    # Rad etilsa (oldingi bosqich tugamagan) chek baribir chiqqan bo'ladi — operator
    # keyin qo'lda skan bilan yakunlaydi.
    # Post aniqlanmasa (stanok biriktirilmagan terminal) chek baribir chiqqan
    # bo'ladi — bu yerda faqat avto-skan o'tkazib yuboriladi. Ilgari himoyasiz edi
    # va chop etish so'rovi 500 bilan tugardi.
    if print_post is None:
        return Message(message=f"Chek chop etishga yuborildi: {instance.qr_text}")
    # ARRA'da doim; ROVER'da esa faqat arradan o'tmaydigan detal uchun (qolganini arrachi kesgan)
    cut_by_print = print_post.code == PostCode.ARRA or (print_post.code == PostCode.ROVER and arra_route is None)
    if cut_by_print:
        try:
            # Har chop etish ALOHIDA hodisa: `cutprint-{id}` doimiy bo'lganda
            # chek bekor qilinib qayta chiqarilsa, idempotentlik tekshiruvi eski
            # (bekor qilingan) qatorni topib `duplicate` qaytarardi — yangi skan
            # yozilmas, `total_done` o'smas, holat "Bajarilmagan" bo'lib qolardi.
            outcome = await record_scan(
                db,
                user=user,
                qr_text=instance.qr_text,
                client_event_id=f"cutprint-{instance.id}-{int(datetime.now(UTC).timestamp())}",
            )
            await finalize_scan(db, outcome, user_id=user.id, source=" (chek chiqarish bilan)")
        except ScanRejected:
            await db.rollback()

    return Message(message=f"Chek chop etishga yuborildi: {instance.qr_text}")


# Bekor qilishga admin webdagi xarita egalari ham kiradi: proyekt ro'yxatdan
# tushib bo'lgach arrachi xaritani ocholmaydi — oxirgi xato chekni texnolog tuzatadi
LabelCancelUser = Annotated[
    User, Depends(require_roles(UserRole.TERMINAL, *POST_ROLES, UserRole.MANAGER, UserRole.TEXNOLOG))
]


@router.delete("/labels/{instance_id}", response_model=Message, operation_id="cancel_instance_label")
async def cancel_instance_label(db: SessionDep, user: LabelCancelUser, instance_id: int) -> Message:
    """Chekni bekor qilish (long press / admin xarita): noto'g'ri chiqarilgan yorliq
    katakni chop etilmagan holatga qaytaradi."""
    instance = await db.get(PartInstance, instance_id)
    if instance is None or instance.is_deleted:
        raise NotFoundException("Nusxa topilmadi.")
    instance.label_printed_at = None

    # Kesish postlarida chek chiqarish skan ham yozadi ("chek = kesildi"), shuning
    # uchun bekor qilish o'sha skanni ham qaytarishi shart — aks holda katak yashil
    # bo'lib qolar va qadam hisobi (`total_done`) oshgan holida qolardi. Faqat
    # chop etish yozgan skan bekor bo'ladi: operator qo'lda qilgan skanga tegilmaydi.
    auto_scans = (
        (
            await db.execute(
                select(Scan).where(
                    Scan.instance_id == instance.id,
                    # Eski shakl (`cutprint-12`) ham, yangisi (`cutprint-12-1755…`)
                    # ham: har chop etish o'z hodisa nomi bilan yoziladi
                    Scan.client_event_id.in_([f"cutprint-{instance.id}", f"rvprint-{instance.id}"])
                    | Scan.client_event_id.like(f"cutprint-{instance.id}-%")
                    | Scan.client_event_id.like(f"rvprint-{instance.id}-%"),
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    for scan in auto_scans:
        scan.is_cancelled = True
        scan.cancelled_at = datetime.now(UTC)
        await db.execute(
            update(PartRoute)
            .where(PartRoute.id == scan.route_id, PartRoute.total_done > 0)
            .values(total_done=PartRoute.total_done - 1)
        )
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
    return Message(message=f"Chek bekor qilindi: {instance.qr_text}")


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
    full_path = upload_root() / row.path
    if not full_path.is_file():
        raise NotFoundException("Fayl diskda topilmadi.")
    return FileResponse(full_path, filename=row.filename, media_type="application/xml")
