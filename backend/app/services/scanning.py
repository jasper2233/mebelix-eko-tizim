"""Scan engine (TZ 7–8): instance-level pipeline control.

Every physical copy has a unique QR (TZ 5.8), so validation is exact: a copy can be
scanned at post N only the allowed number of times (per_instance), and — in strict
mode — only after THE SAME copy finished post N−1. Other copies never interfere.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.schemas.terminal import ScanResult

from sqlalchemy import func, select, update
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
    """Skan xatosi: kod + o'zbekcha xabar (TZ 8.5 dialogi, 422 detail).

    KOD KIM HARAKAT QILISHINI aytadi — matn beqaror (tahrirlanadi), kod barqaror:
    frontend ovozni, hisobot esa guruhlashni shunga qarab tanlaydi.

      E001  detal/plan mos kelmadi — operator chekni tekshiradi
      E002  QR formati buzuq — chek qayta chop etiladi
      E003  buyurtma bekor qilingan — manager
      E004  navbat buzildi — oldingi bosqichni kutish kerak
      E005  sessiya yo'q yoki muddati tugagan — beyjik
      E006  beyjik muammosi — admin/hodim
      E008  ish allaqachon bajarilgan — xato emas, ogohlantirish
      E009  SOZLAMA xatosi (post/stanok yo'q) — admin tuzatadi, operator emas

    E007 server kodi emas: aloqa uzilganda terminal frontendi o'zi hosil qiladi.
    """

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
            raise ScanRejected("E009", f"{post_code} posti topilmadi. Admin postlarni sozlashi kerak.")
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
            raise ScanRejected("E009", f"{post.name} postida stanok yo'q. Admin stanok qo'shishi kerak.")
        return machine, post

    if user.machine_id is None:
        raise ScanRejected("E009", "Terminal foydalanuvchisiga stanok biriktirilmagan.")
    machine = await db.get(Machine, user.machine_id)
    if machine is None or machine.is_deleted:
        raise ScanRejected("E009", "Terminal stanogi topilmadi.")
    post = await db.get(Post, machine.post_id)
    if post is None:
        raise ScanRejected("E009", "Stanok posti topilmadi.")
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


async def expire_if_stale(db: AsyncSession, session: WorkSession | None) -> WorkSession | None:
    """12 soatlik smena muddati (TZ 8.5 E005): o'tgan bo'lsa yopib None qaytaradi.
    Terminal ham, stanok skan-forvardi ham SHU tekshiruvdan o'tadi."""
    if session is None:
        return None
    started = session.created_at if session.created_at.tzinfo else session.created_at.replace(tzinfo=UTC)
    if datetime.now(UTC) - started > timedelta(hours=settings.SESSION_MAX_HOURS):
        session.status = SessionStatus.ENDED
        session.ended_at = datetime.now(UTC)
        await db.flush()
        return None
    return session


async def active_session(db: AsyncSession, user: User, machine: Machine) -> WorkSession:
    session = await latest_active_session(db, machine.id)

    # 12-hour shift timeout (TZ 8.5 E005)
    if session is not None and (session := await expire_if_stale(db, session)) is None:
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


async def _scans_done(db: AsyncSession, instance_id: int, route_id: int) -> int:
    """Shu NUSXA shu QADAMDA necha marta skanlangan. Kalit `route_id` — post emas:
    bitta post marshrutda ikki marta bo'lsa (kromka -> prisadka -> kromka) qadamlar
    hisobi aralashib ketardi."""
    return (
        await db.execute(
            select(func.count(Scan.id)).where(
                Scan.instance_id == instance_id,
                Scan.route_id == route_id,
                Scan.is_cancelled == False,  # noqa: E712
                Scan.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one()


async def _close_assembly_children(
    db: AsyncSession,
    *,
    scan: Scan,
    part: Part,
    post: Post,
    route: PartRoute,
    session: WorkSession,
    machine: Machine,
) -> None:
    """Asosiy detal skani unga biriktirilgan MAYDA detallarni ham yopadi.

    Mayda detal marshruti aynan birikish qadamida tugaydi (`orders._set_custom_route`
    unga qadoqlash/ombor dumini qo'shmaydi), shuning uchun birikish nuqtasi — mayda
    detalning OXIRGI qadami. U shu postda bo'lsa, bu skan o'sha qadamni yopadi.

    Chala detaldan yaxlit buyum yig'ib bo'lmaydi: mayda detalning oldingi bosqichi
    tugamagan bo'lsa butun skan rad etiladi (E004), ya'ni asosiy detal ham o'tmaydi.
    """
    children = (
        (
            await db.execute(
                select(Part).where(
                    Part.assembly_parent_id == part.id,
                    Part.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    if not children:
        return
    # Asosiy detalning shu qadamdagi OXIRGI nusxasi qolgan maydalarning hammasini
    # yopadi: sonlar bo'linmasa (5 mayda / 2 asosiy) qoldiq osilib qolmasin.
    last_parent_scan = route.total_done >= route.total_required

    for child in children:
        steps = list(
            (
                await db.execute(
                    select(PartRoute)
                    .where(
                        PartRoute.part_id == child.id,
                        PartRoute.is_enabled == True,  # noqa: E712
                        PartRoute.is_deleted == False,  # noqa: E712
                    )
                    .order_by(PartRoute.seq)
                )
            )
            .scalars()
            .all()
        )
        if not steps or steps[-1].post_id != post.id:
            continue  # birikish boshqa postda (yoki marshrut chizilmagan)
        merge = steps[-1]

        open_instances = []
        for inst in (
            (
                await db.execute(
                    select(PartInstance)
                    .where(
                        PartInstance.part_id == child.id,
                        PartInstance.is_deleted == False,  # noqa: E712
                    )
                    .order_by(PartInstance.instance_no)
                )
            )
            .scalars()
            .all()
        ):
            if await _scans_done(db, inst.id, merge.id) < merge.per_instance:
                open_instances.append(inst)
        if not open_instances:
            continue

        per_parent = max(1, child.count // part.count) if part.count else len(open_instances)
        take = open_instances if last_parent_scan else open_instances[:per_parent]

        for inst in take:
            for prev in steps[:-1]:
                if await _scans_done(db, inst.id, prev.id) < prev.per_instance:
                    prev_post = await db.get(Post, prev.post_id)
                    nom = prev_post.name if prev_post is not None else f"{prev.seq}-qadam"
                    raise ScanRejected(
                        "E004",
                        f"Mayda detal {inst.qr_text} hali {nom} bosqichidan o'tmagan — yig'ib bo'lmaydi.",
                    )
            db.add(
                Scan(
                    order_id=child.order_id,
                    part_id=child.id,
                    instance_id=inst.id,
                    route_id=merge.id,
                    post_id=post.id,
                    machine_id=machine.id,
                    employee_id=session.employee_id,
                    session_id=session.id,
                    client_event_id=f"asm-{scan.id}-{inst.id}",
                    parent_scan_id=scan.id,
                )
            )
            await db.execute(
                update(PartRoute).where(PartRoute.id == merge.id).values(total_done=PartRoute.total_done + 1)
            )
    await db.flush()


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
        raise ScanRejected("E002", "QR kodi noto'g'ri formatda. Chekni qaytadan chop eting.")

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
        raise ScanRejected("E001", "Bu detal uchun tugallanmagan plan topilmadi. Chekni tekshiring.")
    instance, order = row
    if order.status == OrderStatus.CANCELLED:
        raise ScanRejected("E003", "Buyurtma bekor qilingan. Managerga murojaat qiling.")

    part = await db.get(Part, instance.part_id)
    assert part is not None

    # Shu postdagi qadamlar navbat bo'yicha: birinchi TUGALLANMAGANI shu skanniki.
    # Post marshrutda takrorlanishi mumkin, shuning uchun bitta qator kutilmaydi.
    steps = (
        (
            await db.execute(
                select(PartRoute)
                .where(
                    PartRoute.part_id == part.id,
                    PartRoute.post_id == post.id,
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                )
                .order_by(PartRoute.seq)
            )
        )
        .scalars()
        .all()
    )
    if not steps:
        raise ScanRejected("E001", "Bu post bu detal marshrutida yo'q. Chekni tekshiring.")

    route = None
    for step in steps:
        if await _scans_done(db, instance.id, step.id) < step.per_instance:
            route = step
            break
    if route is None:
        raise ScanRejected("E008", "Bu detal allaqachon yakunlangan.")
    if route.machine_id is not None and route.machine_id != machine.id:
        raise ScanRejected("E001", "Bu detal boshqa stanokka biriktirilgan.")

    # Qat'iy tartib (TZ 7.2.5 / 8.5 E004): postlarning global tartibi emas, detalning
    # O'Z marshruti bo'yicha — nostandart marshrut roverdan boshlanishi mumkin.
    if settings.STRICT_STAGE_ORDER:
        pending = (
            await db.execute(
                select(PartRoute)
                .where(
                    PartRoute.part_id == part.id,
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                    PartRoute.seq < route.seq,
                )
                .order_by(PartRoute.seq)
            )
        ).scalars()
        for prev in pending:
            if await _scans_done(db, instance.id, prev.id) < prev.per_instance:
                prev_post = await db.get(Post, prev.post_id)
                nom = prev_post.name if prev_post is not None else f"{prev.seq}-qadam"
                raise ScanRejected("E004", f"Navbat: avval {nom}. Oldingi bosqich yakunlanmagan.")

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
    # Inkrement SQL tomonda: ikki terminal bir vaqtda skanlasa Python tomonda
    # o'qib-yozish (`+= 1`) bittasini yo'qotardi va qadam `total_required` ga
    # hech qachon yetmasdi — buyurtma abadiy "tugamagan" bo'lib qolardi.
    await db.execute(update(PartRoute).where(PartRoute.id == route.id).values(total_done=PartRoute.total_done + 1))
    await db.refresh(route, ["total_done"])
    try:
        await db.flush()
    except IntegrityError:  # client_event_id race — treat as replay
        await db.rollback()
        raise ScanRejected("E001", "Takroriy scan aniqlandi. Qayta urining.") from None

    # Yig'ma buyum: shu qadamda asosiy detalga mayda detallar yopishtiriladi.
    # Ular alohida skanerlanmaydi — asosiy detalning skani ularnikini ham yopadi.
    await _close_assembly_children(db, scan=scan, part=part, post=post, route=route, session=session, machine=machine)

    outcome = ScanOutcome(
        scan=scan,
        part=part,
        instance=instance,
        qoldiq=route.total_required - route.total_done,
    )

    # SCX served on EVERY scan at CNC posts (TZ 12.5).
    if post.code in (PostCode.PRISADKA, PostCode.ROVER):
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


async def finalize_scan(
    db: AsyncSession,
    outcome: ScanOutcome,
    *,
    user_id: int | None = None,
    source: str = "",
    agent_id: int | None = None,
) -> "ScanResult":
    """Muvaffaqiyatli skanning YAKUNI — log + commit + WS publish + ScanResult.
    Terminal (scans.py) va stanok skan-forvardi (bridge_agents.py) aynan shu
    yo'ldan o'tadi: ikki nusxa drift bergani uchun bitta joyga yig'ildi."""
    from app.core.ws import ws_manager
    from app.crud import log_action
    from app.schemas.terminal import ScanResult

    if not outcome.duplicate:
        meta: dict[str, Any] = {"post_id": outcome.scan.post_id, "machine_id": outcome.scan.machine_id}
        if agent_id is not None:
            meta["agent_id"] = agent_id
        log_action(
            db,
            module="scan",
            action="recorded",
            user_id=user_id,
            employee_id=outcome.scan.employee_id,
            entity_type="scan",
            entity_id=outcome.scan.id,
            message=f"Skan{source}: {outcome.instance.qr_text} — {outcome.part.name}",
            meta=meta,
        )
    # Avto-SCX proyekt papkasiga tushishi uchun (downloadScx subpapka nomi)
    order = await db.get(Order, outcome.scan.order_id)
    await db.commit()
    for event in outcome.events:
        await ws_manager.publish(
            event["type"], event["payload"], post_id=event.get("post_id"), machine_id=event.get("machine_id")
        )
    return ScanResult(
        scan_id=outcome.scan.id,
        duplicate=outcome.duplicate,
        qr_text=outcome.instance.qr_text,
        part_code=qr_part_code(outcome.instance.qr_text, outcome.part.count),
        part_name=outcome.part.name,
        instance_no=outcome.instance.instance_no,
        qoldiq=outcome.qoldiq,
        scx_file_ids=outcome.scx_file_ids,
        project_name=(order.project_name or order.number) if order else None,
        order_stage_completed=outcome.order_stage_completed,
        order_completed=outcome.order_completed,
    )


async def log_rejected_scan(
    db: AsyncSession,
    exc: ScanRejected,
    qr_text: str,
    *,
    user_id: int | None = None,
    source: str = "",
    meta_extra: dict[str, Any] | None = None,
) -> None:
    """Rad etilgan skan YAKUNI — rollback + audit-log + commit.
    Terminal (scans.py) va stanok skan-forvardi (bridge_agents.py) bir xil blokni
    takrorlardi; HTTPException(422) esa har bir chaqiruv joyining o'zida qoladi."""
    from app.crud import log_action

    await db.rollback()
    log_action(
        db,
        module="scan",
        action="rejected",
        user_id=user_id,
        message=f"Skan rad etildi{source}: {qr_text} — {exc.message}",
        meta={"code": exc.code, **(meta_extra or {})},
    )
    await db.commit()


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
    # Yig'ma buyum: shu skan mayda detallarni ham yopgan bo'lsa, ular birga qaytadi —
    # aks holda asosiy detal qaytib, maydalari yopiq qolib ketardi.
    derived = (
        (
            await db.execute(
                select(Scan).where(
                    Scan.parent_scan_id == scan.id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    for child_scan in derived:
        child_scan.is_cancelled = True
        child_scan.cancelled_at = scan.cancelled_at
        await db.execute(
            update(PartRoute)
            .where(PartRoute.id == child_scan.route_id, PartRoute.total_done > 0)
            .values(total_done=PartRoute.total_done - 1)
        )

    route = await db.get(PartRoute, scan.route_id)
    if route is not None:
        # Kamaytirish ham SQL tomonda — parallel skan/bekor qilishda drift bo'lmasin
        await db.execute(
            update(PartRoute)
            .where(PartRoute.id == route.id, PartRoute.total_done > 0)
            .values(total_done=PartRoute.total_done - 1)
        )
        await db.refresh(route, ["total_done"])

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
