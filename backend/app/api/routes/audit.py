from datetime import date, datetime, time
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.api.deps import SessionDep, StaffReadUser
from app.core.config import settings
from app.models import AuditLog
from app.schemas.common import Paginated

router = APIRouter(prefix="/audit-logs", tags=["audit"])


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    employee_id: int | None
    module: str
    action: str
    entity_type: str | None
    entity_id: int | None
    message: str | None
    meta: dict[str, Any]
    ip: str | None
    created_at: datetime


@router.get("/", response_model=Paginated[AuditLogRead], operation_id="read_audit_logs")
async def read_audit_logs(
    db: SessionDep,
    _: StaffReadUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
    module: str | None = None,
    action: str | None = None,
    user_id: int | None = None,
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
    if date_from is not None:
        query = query.where(AuditLog.created_at >= datetime.combine(date_from, time.min))
    if date_to is not None:
        query = query.where(AuditLog.created_at <= datetime.combine(date_to, time.max))

    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(AuditLog.id.desc()).offset(skip).limit(limit))).scalars().all()
    return Paginated(data=[AuditLogRead.model_validate(r) for r in rows], count=total)
