from fastapi import APIRouter, Request

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.core.exceptions import NotFoundException
from app.crud import crud_machines, crud_posts, log_action
from app.models import Machine
from app.schemas.common import Message
from app.schemas.machines import MachineCreate, MachineRead, MachineUpdate

router = APIRouter(prefix="/machines", tags=["machines"])


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
        ip=request.client.host if request.client else None,
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
        ip=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(machine)
    return machine


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
        ip=request.client.host if request.client else None,
    )
    await crud_machines.delete(db, id=machine_id)
    return Message(message="Stanok o'chirildi.")
