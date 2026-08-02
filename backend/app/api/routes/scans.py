"""Scan registration and undo (TZ 8.4–8.6)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import SessionDep, require_roles
from app.core.ws import ws_manager
from app.crud import log_action
from app.models import Part, PartInstance, Scan, WorkSession
from app.models.enums import POST_ROLES, SessionStatus, UserRole
from app.models.user import User
from app.schemas.terminal import ScanHistoryItem, ScanRequest, ScanResult
from app.services.scanning import ScanRejected, cancel_scan, qr_part_code, record_scan

router = APIRouter(prefix="/scans", tags=["scans"])

TerminalUser = Annotated[User, Depends(require_roles(UserRole.TERMINAL, *POST_ROLES))]


@router.post("/", response_model=ScanResult, operation_id="record_scan")
async def record_scan_endpoint(db: SessionDep, user: TerminalUser, body: ScanRequest) -> ScanResult:
    try:
        outcome = await record_scan(db, user=user, qr_text=body.qr_text, client_event_id=body.client_event_id)
    except ScanRejected as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from None

    if not outcome.duplicate:
        log_action(
            db,
            module="scan",
            action="recorded",
            user_id=user.id,
            employee_id=outcome.scan.employee_id,
            entity_type="scan",
            entity_id=outcome.scan.id,
            message=f"Skan: {outcome.instance.qr_text} — {outcome.part.name}",
            meta={"post_id": outcome.scan.post_id, "machine_id": outcome.scan.machine_id},
        )
    await db.commit()
    for event in outcome.events:
        await ws_manager.publish(
            event["type"], event["payload"], post_id=event.get("post_id"), machine_id=event.get("machine_id")
        )
    return ScanResult(
        scan_id=outcome.scan.id,
        duplicate=outcome.duplicate,
        qr_text=outcome.instance.qr_text,
        part_code=qr_part_code(outcome.instance.qr_text, outcome.part.count),
        part_name=outcome.part.name,
        instance_no=outcome.instance.instance_no,
        qoldiq=outcome.qoldiq,
        scx_file_ids=outcome.scx_file_ids,
        order_stage_completed=outcome.order_stage_completed,
        order_completed=outcome.order_completed,
    )


@router.delete("/{scan_id}", response_model=ScanHistoryItem, operation_id="cancel_scan")
async def cancel_scan_endpoint(db: SessionDep, user: TerminalUser, scan_id: int) -> ScanHistoryItem:
    try:
        scan, events = await cancel_scan(db, user=user, scan_id=scan_id)
    except ScanRejected as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from None
    cancelled_instance = await db.get(PartInstance, scan.instance_id)
    log_action(
        db,
        module="scan",
        action="cancelled",
        user_id=user.id,
        employee_id=scan.employee_id,
        entity_type="scan",
        entity_id=scan.id,
        message=f"Skan bekor qilindi: {cancelled_instance.qr_text if cancelled_instance else scan.instance_id}",
        meta={"post_id": scan.post_id, "machine_id": scan.machine_id},
    )
    await db.commit()
    for event in events:
        await ws_manager.publish(
            event["type"], event["payload"], post_id=event.get("post_id"), machine_id=event.get("machine_id")
        )
    instance = await db.get(PartInstance, scan.instance_id)
    part = await db.get(Part, scan.part_id)
    item = ScanHistoryItem.model_validate(scan)
    if instance and part:
        item.qr_text = instance.qr_text
        item.part_code = qr_part_code(instance.qr_text, part.count)
    return item


@router.get("/recent", response_model=list[ScanHistoryItem], operation_id="read_recent_scans")
async def read_recent_scans(db: SessionDep, user: TerminalUser, limit: int = 50) -> list[ScanHistoryItem]:
    """TARIX block (TZ 8.3.3): last 50 entries of the CURRENT session only."""
    session = (
        await db.execute(
            select(WorkSession)
            .where(
                WorkSession.user_id == user.id,
                WorkSession.status == SessionStatus.ACTIVE,
                WorkSession.is_deleted == False,  # noqa: E712
            )
            .order_by(WorkSession.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if session is None:
        return []
    rows = (
        await db.execute(
            select(Scan, PartInstance.qr_text, Part.count)
            .join(PartInstance, PartInstance.id == Scan.instance_id)
            .join(Part, Part.id == Scan.part_id)
            .where(Scan.session_id == session.id, Scan.is_deleted == False)  # noqa: E712
            .order_by(Scan.id.desc())
            .limit(min(limit, 50))
        )
    ).all()
    items = []
    for scan, qr_text, count in rows:
        item = ScanHistoryItem.model_validate(scan)
        item.qr_text = qr_text
        item.part_code = qr_part_code(qr_text, count)
        items.append(item)
    return items
