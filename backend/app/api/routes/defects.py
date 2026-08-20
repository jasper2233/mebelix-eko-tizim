"""Brak: terminalda belgilash, menejerda tasdiqlash (OEE Quality)."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select

from app.api.deps import SessionDep, client_ip, require_roles
from app.core.config import settings
from app.core.exceptions import ForbiddenException, NotFoundException
from app.crud import log_action
from app.models import (
    Defect,
    Employee,
    Machine,
    Order,
    Part,
    PartInstance,
    PartRoute,
    Post,
    Scan,
)
from app.models.enums import POST_ROLES, DefectStatus, UserRole
from app.models.user import User
from app.schemas.common import Message, Paginated
from app.schemas.defects import DefectApprove, DefectCreate, DefectRead, DefectScanRow
from app.services import defects as defect_service
from app.services.scanning import active_session, resolve_terminal

router = APIRouter(prefix="/defects", tags=["defects"])

TerminalUser = Annotated[User, Depends(require_roles(UserRole.TERMINAL, *POST_ROLES))]
ReviewUser = Annotated[User, Depends(require_roles(UserRole.MANAGER, UserRole.DIRECTOR))]


async def _read(db: SessionDep, defect: Defect) -> DefectRead:
    """Menejer ekrani uchun to'liq kartochka: detal, marshrut va skan tarixi.

    Tarix ATAYLAB to'liq: "kim chiqargan" savoliga javob shu yerda va uni
    taxmin bilan emas, yozuv bilan berish kerak.
    """
    instance = await db.get(PartInstance, defect.instance_id)
    part = await db.get(Part, instance.part_id) if instance else None
    order = await db.get(Order, instance.order_id) if instance else None
    found_post = await db.get(Post, defect.found_post_id)
    found_by = await db.get(Employee, defect.found_by_id) if defect.found_by_id else None

    route: list[str] = []
    if part is not None:
        route = list(
            (
                await db.execute(
                    select(Post.name)
                    .select_from(PartRoute)
                    .join(Post, Post.id == PartRoute.post_id)
                    .where(PartRoute.part_id == part.id, PartRoute.is_deleted == False)  # noqa: E712
                    .order_by(PartRoute.seq)
                )
            )
            .scalars()
            .all()
        )

    history: list[DefectScanRow] = []
    if instance is not None:
        rows = (
            await db.execute(
                select(Post.name, Employee.full_name, Machine.name, Scan.created_at)
                .select_from(Scan)
                .join(Post, Post.id == Scan.post_id)
                .outerjoin(Employee, Employee.id == Scan.employee_id)
                .outerjoin(Machine, Machine.id == Scan.machine_id)
                .where(
                    Scan.instance_id == instance.id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .order_by(Scan.created_at)
            )
        ).all()
        history = [DefectScanRow(post_name=p, employee_name=e, machine_name=m, at=at) for p, e, m, at in rows]

    suggested_post, suggested_employee = await defect_service.suggest_blame(db, instance) if instance else (None, None)
    blamed_post = await db.get(Post, defect.blamed_post_id) if defect.blamed_post_id else None
    blamed_employee = await db.get(Employee, defect.blamed_employee_id) if defect.blamed_employee_id else None
    restart_post = await db.get(Post, defect.restart_post_id) if defect.restart_post_id else None
    new_instance = await db.get(PartInstance, defect.new_instance_id) if defect.new_instance_id else None

    return DefectRead(
        id=defect.id,
        status=DefectStatus(defect.status),
        reason=defect.reason,
        created_at=defect.created_at,
        order_number=order.number if order else "—",
        part_name=part.name if part else "—",
        qr_text=instance.qr_text if instance else "—",
        found_post_name=found_post.name if found_post else "—",
        found_by_name=found_by.full_name if found_by else None,
        route=route,
        history=history,
        suggested_post_id=defect.blamed_post_id or suggested_post,
        suggested_employee_id=defect.blamed_employee_id or suggested_employee,
        blamed_post_name=blamed_post.name if blamed_post else None,
        blamed_employee_name=blamed_employee.full_name if blamed_employee else None,
        restart_post_name=restart_post.name if restart_post else None,
        new_qr_text=new_instance.qr_text if new_instance else None,
        reviewed_at=defect.reviewed_at,
    )


@router.post("/", response_model=Message, status_code=201, operation_id="report_defect")
async def report_defect(db: SessionDep, user: TerminalUser, body: DefectCreate, request: Request) -> Message:
    """Operator brakni belgilaydi. Detal ishlab chiqarishga QAYTMAYDI — menejer tasdig'i kerak."""
    machine, post = await resolve_terminal(db, user)
    instance = (
        await db.execute(
            select(PartInstance).where(
                PartInstance.qr_text == body.qr_text.strip(),
                PartInstance.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if instance is None:
        raise NotFoundException("Bu QR bo'yicha detal topilmadi.")
    open_defect = (
        await db.execute(
            select(Defect).where(
                Defect.instance_id == instance.id,
                Defect.status == DefectStatus.PENDING,
                Defect.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if open_defect is not None:
        raise ForbiddenException("Bu detal bo'yicha brak allaqachon yuborilgan — menejer ko'rib chiqmoqda.")

    session = await active_session(db, machine)
    defect = Defect(
        instance_id=instance.id,
        found_post_id=post.id,
        found_by_id=session.employee_id if session else None,
        reason=body.reason.strip(),
    )
    db.add(defect)
    await db.flush()
    log_action(
        db,
        module="oee",
        action="defect_reported",
        user_id=user.id,
        entity_type="defect",
        entity_id=defect.id,
        message=f"Brak: {instance.qr_text} — {defect.reason}",
        ip=client_ip(request),
    )
    await db.commit()
    return Message(message="Brak yuborildi. Menejer ko'rib chiqadi.")


@router.get("/", response_model=Paginated[DefectRead], operation_id="read_defects")
async def read_defects(
    db: SessionDep,
    _: ReviewUser,
    status: DefectStatus | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=settings.MAX_PAGE_SIZE)] = settings.DEFAULT_PAGE_SIZE,
) -> Paginated[DefectRead]:
    query = select(Defect).where(Defect.is_deleted == False)  # noqa: E712
    if status is not None:
        query = query.where(Defect.status == status)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = (await db.execute(query.order_by(Defect.created_at.desc()).offset(skip).limit(limit))).scalars().all()
    return Paginated(data=[await _read(db, d) for d in rows], count=total)


@router.post("/{defect_id}/approve", response_model=DefectRead, operation_id="approve_defect")
async def approve_defect(
    db: SessionDep, user: ReviewUser, defect_id: int, body: DefectApprove, request: Request
) -> DefectRead:
    """Tasdiqlaydi va detalni qayta ishlab chiqarishga yuboradi."""
    defect = await _pending(db, defect_id)
    try:
        created = await defect_service.approve(
            db,
            defect=defect,
            blamed_post_id=body.blamed_post_id,
            blamed_employee_id=body.blamed_employee_id,
            restart_post_id=body.restart_post_id,
            user_id=user.id,
        )
    except ValueError as err:
        raise ForbiddenException(str(err)) from err
    log_action(
        db,
        module="oee",
        action="defect_approved",
        user_id=user.id,
        entity_type="defect",
        entity_id=defect.id,
        message=("Yangi nusxa yaratildi: " + created.qr_text) if created else "Detal qayta ishlashga qaytdi",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(defect)
    return await _read(db, defect)


@router.post("/{defect_id}/reject", response_model=DefectRead, operation_id="reject_defect")
async def reject_defect(db: SessionDep, user: ReviewUser, defect_id: int, request: Request) -> DefectRead:
    """Rad etadi — detal yaroqli, ko'rsatkichga ta'sir qilmaydi."""
    defect = await _pending(db, defect_id)
    defect.status = DefectStatus.REJECTED
    defect.reviewed_by_id = user.id
    defect.reviewed_at = datetime.now(UTC)
    log_action(
        db,
        module="oee",
        action="defect_rejected",
        user_id=user.id,
        entity_type="defect",
        entity_id=defect.id,
        message="Brak rad etildi",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(defect)
    return await _read(db, defect)


async def _pending(db: SessionDep, defect_id: int) -> Defect:
    """Ko'rib chiqilmagan brak yozuvi. Ikki marta tasdiqlash QAYTA ishlab
    chiqarishni ikki marta ishga tushirardi — yangi nusxa ham ikkita bo'lardi."""
    defect = await db.get(Defect, defect_id)
    if defect is None or defect.is_deleted:
        raise NotFoundException("Brak yozuvi topilmadi.")
    if DefectStatus(defect.status) != DefectStatus.PENDING:
        raise ForbiddenException("Bu brak allaqachon ko'rib chiqilgan.")
    return defect
