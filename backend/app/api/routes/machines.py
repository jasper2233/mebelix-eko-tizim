from datetime import UTC, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from app.api.deps import AdminUser, CurrentUser, SessionDep, StaffReadUser, client_ip
from app.api.routes._shared import drop_forbidden_nulls
from app.core.config import TASHKENT_TZ
from app.core.exceptions import DuplicateValueException, NotFoundException
from app.crud import crud_machines, crud_posts, log_action
from app.models import (
    BridgeAgent,
    Machine,
    Order,
    Part,
    PartInstance,
    PartRoute,
    Scan,
    User,
    WorkSession,
)
from app.models import (
    KromkaMeasurement as KromkaMeasurementRecord,
)
from app.models.enums import OrderStatus, SessionStatus
from app.schemas.common import Message
from app.schemas.machines import (
    KromkaMeasurementRow,
    MachineCreate,
    MachineOverview,
    MachineRead,
    MachineUpdate,
)
from app.services.andon import read_live
from app.services.scanning import crew_sessions

router = APIRouter(prefix="/machines", tags=["machines"])


async def _blockers(db: SessionDep, machine_id: int) -> list[str]:
    """Ish markazini o'chirishga to'sqinlik qiladigan bog'lamlar, odam tilida.

    O'chirish soft-delete, ya'ni FK buzilmaydi — LEKIN bog'lam jimgina uziladi:
    qurilma hisobi kirolmaydi (E009), agent skan-forvardi 409 beradi, tugallanmagan
    marshrutlar terminal ro'yxatidan yo'qoladi (filtr `machine_id` bo'yicha).
    Shuning uchun sabab ko'rsatib to'xtatamiz, jim o'chirmaymiz.
    """
    blockers = []
    accounts = (
        (
            await db.execute(
                select(User.username).where(User.machine_id == machine_id, User.is_deleted == False)  # noqa: E712
            )
        )
        .scalars()
        .all()
    )
    if accounts:
        blockers.append(f"biriktirilgan hisob: {', '.join(accounts)}")

    agents = (
        (
            await db.execute(
                select(BridgeAgent.name).where(
                    BridgeAgent.machine_id == machine_id,
                    BridgeAgent.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    if agents:
        blockers.append(f"printer agenti: {', '.join(agents)}")

    # Smena muddati yo'q (2026-09-03): yopilmagan smena ish markazini o'chirishga
    # to'sqinlik qiladi — avval terminalda «Chiqish» yoki logout bilan yopiladi.
    open_sessions = len(await crew_sessions(db, machine_id))
    if open_sessions:
        blockers.append(f"ochiq smena: {open_sessions} ta")

    # Yopilgan buyurtma (bekor qilingan/topshirilgan) marshrutlari hech qachon
    # tugallanmaydi — ularsiz filtr ish markazini abadiy o'chirilmas qilardi.
    unfinished = (
        await db.execute(
            select(func.count(PartRoute.id))
            .join(Order, Order.id == PartRoute.order_id)
            .where(
                PartRoute.machine_id == machine_id,
                PartRoute.total_done < PartRoute.total_required,
                PartRoute.is_deleted == False,  # noqa: E712
                Order.status.notin_((OrderStatus.CANCELLED, OrderStatus.DELIVERED)),
                Order.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one()
    if unfinished:
        blockers.append(f"tugallanmagan marshrut: {unfinished} ta")
    return blockers


async def _check_name(db: SessionDep, name: str, machine_id: int | None = None) -> None:
    """Nom takrorlanmasin. Indeks (`ix_machine_name`) baribir rad etardi, lekin
    IntegrityError xabari admin uchun tushunarsiz bo'lardi."""
    query = select(Machine.id).where(
        func.lower(Machine.name) == name.strip().lower(),
        Machine.is_deleted == False,  # noqa: E712
    )
    if machine_id is not None:
        query = query.where(Machine.id != machine_id)
    if (await db.execute(query)).scalar_one_or_none() is not None:
        raise DuplicateValueException(f'"{name}" nomli ish markazi allaqachon bor.')


@router.get("/", response_model=list[MachineRead], operation_id="read_machines")
async def read_machines(db: SessionDep, _: CurrentUser) -> list[Machine]:
    """All machines — small fixed set, no pagination. Terminals/TABLO need this for context too."""
    machines, _total = await crud_machines.get_multi(db, limit=500)
    return machines


@router.get("/overview", response_model=list[MachineOverview], operation_id="read_machines_overview")
async def read_machines_overview(db: SessionDep, _: StaffReadUser) -> list[MachineOverview]:
    """Sahifa jadvali uchun jonli ustunlar: kim biriktirilgan, smenada nechta odam,
    bugun nechta skan, oxirgi skan, biriktirilgan tugallanmagan qadamlar.
    Ilgari sahifa uch ustun (nom/post/holat) edi — stanok ishlayaptimi, kim unda,
    qaysi agent — javob yo'q edi. O'chirish to'siqlari (`_blockers`) ham shu
    ma'lumotdan oldindan ko'rinadi."""
    today_start = datetime.combine(datetime.now(TASHKENT_TZ).date(), time.min, tzinfo=TASHKENT_TZ).astimezone(UTC)
    online_since = datetime.now(UTC) - timedelta(minutes=6)
    machines = (
        (await db.execute(select(Machine.id).where(Machine.is_deleted == False))).scalars().all()  # noqa: E712
    )
    accounts: dict[int, list[str]] = {}
    for mid, username in (
        await db.execute(
            select(User.machine_id, User.username).where(User.machine_id.is_not(None), User.is_deleted == False)  # noqa: E712
        )
    ).all():
        accounts.setdefault(mid, []).append(username)
    agents: dict[int, list[str]] = {}
    agent_online: dict[int, bool] = {}
    for mid, name, seen, paired in (
        await db.execute(
            select(
                BridgeAgent.machine_id, BridgeAgent.name, BridgeAgent.last_seen_at, BridgeAgent.token_hash.is_not(None)
            ).where(BridgeAgent.machine_id.is_not(None), BridgeAgent.is_deleted == False)  # noqa: E712
        )
    ).all():
        agents.setdefault(mid, []).append(name)
        if paired and seen is not None and seen >= online_since:
            agent_online[mid] = True
    on_shift: dict[int, int] = {
        mid: int(n)
        for mid, n in (
            await db.execute(
                select(WorkSession.machine_id, func.count(func.distinct(WorkSession.employee_id)))
                .where(
                    WorkSession.status == SessionStatus.ACTIVE,
                    WorkSession.created_at >= today_start,
                    WorkSession.is_deleted == False,  # noqa: E712
                )
                .group_by(WorkSession.machine_id)
            )
        ).all()
    }
    live_scan = (Scan.is_cancelled == False, Scan.is_deleted == False)  # noqa: E712
    scans: dict[int, tuple[int, datetime | None]] = {
        mid: (int(today), last)
        for mid, today, last in (
            await db.execute(
                select(
                    Scan.machine_id,
                    func.count(Scan.id).filter(Scan.created_at >= today_start),
                    func.max(Scan.created_at),
                )
                .where(Scan.machine_id.is_not(None), *live_scan)
                .group_by(Scan.machine_id)
            )
        ).all()
    }
    unfinished: dict[int, int] = {
        mid: int(n)
        for mid, n in (
            await db.execute(
                select(PartRoute.machine_id, func.count(PartRoute.id))
                .join(Order, Order.id == PartRoute.order_id)
                .where(
                    PartRoute.machine_id.is_not(None),
                    PartRoute.total_done < PartRoute.total_required,
                    PartRoute.is_deleted == False,  # noqa: E712
                    Order.status.notin_((OrderStatus.CANCELLED, OrderStatus.DELIVERED)),
                    Order.is_deleted == False,  # noqa: E712
                )
                .group_by(PartRoute.machine_id)
            )
        ).all()
    }
    # Navbat — terminal ro'yxati qoidasi (`terminal.py`: machine_id == men YOKI null),
    # qolgan skan bilan; faol buyurtmalar (PRODUCTION), yoqilgan qadamlar
    post_of: dict[int, int] = {}
    for mid, pid in (
        await db.execute(select(Machine.id, Machine.post_id).where(Machine.is_deleted == False))  # noqa: E712
    ).all():
        post_of[mid] = pid
    queue_rows = (
        await db.execute(
            select(PartRoute.post_id, PartRoute.machine_id, func.sum(PartRoute.total_required - PartRoute.total_done))
            .join(Order, Order.id == PartRoute.order_id)
            .where(
                PartRoute.total_done < PartRoute.total_required,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
                Order.status == OrderStatus.PRODUCTION,
                Order.is_deleted == False,  # noqa: E712
            )
            .group_by(PartRoute.post_id, PartRoute.machine_id)
        )
    ).all()
    queue: dict[int, int] = dict.fromkeys(machines, 0)
    for post_id, machine_id, remaining in queue_rows:
        for mid in machines:
            if post_of.get(mid) == post_id and (machine_id is None or machine_id == mid):
                queue[mid] += int(remaining)
    # Andon jonli holati Redis'da (`services/andon.py`); kalit yo'q — andon ulanmagan yoki aloqa yo'q
    andon = await read_live(machines)
    return [
        MachineOverview(
            machine_id=mid,
            accounts=accounts.get(mid, []),
            agents=agents.get(mid, []),
            agent_online=agent_online.get(mid, False),
            on_shift=on_shift.get(mid, 0),
            today_scans=scans.get(mid, (0, None))[0],
            last_scan_at=scans.get(mid, (0, None))[1],
            unfinished_routes=unfinished.get(mid, 0),
            queue_scans=queue.get(mid, 0),
            andon_state=andon[mid]["state"] if mid in andon else None,
            andon_since=datetime.fromtimestamp(andon[mid]["since"], UTC) if mid in andon else None,
        )
        for mid in machines
    ]


#: Jonli oqimda ko'rsatiladigan o'lchovlar soni. Yangi o'lchov WS bilan darhol qo'shiladi —
#: bu faqat sahifa ochilgandagi BOSHLANG'ICH ro'yxat.
_KROMKA_LIVE_N = 20


@router.get(
    "/kromka-measurements", response_model=list[KromkaMeasurementRow], operation_id="read_kromka_measurement_feed"
)
async def read_kromka_measurement_feed(db: SessionDep, _: StaffReadUser) -> list[KromkaMeasurementRow]:
    """Kromka stansiyalari o'lchagan oxirgi detallar — admin paneldagi jonli oqim.

    Har qator DETALGA bog'langan (`services/kromka.py`): kutilgan o'lcham va hukm
    shu yerda ko'rinadi. Marshrut `/{machine_id}` dan OLDIN turishi shart, aks holda
    «kromka-measurements» ish markazi id'si deb o'qilardi. Yangi o'lchov WS
    `kromka.measure` bilan darhol qo'shiladi; bu endpoint sahifa ochilganda chaqiriladi."""
    rows = (
        (
            await db.execute(
                select(KromkaMeasurementRecord, Machine.name, Part.name, PartInstance.qr_text)
                .join(Machine, Machine.id == KromkaMeasurementRecord.machine_id)
                .outerjoin(PartInstance, PartInstance.id == KromkaMeasurementRecord.instance_id)
                .outerjoin(Part, Part.id == PartInstance.part_id)
                .where(KromkaMeasurementRecord.is_deleted == False)  # noqa: E712
                .order_by(KromkaMeasurementRecord.measured_at.desc(), KromkaMeasurementRecord.id.desc())
                .limit(_KROMKA_LIVE_N)
            )
        )
        .tuples()
        .all()
    )

    def son(v: float | None) -> float | None:
        # Numeric ustun Decimal bo'lib keladi — JSON uchun float
        return float(v) if v is not None else None

    return [
        KromkaMeasurementRow(
            machine_id=row.machine_id,
            machine_name=machine_name,
            at=row.measured_at,
            length_mm=son(row.measured_mm),
            code=row.code,
            verdict=row.verdict.value,
            expected_mm=son(row.expected_mm),
            delta_mm=son(row.delta_mm),
            part_name=part_name,
            qr_text=qr_text,
            scan_id=row.scan_id,
        )
        for row, machine_name, part_name, qr_text in rows
    ]


@router.post("/", response_model=MachineRead, status_code=201, operation_id="create_machine")
async def create_machine(db: SessionDep, current_user: AdminUser, body: MachineCreate, request: Request) -> Machine:
    if await crud_posts.get(db, id=body.post_id) is None:
        raise NotFoundException("Post topilmadi.")
    await _check_name(db, body.name)
    machine = Machine(**body.model_dump())
    db.add(machine)
    await db.flush()
    log_action(
        db,
        module="machines",
        action="created",
        user_id=current_user.id,
        entity_type="machine",
        entity_id=machine.id,
        message=f"Ish markazi qo'shildi: {machine.name}",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(machine)
    return machine


@router.patch("/{machine_id}", response_model=MachineRead, operation_id="update_machine")
async def update_machine(
    db: SessionDep, current_user: AdminUser, machine_id: int, body: MachineUpdate, request: Request
) -> Machine:
    machine = await crud_machines.get_or_404(db, "Ish markazi topilmadi.", id=machine_id)
    # Machine ustunlarining hammasi NOT NULL — aniq `null` no-op, aks holda 500
    update_data = drop_forbidden_nulls(body.model_dump(exclude_unset=True))
    if "name" in update_data:
        await _check_name(db, update_data["name"], machine_id=machine.id)
    if "post_id" in update_data and update_data["post_id"] != machine.post_id:
        if await crud_posts.get(db, id=update_data["post_id"]) is None:
            raise NotFoundException("Post topilmadi.")
        # Skan tarixi bor ish markazini boshqa postga ko'chirish o'tgan hisobotlarni
        # jimgina buzadi: skanlar yangi post nomidan sanalib ketadi
        scans = (await db.execute(select(func.count(Scan.id)).where(Scan.machine_id == machine_id))).scalar_one()
        if scans:
            raise HTTPException(
                status_code=409,
                detail=f"{machine.name} da {scans} ta skan bor — postni o'zgartirib bo'lmaydi. Yangisini qo'shing.",
            )
    for field, value in update_data.items():
        setattr(machine, field, value)
    log_action(
        db,
        module="machines",
        action="updated",
        user_id=current_user.id,
        entity_type="machine",
        entity_id=machine.id,
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(machine)
    return machine


@router.delete("/{machine_id}", response_model=Message, operation_id="delete_machine")
async def delete_machine(db: SessionDep, current_user: AdminUser, machine_id: int, request: Request) -> Message:
    machine = await crud_machines.get_or_404(db, "Ish markazi topilmadi.", id=machine_id)
    blockers = await _blockers(db, machine_id)
    if blockers:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{machine.name} ishlatilmoqda — {'; '.join(blockers)}. "
                "Avval bog'lamni uzing yoki ish tugashini kutib, NOAKTIV holatiga o'tkazing."
            ),
        )
    log_action(
        db,
        module="machines",
        action="deleted",
        user_id=current_user.id,
        entity_type="machine",
        entity_id=machine.id,
        message=f"Ish markazi o'chirildi: {machine.name}",
        ip=client_ip(request),
    )
    await crud_machines.delete(db, id=machine_id)
    return Message(message="Ish markazi o'chirildi.")
