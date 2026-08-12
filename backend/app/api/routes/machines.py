import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request

from app.api.deps import AdminUser, CurrentUser, SessionDep, client_ip
from app.core.exceptions import NotFoundException
from app.crud import crud_machines, crud_posts, log_action
from app.models import Machine
from app.schemas.common import Message
from app.schemas.machines import MachineCreate, MachinePairCode, MachineRead, MachineUpdate

router = APIRouter(prefix="/machines", tags=["machines"])

# Bridge-agent pairing bilan bir xil: I/L/O/0/1 yo'q — kodni og'zaki aytganda adashtirmaydi
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
PAIR_TTL = timedelta(minutes=15)


@router.get("/", response_model=list[MachineRead], operation_id="read_machines")
async def read_machines(db: SessionDep, _: CurrentUser) -> list[Machine]:
    """All machines — small fixed set, no pagination. Terminals/TABLO need this for context too."""
    machines, _total = await crud_machines.get_multi(db, limit=500)
    return machines


@router.post("/", response_model=MachineRead, status_code=201, operation_id="create_machine")
async def create_machine(db: SessionDep, current_user: AdminUser, body: MachineCreate, request: Request) -> Machine:
    if await crud_posts.get(db, id=body.post_id) is None:
        raise NotFoundException("Post topilmadi.")
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
        message=f"Stanok qo'shildi: {machine.name}",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(machine)
    return machine


@router.get("/{machine_id}", response_model=MachineRead, operation_id="read_machine")
async def read_machine(db: SessionDep, _: CurrentUser, machine_id: int) -> Machine:
    return await crud_machines.get_or_404(db, "Stanok topilmadi.", id=machine_id)


@router.patch("/{machine_id}", response_model=MachineRead, operation_id="update_machine")
async def update_machine(
    db: SessionDep, current_user: AdminUser, machine_id: int, body: MachineUpdate, request: Request
) -> Machine:
    machine = await crud_machines.get_or_404(db, "Stanok topilmadi.", id=machine_id)
    update_data = body.model_dump(exclude_unset=True)
    if "post_id" in update_data and await crud_posts.get(db, id=update_data["post_id"]) is None:
        raise NotFoundException("Post topilmadi.")
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


@router.post("/{machine_id}/pair-code", response_model=MachinePairCode, operation_id="regenerate_machine_pair_code")
async def regenerate_machine_pair_code(
    db: SessionDep, current_user: AdminUser, machine_id: int, request: Request
) -> MachinePairCode:
    """Monoblokni shu stanokka bog'lash uchun bir martalik kod (15 daqiqa).

    Eski qurilma tokeni bekor bo'ladi: monoblok almashtirilganda eskisi keyingi
    kirishda rad etiladi. Bog'langan qurilmada operator beyjik bilan kiradi.
    """
    machine = await crud_machines.get_or_404(db, "Stanok topilmadi.", id=machine_id)
    machine.token_hash = None
    machine.pair_code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
    machine.pair_expires_at = datetime.now(UTC) + PAIR_TTL
    log_action(
        db,
        module="machines",
        action="pair_code_issued",
        user_id=current_user.id,
        entity_type="machine",
        entity_id=machine.id,
        message=f"Terminal ulanish kodi berildi: {machine.name} (eski qurilma bekor)",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(machine)
    return MachinePairCode(
        machine_id=machine.id,
        machine_name=machine.name,
        code=machine.pair_code or "",
        expires_at=machine.pair_expires_at or datetime.now(UTC),
    )


@router.delete("/{machine_id}", response_model=Message, operation_id="delete_machine")
async def delete_machine(db: SessionDep, current_user: AdminUser, machine_id: int, request: Request) -> Message:
    machine = await crud_machines.get_or_404(db, "Stanok topilmadi.", id=machine_id)
    log_action(
        db,
        module="machines",
        action="deleted",
        user_id=current_user.id,
        entity_type="machine",
        entity_id=machine.id,
        message=f"Stanok o'chirildi: {machine.name}",
        ip=client_ip(request),
    )
    await crud_machines.delete(db, id=machine_id)
    return Message(message="Stanok o'chirildi.")
