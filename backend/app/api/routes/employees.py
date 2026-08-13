from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, or_, select

from app.api.deps import AdminUser, SessionDep, StaffReadUser, client_ip
from app.core.config import settings
from app.core.exceptions import ForbiddenException, NotFoundException
from app.crud import crud_employees, crud_posts, log_action
from app.models import Employee
from app.models.enums import EmployeeStatus
from app.schemas.common import Message, Paginated
from app.schemas.employees import EmployeeCreate, EmployeeRead, EmployeeUpdate

router = APIRouter(prefix="/employees", tags=["employees"])


async def _validate_post_ids(db: SessionDep, post_ids: list[int]) -> None:
    if not post_ids:
        return
    posts, _ = await crud_posts.get_multi(db, limit=100)
    valid = {p.id for p in posts}
    unknown = set(post_ids) - valid
    if unknown:
        raise NotFoundException(f"Post topilmadi: {sorted(unknown)}")


@router.get("/", response_model=Paginated[EmployeeRead], operation_id="read_employees")
async def read_employees(
    db: SessionDep,
    _: StaffReadUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
    search: str | None = None,
    status: EmployeeStatus | None = None,
) -> Paginated[EmployeeRead]:
    query = select(Employee).where(Employee.is_deleted == False)  # noqa: E712
    if status is not None:
        query = query.where(Employee.status == status)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(or_(Employee.full_name.ilike(pattern), Employee.badge_id.ilike(pattern)))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(Employee.full_name).offset(skip).limit(limit))).scalars().all()
    return Paginated(data=[EmployeeRead.model_validate(e) for e in rows], count=total)


@router.post("/", response_model=EmployeeRead, status_code=201, operation_id="create_employee")
async def create_employee(db: SessionDep, current_user: AdminUser, body: EmployeeCreate, request: Request) -> Employee:
    await _validate_post_ids(db, body.assigned_post_ids)
    employee = Employee(**body.model_dump(), badge_id=str(uuid4()))
    db.add(employee)
    await db.flush()
    log_action(
        db,
        module="employees",
        action="created",
        user_id=current_user.id,
        entity_type="employee",
        entity_id=employee.id,
        message=f"Hodim qo'shildi: {employee.full_name}",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(employee)
    return employee


@router.get("/{employee_id}", response_model=EmployeeRead, operation_id="read_employee")
async def read_employee(db: SessionDep, _: StaffReadUser, employee_id: int) -> Employee:
    return await crud_employees.get_or_404(db, "Hodim topilmadi.", id=employee_id)


@router.patch("/{employee_id}", response_model=EmployeeRead, operation_id="update_employee")
async def update_employee(
    db: SessionDep, current_user: AdminUser, employee_id: int, body: EmployeeUpdate, request: Request
) -> Employee:
    employee = await crud_employees.get_or_404(db, "Hodim topilmadi.", id=employee_id)
    update_data = body.model_dump(exclude_unset=True)
    if "assigned_post_ids" in update_data and update_data["assigned_post_ids"] is not None:
        await _validate_post_ids(db, update_data["assigned_post_ids"])
    for field, value in update_data.items():
        setattr(employee, field, value)
    log_action(
        db,
        module="employees",
        action="updated",
        user_id=current_user.id,
        entity_type="employee",
        entity_id=employee.id,
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(employee)
    return employee


@router.post("/{employee_id}/badge", response_model=EmployeeRead, operation_id="regenerate_badge")
async def regenerate_badge(db: SessionDep, current_user: AdminUser, employee_id: int, request: Request) -> Employee:
    """Lost badge (TZ 4.2): old badge stops working immediately, history stays on the same employee."""
    employee = await crud_employees.get_or_404(db, "Hodim topilmadi.", id=employee_id)
    old_badge = employee.badge_id
    employee.badge_id = str(uuid4())
    log_action(
        db,
        module="employees",
        action="badge_regenerated",
        user_id=current_user.id,
        entity_type="employee",
        entity_id=employee.id,
        message="Beyjik yangilandi (eskisi bloklandi)",
        meta={"old_badge": old_badge},
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(employee)
    return employee


@router.post("/{employee_id}/print", response_model=Message, operation_id="print_employee_badge")
async def print_employee_badge(db: SessionDep, current_user: AdminUser, employee_id: int, request: Request) -> Message:
    """Beyjikni chop etish navbatiga qo'yadi — detal cheki bilan bir xil zanjir."""
    employee = await crud_employees.get_or_404(db, "Hodim topilmadi.", id=employee_id)
    from app.core.utils import queue

    if queue.pool is None:
        raise ForbiddenException("Chop etish navbati ishlamayapti. Adminga murojaat qiling.")
    await queue.pool.enqueue_job("print_badge", employee.id)
    log_action(
        db,
        module="print",
        action="badge_queued",
        user_id=current_user.id,
        entity_type="employee",
        entity_id=employee.id,
        message=f"Beyjik chop etishga yuborildi: {employee.full_name}",
        ip=client_ip(request),
    )
    await db.commit()
    return Message(message=f"{employee.full_name} beyjigi printerga yuborildi.")


@router.delete("/{employee_id}", response_model=Message, operation_id="delete_employee")
async def delete_employee(db: SessionDep, current_user: AdminUser, employee_id: int, request: Request) -> Message:
    employee = await crud_employees.get_or_404(db, "Hodim topilmadi.", id=employee_id)
    # `user_id` li yozuvlar — eski avtomat mirror'lar ("arrachi", "omborchi").
    # Ular arxiv: yangi mirror yaratilmaydi (`c7e2b4f81d39`), lekin ularda
    # haqiqiy skan tarixi bor va o'chirilsa mahsuldorlik hisobotidan tushardi.
    if employee.user_id is not None:
        raise ForbiddenException(
            f"{employee.full_name} — eski operator hisobi yozuvi, o'chirib bo'lmaydi: "
            "unda skan tarixi bor. U allaqachon NOFAOL va ro'yxatda faqat tarix uchun turibdi."
        )
    log_action(
        db,
        module="employees",
        action="deleted",
        user_id=current_user.id,
        entity_type="employee",
        entity_id=employee.id,
        message=f"Hodim o'chirildi: {employee.full_name}",
        ip=client_ip(request),
    )
    await crud_employees.delete(db, id=employee_id)
    return Message(message="Hodim o'chirildi.")
