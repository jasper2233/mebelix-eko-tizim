"""Scan engine (TZ 7–8): instance-level pipeline control.

Every physical copy has a unique QR (TZ 5.8), so validation is exact: a copy can be
scanned at post N only the allowed number of times (per_instance), and — in strict
mode — only after THE SAME copy finished post N−1. Other copies never interfere.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Employee, Machine, Order, OrderFile, Part, PartInstance, PartRoute, Post, Scan, WorkSession
from app.models.enums import POST_ROLES, EmployeeStatus, FileKind, OrderStatus, PostCode, SessionStatus, UserRole
from app.models.user import User

_QR_RE = re.compile(r"^.+_.+$")  # {productCode}_{partCode}[_{n}] — yagona nusxada suffiks yo'q (TZ 5.8)


def qr_part_code(qr: str, count: int) -> str:
    """Nusxa QR'idan detal kodi: yagona nusxada QR = kodning o'zi, takrorlanganda _n olib tashlanadi."""
    return qr if count == 1 else qr.rsplit("_", 1)[0]


class ScanRejected(Exception):
    """TZ 8.5 error dialog: code (E001..E006) + Uzbek message."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


@dataclass
class ScanOutcome:
    scan: Scan
    part: Part
    instance: PartInstance
    qoldiq: int
    duplicate: bool = False
    scx_file_ids: list[int] = field(default_factory=list)
    order_stage_completed: bool = False
    order_completed: bool = False
    events: list[dict[str, Any]] = field(default_factory=list)


async def resolve_terminal(db: AsyncSession, user: User) -> tuple[Machine, Post]:
    post_code = POST_ROLES.get(UserRole(user.role))
    if post_code is not None:
        # Operator role (arrachi, kromkachi, ...): post comes from the role itself.
        post = (
            await db.execute(select(Post).where(Post.code == post_code, Post.is_deleted == False))  # noqa: E712
        ).scalar_one_or_none()
        if post is None:
            raise ScanRejected("E001", f"{post_code} posti topilmadi. Admin postlarni sozlashi kerak.")
        machine = None
        if user.machine_id is not None:
            machine = await db.get(Machine, user.machine_id)
        if machine is None or machine.is_deleted:
            # ponytail: first active machine of the post; bind user.machine_id when a post gets several
            machine = (
                await db.execute(
                    select(Machine)
                    .where(Machine.post_id == post.id, Machine.is_deleted == False)  # noqa: E712
                    .order_by(Machine.id)
                    .limit(1)
                )
            ).scalar_one_or_none()
        if machine is None:
            raise ScanRejected("E001", f"{post.name} postida stanok yo'q. Admin stanok qo'shishi kerak.")
        return machine, post

    if user.machine_id is None:
        raise ScanRejected("E001", "Terminal foydalanuvchisiga stanok biriktirilmagan.")
    machine = await db.get(Machine, user.machine_id)
    if machine is None or machine.is_deleted:
        raise ScanRejected("E001", "Terminal stanogi topilmadi.")
    post = await db.get(Post, machine.post_id)
    if post is None:
        raise ScanRejected("E001", "Stanok posti topilmadi.")
    return machine, post


async def operator_employee(db: AsyncSession, user: User, post_id: int) -> Employee:
    """Auto-provisioned Employee mirror for operator-role users, so scans, sessions and
    productivity reports keep their employee attribution without a badge."""
    badge = f"user-{user.id}"  # ponytail: avoids a user_id FK migration; badge_id is unique and 36 chars
    employee = (
        await db.execute(
            select(Employee).where(Employee.badge_id == badge, Employee.is_deleted == False)  # noqa: E712
        )
    ).scalar_one_or_none()
    if employee is None:
        employee = Employee(
            full_name=user.name or user.username,
            badge_id=badge,
            position=str(user.role),
            assigned_post_ids=[post_id],
        )
        db.add(employee)
        await db.flush()
    elif post_id not in employee.assigned_post_ids:
        employee.assigned_post_ids = [*employee.assigned_post_ids, post_id]
    return employee


