from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from app.api.deps import AdminUser, CurrentUser, SessionDep, client_ip
from app.api.routes._shared import drop_forbidden_nulls
from app.core.exceptions import DuplicateValueException, NotFoundException
from app.crud import crud_machines, crud_posts, log_action
from app.models import BridgeAgent, Machine, Order, PartRoute, Scan, User
from app.models.enums import OrderStatus
from app.schemas.common import Message
from app.schemas.machines import MachineCreate, MachineRead, MachineUpdate
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

    # `crew_sessions` 12 soatlik muddatni o'zi qo'llaydi — yopishni unutilgan
    # eskirgan smena o'chirishni abadiy bloklab turmasin (xom COUNT shunday qilardi).
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
