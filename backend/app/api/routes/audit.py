from datetime import date, datetime, time
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import AdminUser, SessionDep
from app.core.config import TASHKENT_TZ, settings
from app.models import AuditLog, Employee
from app.models.user import User
from app.schemas.audit import AuditLogRead
from app.schemas.common import Paginated

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("/", response_model=Paginated[AuditLogRead], operation_id="read_audit_logs")
async def read_audit_logs(
    db: SessionDep,
    # Butun tizimning audit izi — faqat admin (TZ 10.11). Direktor ishlab
    # chiqarish ko'rsatkichlarini /reports dan oladi, xom hodisa jurnalidan emas.
    _: AdminUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
    module: str | None = None,
    action: str | None = None,
    user_id: int | None = None,
    q: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Paginated[AuditLogRead]:
    query = select(AuditLog)
    if module:
        query = query.where(AuditLog.module == module)
    if action:
        query = query.where(AuditLog.action == action)
    if user_id is not None:
        query = query.where(AuditLog.user_id == user_id)
    if q:
        query = query.where(AuditLog.message.ilike(f"%{q.strip()}%"))
    # Kun chegarasi Toshkent vaqtida — naive datetime UTC deb ketib
    # "bugun" filtri 00:00-05:00 dagi yozuvlarni yo'qotardi
    if date_from is not None:
        query = query.where(AuditLog.created_at >= datetime.combine(date_from, time.min, tzinfo=TASHKENT_TZ))
    if date_to is not None:
        query = query.where(AuditLog.created_at <= datetime.combine(date_to, time.max, tzinfo=TASHKENT_TZ))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                query.add_columns(User.name, Employee.full_name)
                .outerjoin(User, User.id == AuditLog.user_id)
                .outerjoin(Employee, Employee.id == AuditLog.employee_id)
                .order_by(AuditLog.id.desc())
                .offset(skip)
                .limit(limit)
            )
        )
        .tuples()
        .all()
    )
    data = []
    for row, user_name, employee_name in rows:
        item = AuditLogRead.model_validate(row)
        item.user_name = user_name
        item.employee_name = employee_name
        data.append(item)
    return Paginated(data=data, count=total)
