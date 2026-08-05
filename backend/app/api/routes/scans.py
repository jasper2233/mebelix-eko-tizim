"""Scan registration and undo (TZ 8.4–8.6)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep, require_roles
from app.core.ws import ws_manager
from app.crud import log_action
from app.models import Part, PartInstance
from app.models.enums import POST_ROLES, UserRole
from app.models.user import User
from app.schemas.terminal import ScanHistoryItem, ScanRequest, ScanResult
from app.services.scanning import (
    ScanRejected,
    cancel_scan,
    finalize_scan,
    log_rejected_scan,
    qr_part_code,
    record_scan,
)

router = APIRouter(prefix="/scans", tags=["scans"])

TerminalUser = Annotated[User, Depends(require_roles(UserRole.TERMINAL, *POST_ROLES))]


@router.post("/", response_model=ScanResult, operation_id="record_scan")
async def record_scan_endpoint(db: SessionDep, user: TerminalUser, body: ScanRequest) -> ScanResult:
    try:
        outcome = await record_scan(db, user=user, qr_text=body.qr_text, client_event_id=body.client_event_id)
    except ScanRejected as exc:
        # Rad etilgan urinish ham logga: kim nimani qayta/noto'g'ri skan qilganini ko'rish uchun
        await log_rejected_scan(db, exc, body.qr_text, user_id=user.id)
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from None

    return await finalize_scan(db, outcome, user_id=user.id)


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
