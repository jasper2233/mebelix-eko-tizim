from datetime import date, datetime, time
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import AdminUser, SessionDep
from app.core.config import TASHKENT_TZ, settings
from app.models import AuditLog, Employee
from app.models.user import User
from app.schemas.audit import AuditLogRead, AuditSummaryRow
from app.schemas.common import Paginated

router = APIRouter(prefix="/audit-logs", tags=["audit"])

# Prodda 19 ta qo'lda yozilgan yozuv `module="scans"` bilan turibdi (kod doim
# `"scan"` yozadi). Tab'da yo'qolib qolmasin — o'qishda bitta modul deb olinadi.
_MODULE_ALIASES: dict[str, tuple[str, ...]] = {"scan": ("scan", "scans")}


def _canon_module(module: str) -> str:
    for canon, variants in _MODULE_ALIASES.items():
        if module in variants:
            return canon
    return module


def _day_bounds(date_from: date | None, date_to: date | None) -> list:
    # Kun chegarasi Toshkent vaqtida — naive datetime UTC deb ketib
    # "bugun" filtri 00:00-05:00 dagi yozuvlarni yo'qotardi
    conds = []
    if date_from is not None:
        conds.append(AuditLog.created_at >= datetime.combine(date_from, time.min, tzinfo=TASHKENT_TZ))
    if date_to is not None:
        conds.append(AuditLog.created_at <= datetime.combine(date_to, time.max, tzinfo=TASHKENT_TZ))
    return conds


@router.get("/summary", response_model=list[AuditSummaryRow], operation_id="read_audit_summary")
async def read_audit_summary(
    db: SessionDep,
    _: AdminUser,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[AuditSummaryRow]:
    """Modul × amal bo'yicha sonlar — sahifa tab'lari shundan quriladi (qo'lda
    yuritiladigan kategoriya ro'yxati o'rniga: bo'sh modul tab bo'lmaydi, yangi
    modul o'zi chiqadi). Sana filtri ro'yxat bilan bir xil, ya'ni tab sonlari
    ko'rinib turgan kunga mos."""
    rows = (
        await db.execute(
            select(AuditLog.module, AuditLog.action, func.count(AuditLog.id))
            .where(*_day_bounds(date_from, date_to))
            .group_by(AuditLog.module, AuditLog.action)
        )
    ).all()
    merged: dict[tuple[str, str], int] = {}
    for module, action, n in rows:
        key = (_canon_module(module), action)
        merged[key] = merged.get(key, 0) + int(n)
    return [
        AuditSummaryRow(module=m, action=a, count=n)
        for (m, a), n in sorted(merged.items(), key=lambda kv: (kv[0][0], -kv[1]))
    ]


@router.get("/", response_model=Paginated[AuditLogRead], operation_id="read_audit_logs")
async def read_audit_logs(
    db: SessionDep,
    # Butun tizimning audit izi — faqat admin. Direktor ishlab
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
        query = query.where(AuditLog.module.in_(_MODULE_ALIASES.get(module, (module,))))
    if action:
        query = query.where(AuditLog.action == action)
    if user_id is not None:
        query = query.where(AuditLog.user_id == user_id)
    if q:
        query = query.where(AuditLog.message.ilike(f"%{q.strip()}%"))
    query = query.where(*_day_bounds(date_from, date_to))

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