async def latest_active_session(db: AsyncSession, machine_id: int) -> WorkSession | None:
    """Shu stanokdagi ochiq smena (eng oxirgisi)."""
    return (
        await db.execute(
            select(WorkSession)
            .where(
                WorkSession.machine_id == machine_id,
                WorkSession.status == SessionStatus.ACTIVE,
                WorkSession.is_deleted == False,  # noqa: E712
            )
            .order_by(WorkSession.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def active_session(db: AsyncSession, user: User, machine: Machine) -> WorkSession:
    session = await latest_active_session(db, machine.id)

    # 12-hour shift timeout (TZ 8.5 E005)
    if session is not None:
        started = session.created_at if session.created_at.tzinfo else session.created_at.replace(tzinfo=UTC)
        if datetime.now(UTC) - started > timedelta(hours=settings.SESSION_MAX_HOURS):
            session.status = SessionStatus.ENDED
            session.ended_at = datetime.now(UTC)
            await db.flush()
            session = None
            if POST_ROLES.get(UserRole(user.role)) is None:
                raise ScanRejected(
                    "E005",
                    f"Sessiya muddati tugadi ({settings.SESSION_MAX_HOURS} soat). Beyjikni qaytadan scan qiling.",
                )

    # Operator role: the login IS the shift — open/take over the session automatically.
    if POST_ROLES.get(UserRole(user.role)) is not None:
        employee = await operator_employee(db, user, machine.post_id)
        if session is not None and session.employee_id != employee.id:
            session.status = SessionStatus.ENDED
            session.ended_at = datetime.now(UTC)
            session = None
        if session is None:
            session = WorkSession(
                employee_id=employee.id, user_id=user.id, machine_id=machine.id, post_id=machine.post_id
            )
            db.add(session)
            await db.flush()
        return session

    if session is None:
        raise ScanRejected("E005", "Aktiv sessiya yo'q. Beyjikni scan qiling.")
    badge_employee = await db.get(Employee, session.employee_id)
    if badge_employee is None or badge_employee.status != EmployeeStatus.ACTIVE:
        raise ScanRejected("E006", "Beyjik nofaol. Adminga murojaat qiling.")
    return session


async def _scans_done(db: AsyncSession, instance_id: int, post_id: int) -> int:
    return (
        await db.execute(
            select(func.count(Scan.id)).where(
                Scan.instance_id == instance_id,
                Scan.post_id == post_id,
                Scan.is_cancelled == False,  # noqa: E712
                Scan.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one()


async def record_scan(
    db: AsyncSession,
    *,
    user: User,
    qr_text: str,
    client_event_id: str,
) -> ScanOutcome:
    """Validate and register one work unit. Caller commits and publishes outcome.events."""
    machine, post = await resolve_terminal(db, user)
    session = await active_session(db, user, machine)
    return await record_scan_at(
        db, machine=machine, post=post, session=session, qr_text=qr_text, client_event_id=client_event_id
    )


async def record_scan_at(
    db: AsyncSession,
    *,
    machine: Machine,
    post: Post,
    session: WorkSession,
    qr_text: str,
    client_event_id: str,
) -> ScanOutcome:
    """Core yozuv — kontekst tayyor bo'lganda. Terminal (user orqali) ham,
    bridge-agent skan-forvardi (stanok bog'lami orqali) ham shu yo'ldan o'tadi."""
    qr = qr_text.strip()
    if not _QR_RE.match(qr):
        raise ScanRejected("E002", "QR kodi noto'g'ri formatda. Yorliqni qaytadan chop eting.")

    # Idempotent replay (network retry): same client_event_id → same success, no recount.
    existing = (await db.execute(select(Scan).where(Scan.client_event_id == client_event_id))).scalar_one_or_none()
    if existing is not None:
        part = await db.get(Part, existing.part_id)
        instance = await db.get(PartInstance, existing.instance_id)
        route = await db.get(PartRoute, existing.route_id)
        assert part is not None and instance is not None and route is not None
        return ScanOutcome(
            scan=existing,
            part=part,
            instance=instance,
            qoldiq=route.total_required - route.total_done,
            duplicate=True,
        )

    # Locate the copy among live orders. Eski chop etilgan yorliqlar (migratsiyadan
    # oldin yagona nusxa ham `_1` bilan chiqqan) uchun suffikssiz variant ham sinaladi.
    row = None
    for cand in [qr, qr[:-2]] if qr.endswith("_1") else [qr]:
        row = (
            await db.execute(
                select(PartInstance, Order)
                .join(Order, Order.id == PartInstance.order_id)
                .where(
                    PartInstance.qr_text == cand,
                    PartInstance.is_deleted == False,  # noqa: E712
                    Order.is_deleted == False,  # noqa: E712
                    Order.status.in_([OrderStatus.PRODUCTION, OrderStatus.CANCELLED]),
                )
                .order_by(Order.id.desc())
            )
        ).first()
        if row is not None:
            break
    if row is None:
        raise ScanRejected("E001", "Bu detal uchun tugallanmagan plan topilmadi. Yorliqni tekshiring.")
    instance, order = row
    if order.status == OrderStatus.CANCELLED:
        raise ScanRejected("E003", "Buyurtma bekor qilingan. Managerga murojaat qiling.")

    part = await db.get(Part, instance.part_id)
    assert part is not None

    route = (
        await db.execute(
            select(PartRoute).where(
                PartRoute.part_id == part.id,
                PartRoute.post_id == post.id,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if route is None:
        raise ScanRejected("E001", "Bu post bu detal marshrutida yo'q. Yorliqni tekshiring.")
    if route.machine_id is not None and route.machine_id != machine.id:
        raise ScanRejected("E001", "Bu detal boshqa stanokka biriktirilgan.")

    done = await _scans_done(db, instance.id, post.id)
    if done >= route.per_instance:
        raise ScanRejected("E001", "Bu detal allaqachon yakunlangan.")

    # Optional strict pipeline order (TZ 7.2.5 / 8.5 E004) — per-instance check.
    if settings.STRICT_STAGE_ORDER:
        earlier_routes = (
            await db.execute(
                select(PartRoute)
                .join(Post, Post.id == PartRoute.post_id)
                .where(
                    PartRoute.part_id == part.id,
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                    Post.order_index < post.order_index,
                )
            )
        ).scalars()
        for prev_route in earlier_routes:
            prev_done = await _scans_done(db, instance.id, prev_route.post_id)
            if prev_done < prev_route.per_instance:
                raise ScanRejected("E004", "Oldingi bosqich yakunlanmagan. Avval oldingi bosqichni yakunlang.")

    scan = Scan(
        order_id=order.id,
        part_id=part.id,
        instance_id=instance.id,
        route_id=route.id,
        post_id=post.id,
        machine_id=machine.id,
        employee_id=session.employee_id,
        session_id=session.id,
        client_event_id=client_event_id,
    )
    db.add(scan)
    route.total_done += 1
    try:
        await db.flush()
    except IntegrityError:  # client_event_id race — treat as replay
        await db.rollback()
        raise ScanRejected("E001", "Takroriy scan aniqlandi. Qayta urining.") from None

    outcome = ScanOutcome(
        scan=scan,
        part=part,
        instance=instance,
        qoldiq=route.total_required - route.total_done,
    )

    # SCX served on EVERY scan at CNC posts (TZ 12.5).
    if post.code in (PostCode.PRISADKA, PostCode.PAZ, PostCode.ROVER):
        files = (
            (
                await db.execute(
                    select(OrderFile.id).where(
                        OrderFile.part_id == part.id,
                        OrderFile.kind == FileKind.SCX,
                        OrderFile.is_deleted == False,  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        )
        outcome.scx_file_ids = list(files)

    outcome.events.append(
        {
            "type": "scan.recorded",
            "payload": {
                "order_id": order.id,
                "order_number": order.number,
                "part_id": part.id,
                "part_code": qr_part_code(instance.qr_text, part.count),
                "instance_no": instance.instance_no,
                "post_id": post.id,
                "machine_id": machine.id,
                "qoldiq": outcome.qoldiq,
                "pattern_no": instance.pattern_no,
                "cell_index": instance.cell_index,
            },
            "post_id": post.id,
            "machine_id": machine.id,
        }
    )

    # Stage / order completion (TZ 7.1.8).
    stage_left = (
        await db.execute(
            select(func.count(PartRoute.id)).where(
                PartRoute.order_id == order.id,
                PartRoute.post_id == post.id,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
                PartRoute.total_done < PartRoute.total_required,
            )
        )
    ).scalar_one()
    if stage_left == 0:
        outcome.order_stage_completed = True
        outcome.events.append(
            {
                "type": "order.stage_completed",
                "payload": {"order_id": order.id, "order_number": order.number, "post_id": post.id},
            }
        )
        all_left = (
            await db.execute(
                select(func.count(PartRoute.id)).where(
                    PartRoute.order_id == order.id,
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                    PartRoute.total_done < PartRoute.total_required,
                )
            )
        ).scalar_one()
        if all_left == 0:
            order.status = OrderStatus.COMPLETED
            order.completed_at = datetime.now(UTC)
            outcome.order_completed = True
            outcome.events.append(
                {
                    "type": "order.completed",
                    "payload": {"order_id": order.id, "order_number": order.number},
                }
            )
    return outcome


async def cancel_scan(db: AsyncSession, *, user: User, scan_id: int) -> tuple[Scan, list[dict[str, Any]]]:
    """BEKOR QILISH (TZ 8.6): only the last N seconds, same terminal session."""
    machine, post = await resolve_terminal(db, user)
    session = await active_session(db, user, machine)

    scan = await db.get(Scan, scan_id)
    if scan is None or scan.is_deleted or scan.session_id != session.id:
        raise ScanRejected("E001", "Scan topilmadi yoki bu sessiyaga tegishli emas.")
    if scan.is_cancelled:
        raise ScanRejected("E001", "Bu scan allaqachon bekor qilingan.")
    created = scan.created_at if scan.created_at.tzinfo else scan.created_at.replace(tzinfo=UTC)
    if datetime.now(UTC) - created > timedelta(seconds=settings.SCAN_UNDO_SECONDS):
        raise ScanRejected("E001", f"{settings.SCAN_UNDO_SECONDS} sekunddan ko'p o'tdi — faqat admin bekor qila oladi.")

    scan.is_cancelled = True
    scan.cancelled_at = datetime.now(UTC)
    route = await db.get(PartRoute, scan.route_id)
    if route is not None and route.total_done > 0:
        route.total_done -= 1

    order = await db.get(Order, scan.order_id)
    events: list[dict[str, Any]] = [
        {
            "type": "scan.cancelled",
            "payload": {
                "scan_id": scan.id,
                "order_id": scan.order_id,
                "part_id": scan.part_id,
                "post_id": scan.post_id,
                "qoldiq": (route.total_required - route.total_done) if route else None,
            },
            "post_id": scan.post_id,
            "machine_id": scan.machine_id,
        }
    ]
    # A completed order regresses if its last scan is undone.
    if order is not None and order.status == OrderStatus.COMPLETED:
        order.status = OrderStatus.PRODUCTION
        order.completed_at = None
    return scan, events
