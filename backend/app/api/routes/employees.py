from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, or_, select

from app.api.deps import AdminUser, SessionDep, StaffReadUser, client_ip
from app.api.routes._shared import drop_forbidden_nulls
from app.core.config import settings
from app.core.exceptions import DuplicateValueException, NotFoundException
from app.core.utils import queue
from app.crud import crud_employees, crud_posts, crud_users, log_action
from app.models import Employee
from app.models.enums import EmployeeStatus, UserRole
from app.schemas.common import Message, Paginated
from app.schemas.employees import EmployeeCreate, EmployeeRead, EmployeeUpdate
from app.services.scanning import end_employee_sessions
from app.tasks import printing_agents

router = APIRouter(prefix="/employees", tags=["employees"])

#: PATCH da aniq `null` faqat shu ustunlarga ruxsat (qolganlari NOT NULL — 500 berardi).
_NULLABLE_FIELDS = ("phone", "position", "user_id")


async def _validate_post_ids(db: SessionDep, post_ids: list[int]) -> None:
    if not post_ids:
        return
    posts, _ = await crud_posts.get_multi(db, limit=100)
    valid = {p.id for p in posts}
    unknown = set(post_ids) - valid
    if unknown:
        raise NotFoundException(f"Post topilmadi: {sorted(unknown)}")


async def _validate_user_link(db: SessionDep, user_id: int | None, employee_id: int | None = None) -> None:
    """Hodimni kirish hisobiga bog'lash qoidalari.

    Qurilma va post hisoblari (TERMINAL/TABLO va POST_ROLES) ODAM EMAS — ular
    monoblokning o'zi va smena qaysi hisob nomidan yozilishini hal qiladigan
    texnik hisoblar (`login._terminal_user`). Odam ularga bog'lanmaydi.

    Bitta hisob ikki hodimga tegishli bo'lolmaydi: `ix_employee_user_id` PARTIAL
    UNIQUE indeksi buni baribir rad etardi, lekin xato xabari tushunarsiz bo'lardi.
    """
    if user_id is None:
        return
    user = await crud_users.get(db, id=user_id)
    if user is None:
        raise NotFoundException("Kirish hisobi topilmadi.")
    role = UserRole(user.role)
    # Post rolidagi SHAXSIY hisobga ruxsat: skanersiz postda (ARRA) xodim aynan
    # shu hisob bilan kiradi va smenasi o'ziga yoziladi. Qurilma hisobi va
    # `seed_defaults` yaratgan TEXNIK hisob esa odam emas.
    if role in (UserRole.TERMINAL, UserRole.TABLO) or user.is_system:
        raise DuplicateValueException(f"{user.username} — qurilma yoki texnik hisob, unga hodim biriktirilmaydi.")
    query = select(Employee.full_name).where(
        Employee.user_id == user_id,
        Employee.is_deleted == False,  # noqa: E712
    )
    if employee_id is not None:
        query = query.where(Employee.id != employee_id)
    taken = (await db.execute(query)).scalar_one_or_none()
    if taken is not None:
        raise DuplicateValueException(f"Bu hisob allaqachon {taken} ga biriktirilgan.")


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
        # Beyjik ATAYLAB aniq moslik bilan: skaner har doim to'liq UUID beradi,
        # qismiy qidiruv esa `EmployeeRead` yashirgan `badge_id` ni prefiks-prefiks
        # tiklab olish kanali bo'lardi (~400 GET bilan to'liq beyjik chiqadi).
        query = query.where(or_(Employee.full_name.ilike(f"%{search.strip()}%"), Employee.badge_id == search.strip()))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(Employee.full_name).offset(skip).limit(limit))).scalars().all()
    return Paginated(data=[EmployeeRead.model_validate(e) for e in rows], count=total)


@router.post("/", response_model=EmployeeRead, status_code=201, operation_id="create_employee")
async def create_employee(db: SessionDep, current_user: AdminUser, body: EmployeeCreate, request: Request) -> Employee:
    await _validate_post_ids(db, body.assigned_post_ids)
    await _validate_user_link(db, body.user_id)
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


