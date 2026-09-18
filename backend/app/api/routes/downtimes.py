"""Terminal: stanok to'xtashi sababini smenadagi hodim kiritadi (docs/12-oee.md §7).

Oyna terminalda O'ZI chiqadi — doimiy tugma yo'q (2026-08-21 dagi modul 1366×768 ekranga
sig'magani uchun qaytarilgan). Qulf tugmasi esa avval sababni so'raydi, keyin qulflaydi.
"""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.api.deps import SessionDep, client_ip
from app.api.routes.terminal import TerminalCtx, TerminalUser
from app.core.exceptions import NotFoundException
from app.crud import log_action
from app.models import Downtime, DowntimeReason, Machine, WorkSession
from app.models.enums import DowntimeKind
from app.schemas.downtimes import DowntimeRead, DowntimeReasonInput, DowntimeReasonRead
from app.services.downtimes import close_open_locks, sync_machine
from app.services.scanning import crew_sessions, scan_error

router = APIRouter(prefix="/terminal", tags=["terminal"])


async def _anchor(db: SessionDep, machine: Machine) -> WorkSession:
    """Sababni kim kiritadi — brigadaning langar smenasi (skan ham unga yoziladi)."""
    crew = await crew_sessions(db, machine.id)
    if not crew:
        raise scan_error("E005", "Aktiv smena yo'q. Terminalda ismingizni bosing yoki beyjikni skanerlang.")
    return crew[0]


async def _reason(db: SessionDep, body: DowntimeReasonInput) -> DowntimeReason:
    reason = await db.get(DowntimeReason, body.reason_id)
    if reason is None or reason.is_deleted or not reason.is_active:
        raise NotFoundException("Sabab topilmadi.")
    if reason.needs_note and not body.note:
        raise HTTPException(status_code=422, detail=f"«{reason.name}» uchun qisqacha izoh yozing.")
    return reason


@router.get("/downtime-reasons", response_model=list[DowntimeReasonRead], operation_id="read_terminal_downtime_reasons")
async def read_terminal_downtime_reasons(db: SessionDep, _: TerminalUser) -> list[DowntimeReason]:
    """Faol sabablar — rejasizlar oldin (odatda shular so'raladi), keyin admin tartibi."""
    return list(
        (
            await db.execute(
                select(DowntimeReason)
                .where(DowntimeReason.is_deleted == False, DowntimeReason.is_active == True)  # noqa: E712
                .order_by(DowntimeReason.is_planned, DowntimeReason.order_index, DowntimeReason.id)
            )
        )
        .scalars()
        .all()
    )


@router.get("/downtimes/pending", response_model=list[DowntimeRead], operation_id="read_pending_downtimes")
async def read_pending_downtimes(db: SessionDep, _: TerminalUser, ctx: TerminalCtx) -> list[Downtime]:
    """Sababi kiritilmagan to'xtashlar — terminal oynasi shundan chiqadi.

    GET bo'lsa ham YOZADI: sariq chiroq chegaradan oshishi uchun yangi Pico hodisasi kelmaydi
    (holat o'zgarmagan), ya'ni to'xtash yozuvi aynan so'ralgan paytda paydo bo'lishi kerak.
    Yozuv idempotent (`services/downtimes.sync_machine`).

    Faqat SHU SMENAGA tegishlilari: smena boshlanishidan keyin tugagan yoki hali davom
    etayotgan. Oldingi smenadagi to'xtash sababini hozirgi odam bilmaydi — sababsiz qoladi.
    Smena ochilmagan bo'lsa bo'sh ro'yxat: kiritadigan odam yo'q."""
    machine, _post = ctx
    crew = await crew_sessions(db, machine.id)
    if not crew:
        return []
    await sync_machine(db, machine.id, datetime.now(UTC))
    await db.commit()
    return list(
        (
            await db.execute(
                select(Downtime)
                .where(
                    Downtime.machine_id == machine.id,
                    Downtime.kind != DowntimeKind.LOCK,
                    Downtime.reason_id.is_(None),
                    Downtime.is_deleted == False,  # noqa: E712
                    (Downtime.ended_at.is_(None)) | (Downtime.ended_at >= crew[0].created_at),
                )
                .order_by(Downtime.started_at)
            )
        )
        .scalars()
        .all()
    )


@router.post("/downtimes/{downtime_id}/reason", response_model=DowntimeRead, operation_id="set_downtime_reason")
async def set_downtime_reason(
    db: SessionDep, user: TerminalUser, ctx: TerminalCtx, downtime_id: int, body: DowntimeReasonInput, request: Request
) -> Downtime:
    machine, _post = ctx
    downtime = await db.get(Downtime, downtime_id)
    if downtime is None or downtime.is_deleted or downtime.machine_id != machine.id:
        raise NotFoundException("To'xtash topilmadi.")
    reason = await _reason(db, body)
    anchor = await _anchor(db, machine)
    downtime.reason_id = reason.id
    downtime.note = body.note or None
    downtime.employee_id = anchor.employee_id
    downtime.reason_at = datetime.now(UTC)
    log_action(
        db,
        module="downtime",
        action="reason_set",
        user_id=user.id,
        employee_id=anchor.employee_id,
        entity_type="downtime",
        entity_id=downtime.id,
        message=f"To'xtash sababi: {reason.name} — {machine.name}",
        ip=client_ip(request),
    )
    await db.commit()
    return downtime


@router.post("/downtimes/lock", response_model=DowntimeRead, operation_id="lock_with_downtime_reason")
async def lock_with_downtime_reason(
    db: SessionDep, user: TerminalUser, ctx: TerminalCtx, body: DowntimeReasonInput, request: Request
) -> Downtime:
    """Qulf tugmasi: hodim ketishdan oldin sababni aytadi, keyin ekran qulflanadi.

    To'xtash shu paytdan beyjik bilan qulf ochilguncha (`scanning.open_badge_session`).
    Shu oraliqda boshlangan Pico to'xtashi sababni shundan oladi va qayta so'ralmaydi."""
    machine, _post = ctx
    reason = await _reason(db, body)
    anchor = await _anchor(db, machine)
    now = datetime.now(UTC)
    await close_open_locks(db, machine.id, now)
    downtime = Downtime(
        machine_id=machine.id,
        kind=DowntimeKind.LOCK,
        start_key=f"lock-{uuid4().hex[:24]}",
        started_at=now,
    )
    downtime.reason_id = reason.id
    downtime.note = body.note or None
    downtime.employee_id = anchor.employee_id
    downtime.reason_at = now
    db.add(downtime)
    await db.flush()
    log_action(
        db,
        module="downtime",
        action="locked",
        user_id=user.id,
        employee_id=anchor.employee_id,
        entity_type="downtime",
        entity_id=downtime.id,
        message=f"Qulflandi: {reason.name} — {machine.name}",
        ip=client_ip(request),
    )
    await db.commit()
    return downtime
