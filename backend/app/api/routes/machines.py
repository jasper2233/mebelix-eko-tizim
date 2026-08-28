from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from app.api.deps import AdminUser, CurrentUser, SessionDep, client_ip
from app.core.exceptions import DuplicateValueException, NotFoundException
from app.core.security import get_password_hash
from app.crud import crud_machines, crud_posts, log_action
from app.models import BridgeAgent, Machine, PartRoute, Scan, User, WorkSession
from app.models.enums import SessionStatus, UserRole
from app.schemas.common import Message
from app.schemas.machines import MachineCreate, MachineRead, MachineUpdate, TerminalAccountUpsert

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

    open_sessions = (
        await db.execute(
            select(func.count(WorkSession.id)).where(
                WorkSession.machine_id == machine_id,
                WorkSession.status == SessionStatus.ACTIVE,
                WorkSession.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one()
    if open_sessions:
        blockers.append(f"ochiq smena: {open_sessions} ta")

    unfinished = (
        await db.execute(
            select(func.count(PartRoute.id)).where(
                PartRoute.machine_id == machine_id,
                PartRoute.total_done < PartRoute.total_required,
                PartRoute.is_deleted == False,  # noqa: E712
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
        raise HTTPException(status_code=409, detail=f'"{name}" nomli ish markazi allaqachon bor.')


async def _with_accounts(db: SessionDep, machines: list[Machine]) -> list[MachineRead]:
    """Har mashinaga uning monoblok hisobining loginini qo'shadi (bitta so'rov)."""
    if not machines:
        return []
    rows = (
        await db.execute(
            select(User.machine_id, User.username).where(
                User.machine_id.in_([m.id for m in machines]),
                User.role == UserRole.TERMINAL,
                User.is_deleted == False,  # noqa: E712
            )
        )
    ).all()
    by_machine: dict[int | None, str] = {mid: uname for mid, uname in rows}  # noqa: C416
    out = []
    for m in machines:
        item = MachineRead.model_validate(m)
        item.terminal_username = by_machine.get(m.id)
        out.append(item)
    return out


@router.get("/", response_model=list[MachineRead], operation_id="read_machines")
async def read_machines(db: SessionDep, _: CurrentUser) -> list[MachineRead]:
    """All machines — small fixed set, no pagination. Terminals/TABLO need this for context too."""
    machines, _total = await crud_machines.get_multi(db, limit=500)
    return await _with_accounts(db, list(machines))


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


@router.get("/{machine_id}", response_model=MachineRead, operation_id="read_machine")
async def read_machine(db: SessionDep, _: CurrentUser, machine_id: int) -> Machine:
    return await crud_machines.get_or_404(db, "Ish markazi topilmadi.", id=machine_id)


@router.patch("/{machine_id}", response_model=MachineRead, operation_id="update_machine")
async def update_machine(
    db: SessionDep, current_user: AdminUser, machine_id: int, body: MachineUpdate, request: Request
) -> Machine:
    machine = await crud_machines.get_or_404(db, "Ish markazi topilmadi.", id=machine_id)
    update_data = body.model_dump(exclude_unset=True)
    if update_data.get("name"):
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


@router.put(
    "/{machine_id}/terminal-account",
    response_model=Message,
    operation_id="upsert_terminal_account",
)
async def upsert_terminal_account(
    db: SessionDep, current_user: AdminUser, machine_id: int, body: TerminalAccountUpsert, request: Request
) -> Message:
    """Ish markazining MONOBLOK hisobi: yaratadi yoki loginini/parolini yangilaydi.

    Nega ish markazlari sahifasida, Hodimlarda emas: bu hisob ODAM emas —
    monoblokning o'zi. Terminal ekrani qaysi mashinani ochishini AYNAN shu hisob
    hal qiladi (`resolve_terminal` uni `user.machine_id` dan oladi). Usiz post
    o'zining eng kichik id'li mashinasiga qulflanadi va postda ikkinchi mashina
    paydo bo'lgach unga yetib boradigan yo'l qolmaydi (buyurtma o'sha mashinaga
    biriktirilsa har skan E001 beradi).

    Odam bu hisob bilan tanishtirilmaydi — smenani beyjik yoki ismni bosish
    ochadi. Shuning uchun hodim yozuvi YARATILMAYDI.
    """
    machine = await crud_machines.get(db, id=machine_id)
    if machine is None:
        raise NotFoundException("Ish markazi topilmadi.")
    existing = (
        await db.execute(
            select(User).where(
                User.machine_id == machine_id,
                User.role == UserRole.TERMINAL,
                User.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    band = (
        await db.execute(
            select(User.id).where(
                User.username == body.username,
                User.is_deleted == False,  # noqa: E712
                *([User.id != existing.id] if existing is not None else []),
            )
        )
    ).scalar_one_or_none()
    if band is not None:
        raise DuplicateValueException("Bu login allaqachon band.")

    if existing is not None:
        existing.username = body.username
        existing.hashed_password = await get_password_hash(body.password)
        existing.is_active = True
        xabar = f"Monoblok hisobi yangilandi: {machine.name} ({body.username})"
        action = "terminal_account_updated"
    else:
        db.add(
            User(
                name=f"{machine.name} monoblok",
                username=body.username,
                # Telefon User'da majburiy va unikal — qurilmada u yo'q, shuning
                # uchun seed'dagi kabi sintetik raqam (odam raqami bilan
                # to'qnashmaydigan oraliq).
                phone=f"+99801{machine_id:06d}",
                hashed_password=await get_password_hash(body.password),
                role=UserRole.TERMINAL,
                machine_id=machine_id,
                is_active=True,
            )
        )
        xabar = f"Monoblok hisobi yaratildi: {machine.name} ({body.username})"
        action = "terminal_account_created"
    log_action(
        db,
        module="machines",
        action=action,
        user_id=current_user.id,
        entity_type="machine",
        entity_id=machine_id,
        message=xabar,
        ip=client_ip(request),
    )
    await db.commit()
    return Message(message=xabar)


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
