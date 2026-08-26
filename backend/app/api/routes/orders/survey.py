"""Mijoz anketasi va o'lchov varag'i: xonalar, rasmlar (`Order.survey` JSONB)."""

import contextlib
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from sqlalchemy import func, select

from app.api.deps import ManagerUser, SessionDep, client_ip
from app.core.config import upload_root
from app.core.exceptions import ForbiddenException, NotFoundException
from app.crud import log_action
from app.models import OrderFile
from app.models.enums import FileKind, OrderStatus
from app.schemas.common import Message
from app.schemas.orders import OrderFileRead, OrderSurvey

from ._common import _get_order

router = APIRouter()


@router.put("/{order_id}/survey", response_model=Message, operation_id="save_order_survey")
async def save_order_survey(
    db: SessionDep, current_user: ManagerUser, order_id: int, body: OrderSurvey, request: Request
) -> Message:
    """Mijoz anketasi va o'lchov varag'ini saqlaydi (TZ 6.2, qog'oz forma o'rniga).

    Butun anketa bir butun sifatida yoziladi — menejer to'ldirib boradi, texnolog o'qiydi.
    """
    order = await _get_order(db, order_id)
    if order.status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        raise ForbiddenException("Yakunlangan yoki bekor qilingan buyurtma anketasini o'zgartirib bo'lmaydi.")
    order.survey = body.model_dump(mode="json")

    # Xona o'chirilsa uning rasmlari yetim qolmasin (diskda ham, bazada ham)
    live_rooms = {r.id for r in body.rooms}
    orphans = (
        (
            await db.execute(
                select(OrderFile).where(
                    OrderFile.order_id == order_id,
                    OrderFile.kind == FileKind.DOCUMENT,
                    OrderFile.meta.has_key("room_id"),  # noqa: W601 — JSONB operatori, dict.has_key emas
                    OrderFile.meta["room_id"].astext.not_in(live_rooms or {""}),
                    OrderFile.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    for f in orphans:
        with contextlib.suppress(OSError):
            (upload_root() / f.path).unlink()
        f.is_deleted = True
        f.deleted_at = datetime.now(UTC)

    log_action(
        db,
        module="orders",
        action="survey_saved",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"Anketa saqlandi: {len(body.rooms)} ta xona",
        ip=client_ip(request),
    )
    await db.commit()
    return Message(message="Anketa saqlandi.")


_ROOM_PHOTO_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


MAX_ROOM_PHOTO_SIZE = 5 * 1024 * 1024  # telefon surati odatda 2-4 MB


MAX_ROOM_PHOTOS = 6


@router.post(
    "/{order_id}/survey/photos", response_model=OrderFileRead, status_code=201, operation_id="upload_room_photo"
)
async def upload_room_photo(
    db: SessionDep,
    current_user: ManagerUser,
    order_id: int,
    room_id: Annotated[str, Form(max_length=40)],
    file: UploadFile,
    request: Request,
) -> OrderFileRead:
    """Xona uchun taxminiy ko'rinish rasmi (anketa, mijoz ko'rsatgan namuna).

    Rasm SurveyRoom.id ga bog'lanadi — xona ro'yxatdagi o'rni o'zgarsa ham yo'qolmaydi.
    """
    order = await _get_order(db, order_id)
    if order.status in (OrderStatus.DELIVERED, OrderStatus.CANCELLED):
        raise ForbiddenException("Yakunlangan yoki bekor qilingan buyurtmaga rasm qo'shib bo'lmaydi.")

    ext = _ROOM_PHOTO_TYPES.get(file.content_type or "")
    if ext is None:
        raise HTTPException(status_code=422, detail="Faqat JPG, PNG yoki WEBP rasm qabul qilinadi.")
    content = await file.read()
    if len(content) > MAX_ROOM_PHOTO_SIZE:
        raise HTTPException(status_code=422, detail=f"Rasm {MAX_ROOM_PHOTO_SIZE // 1024**2} MB dan katta bo'lmasin.")

    existing = (
        await db.execute(
            select(func.count(OrderFile.id)).where(
                OrderFile.order_id == order_id,
                OrderFile.kind == FileKind.DOCUMENT,
                OrderFile.meta["room_id"].astext == room_id,
                OrderFile.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one()
    if existing >= MAX_ROOM_PHOTOS:
        raise HTTPException(
            status_code=422, detail=f"Bitta xonaga {MAX_ROOM_PHOTOS} tadan ko'p rasm qo'shib bo'lmaydi."
        )

    rel = f"survey/{order_id}/{uuid4().hex}{ext}"
    full = upload_root() / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(content)

    row = OrderFile(
        order_id=order_id,
        kind=FileKind.DOCUMENT,
        path=rel,
        filename=(file.filename or "rasm")[:255],
        size=len(content),
        meta={"room_id": room_id, "content_type": file.content_type},
    )
    db.add(row)
    await db.flush()
    log_action(
        db,
        module="orders",
        action="survey_photo_added",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order_id,
        message=f"Anketaga rasm qo'shildi: {row.filename}",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(row)
    return OrderFileRead.model_validate(row)


@router.delete("/{order_id}/survey/photos/{file_id}", response_model=Message, operation_id="delete_room_photo")
async def delete_room_photo(
    db: SessionDep, current_user: ManagerUser, order_id: int, file_id: int, request: Request
) -> Message:
    row = (
        await db.execute(
            select(OrderFile).where(
                OrderFile.id == file_id,
                OrderFile.order_id == order_id,
                OrderFile.kind == FileKind.DOCUMENT,
                OrderFile.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundException("Rasm topilmadi.")
    # Diskdagi fayl ham o'chadi — anketa rasmlari tarix uchun saqlanmaydi
    with contextlib.suppress(OSError):
        (upload_root() / row.path).unlink()
    row.is_deleted = True
    row.deleted_at = datetime.now(UTC)
    log_action(
        db,
        module="orders",
        action="survey_photo_deleted",
        user_id=current_user.id,
        entity_type="order",
        entity_id=order_id,
        message=f"Anketa rasmi o'chirildi: {row.filename}",
        ip=client_ip(request),
    )
    await db.commit()
    return Message(message="Rasm o'chirildi.")
