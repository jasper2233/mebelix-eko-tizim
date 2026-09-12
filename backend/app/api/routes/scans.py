"""Scan registration and undo."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import SessionDep, require_roles
from app.core.config import TASHKENT_TZ
from app.core.ws import ws_manager
from app.crud import log_action
from app.models import Order, Part, PartInstance, WasteItem
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
    scan_error,
)

router = APIRouter(prefix="/scans", tags=["scans"])

TerminalUser = Annotated[User, Depends(require_roles(UserRole.TERMINAL, *POST_ROLES))]


@router.post("/", response_model=ScanResult, operation_id="record_scan")
async def record_scan_endpoint(db: SessionDep, user: TerminalUser, body: ScanRequest) -> ScanResult:
    # QOLDIQ cheki skanlandi: bu ish bosqichi emas — skan yozilmaydi, operator
    # qoldiq HAQIDA to'liq ma'lumot oladi (qaysi buyurtma, qaysi list, o'lcham).
    # 422 + "ATX" kodi bilan: frontend buni xato emas, ma'lumot deb ko'rsatadi.
    if body.qr_text.startswith("ATX-"):
        w = (
            await db.execute(
                select(WasteItem).where(
                    WasteItem.qr_text == body.qr_text,
                    WasteItem.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if w is None:
            raise scan_error("E002", "Bunday qoldiq cheki ro'yxatda yo'q.")
        order = await db.get(Order, w.order_id)
        chek = (
            w.label_printed_at.astimezone(TASHKENT_TZ).strftime("%d-%m %H:%M")
            if w.label_printed_at
            else "chiqarilmagan"
        )
        raise scan_error(
            "ATX",
            (
                f"QOLDIQ: {w.length:g} x {w.width:g} mm, {w.material_name}. "
                f"Buyurtma {order.number if order else '?'}"
                f"{' (' + order.project_name + ')' if order and order.project_name else ''}, "
                f"list {w.sheet_no}. Chek: {chek}."
            ),
        )
    # `user.id` SHU YERDA: `record_scan_at` `client_event_id` unikal indeksi poygasida
    # ScanRejected'dan OLDIN o'zi `rollback` qiladi (`scanning.py`), rollback esa identity
    # map'dagi hamma obyektni expire qiladi — `except` ichida `user.id` ni o'qish lazy IO
    # talab qilib `MissingGreenlet` -> 500 berardi (o'lchangan), ya'ni operator 422 o'rniga
    # "Serverda xatolik" ko'rardi va rad etilgan skan Loglarga umuman tushmasdi.
    user_id = user.id
    try:
        outcome = await record_scan(db, user=user, qr_text=body.qr_text, client_event_id=body.client_event_id)
    except ScanRejected as exc:
        # Rad etilgan urinish ham logga: kim nimani qayta/noto'g'ri skan qilganini ko'rish uchun
        await log_rejected_scan(db, exc, body.qr_text, user_id=user_id)
        raise scan_error(exc.code, exc.message) from None

    return await finalize_scan(db, outcome, user_id=user_id)


@router.delete("/{scan_id}", response_model=ScanHistoryItem, operation_id="cancel_scan")
async def cancel_scan_endpoint(db: SessionDep, user: TerminalUser, scan_id: int) -> ScanHistoryItem:
    try:
        scan, events = await cancel_scan(db, user=user, scan_id=scan_id)
    except ScanRejected as exc:
        await db.rollback()
        raise scan_error(exc.code, exc.message) from None
    instance = await db.get(PartInstance, scan.instance_id)
    log_action(
        db,
        module="scan",
        action="cancelled",
        user_id=user.id,
        employee_id=scan.employee_id,
        entity_type="scan",
        entity_id=scan.id,
        message=f"Skan bekor qilindi: {instance.qr_text if instance else scan.instance_id}",
        meta={"post_id": scan.post_id, "machine_id": scan.machine_id},
    )
    await db.commit()
    for event in events:
        await ws_manager.publish(
            event["type"], event["payload"], post_id=event.get("post_id"), machine_id=event.get("machine_id")
        )
    part = await db.get(Part, scan.part_id)
    item = ScanHistoryItem.model_validate(scan)
    if instance and part:
        item.qr_text = instance.qr_text
        item.part_code = qr_part_code(instance.qr_text, part.count)
    return item