@router.patch("/{employee_id}", response_model=EmployeeRead, operation_id="update_employee")
async def update_employee(
    db: SessionDep, current_user: AdminUser, employee_id: int, body: EmployeeUpdate, request: Request
) -> Employee:
    employee = await crud_employees.get_or_404(db, "Hodim topilmadi.", id=employee_id)
    update_data = drop_forbidden_nulls(body.model_dump(exclude_unset=True), _NULLABLE_FIELDS)
    if "assigned_post_ids" in update_data:
        await _validate_post_ids(db, update_data["assigned_post_ids"])
    if "user_id" in update_data:
        await _validate_user_link(db, update_data["user_id"], employee_id=employee.id)
    for field, value in update_data.items():
        setattr(employee, field, value)
    # Nofaol hodimning ochiq smenasi ish markazini to'xtatib qo'yadi (E006) —
    # holat o'zgarishi bilan bitta tranzaksiyada yopiladi
    closed = await end_employee_sessions(db, employee.id) if employee.status != EmployeeStatus.ACTIVE else 0
    log_action(
        db,
        module="employees",
        action="updated",
        message=f"Nofaol qilindi, {closed} ta ochiq smena yopildi" if closed else None,
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
    """Lost badge: old badge stops working immediately, history stays on the same employee."""
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
        # Faqat DUM: `meta` ni `AuditLogRead` xom holda qaytaradi, ya'ni to'liq
        # eski beyjik UUID'i jurnalda ochiq matn bo'lib qolardi. Olti belgi ikki
        # yozuvni bog'lashga yetadi.
        meta={"old_badge_tail": old_badge[-6:]},
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(employee)
    return employee


@router.post("/{employee_id}/print", response_model=Message, operation_id="print_employee_badge")
async def print_employee_badge(
    db: SessionDep,
    current_user: AdminUser,
    employee_id: int,
    request: Request,
    agent_id: int | None = None,
) -> Message:
    """Beyjikni chop etish navbatiga qo'yadi — detal cheki bilan bir xil zanjir.

    Beyjikda ish markazi YO'Q (ofisdan chop etiladi), shuning uchun printer
    ATAYLAB tanlanadi: `agent_id` berilsa o'sha, berilmasa — chop eta oladigan
    yagona agent. Bir nechta printer bo'lsa 422 va ro'yxat qaytadi.

    Ilgari job manzilsiz qo'yilardi va uni umumiy navbatdan birinchi ulgurgan
    printer olardi — beyjik qaysi tsex printeridan chiqishi tasodif edi.
    """
    employee = await crud_employees.get_or_404(db, "Hodim topilmadi.", id=employee_id)
    if queue.pool is None:
        # 503, 403 emas: navbat (arq/Redis) o'chgani infratuzilma nosozligi,
        # operatorning huquqi bilan aloqasi yo'q.
        raise HTTPException(status_code=503, detail="Chop etish navbati ishlamayapti. Adminga murojaat qiling.")

    agents = await printing_agents(db)
    if not agents:
        raise HTTPException(
            status_code=422,
            detail="Chop etadigan printer yo'q. /printers sahifasida agentni ulang.",
        )
    if agent_id is not None:
        target = next((a for a in agents if a.id == agent_id), None)
        if target is None:
            raise HTTPException(status_code=422, detail="Bunday printer topilmadi yoki chop eta olmaydi.")
    elif len(agents) == 1:
        target = agents[0]
    else:
        nomlar = ", ".join(f"{a.name} (id={a.id})" for a in agents)
        raise HTTPException(
            status_code=422,
            detail=f"Bir nechta printer bor — qaysi biridan chiqarishni tanlang: {nomlar}",
        )
    await queue.pool.enqueue_job("print_badge", employee.id, target.id)
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
    # Ilgari bu yerda POST ROLI hisobiga bog'langan yozuvni o'chirishga to'siq bor
    # edi — eski avtomat mirror'lar uchun. Mirror'lar `a9e14b7c2d63` da butunlay
    # o'chirildi va endi post rolidagi bog'lam BOSHQA narsani bildiradi: skaneri
    # yo'q postda ishlaydigan odamning SHAXSIY hisobi. To'siq qolganda haqiqiy
    # hodimni o'chirib bo'lmasdi.
    closed = await end_employee_sessions(db, employee.id)
    log_action(
        db,
        module="employees",
        action="deleted",
        user_id=current_user.id,
        entity_type="employee",
        entity_id=employee.id,
        message=f"Hodim o'chirildi: {employee.full_name}" + (f" ({closed} ta ochiq smena yopildi)" if closed else ""),
        ip=client_ip(request),
    )
    await crud_employees.delete(db, id=employee_id)
    return Message(message="Hodim o'chirildi.")
