"""Tayyor mahsulot ombori API (marshrutning ENG OXIRGI qadami).

Ikki ish: QABUL va TOPSHIRISH.

QABUL — omborchi kelgan narsani skanerlaydi va u ro'yxatga tushadi. Bu ayni
paytda marshrutning OMBOR qadami: shu skansiz detal "oxirgi postda qolib
ketgan" bo'lib qolaverardi va buyurtma hech qachon yopilmasdi. Qadoqlangan
buyurtmada bitta qadoq QR'i ichidagi HAMMA nusxani birdaniga qabul qiladi —
omborchi qadoqni ochib har detalni skanerlamaydi.

TOPSHIRISH — mijozga berish. Qadoqlangan buyurtmada birlik = qadoq, qadoqsizda
= butun buyurtma. Hamma narsa topshirilgach buyurtma DELIVERED bo'ladi.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import SessionDep, require_roles
from app.core.exceptions import ForbiddenException
from app.core.ws import ws_manager
from app.crud import crud_orders, log_action
from app.models import Machine, Order, Pachka, PachkaItem, Part, PartInstance, PartRoute, Post, Product, Scan
from app.models.enums import POST_ROLES, OrderStatus, PachkaStatus, PostCode, UserRole
from app.models.user import User
from app.schemas.common import Message
from app.schemas.terminal import (
    OmborOrderState,
    OmborPachkaRow,
    OmborPending,
    PachkaScan,
)
from app.services.scanning import ScanRejected, active_session, record_scan_at, resolve_terminal

from .pachka import _weight, instance_stages

router = APIRouter(prefix="/ombor", tags=["ombor"])

WhUser = Annotated[User, Depends(require_roles(UserRole.TERMINAL, *POST_ROLES))]


async def _wh_ctx(db: SessionDep, user: WhUser) -> tuple[Machine, Post]:
    try:
        machine, post = await resolve_terminal(db, user)
    except ScanRejected as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from None
    if post.code != PostCode.OMBOR:
        raise ForbiddenException("Bu sahifa faqat ombor postida ochiladi.")
    return machine, post


WhCtx = Annotated[tuple[Machine, Post], Depends(_wh_ctx)]


async def _state(db: SessionDep, order: Order, post: Post) -> OmborOrderState:
    """Buyurtmaning ombor holati: qadoqlar, qabul qilinmagan nusxalar, hisob."""
    # Butun buyurtmaning marshruti bir so'rovda — `ready` ni har nusxa uchun
    # alohida COUNT bilan hisoblasak 100 detalga 100 so'rov ketardi.
    routes = list(
        (
            await db.execute(
                select(PartRoute).where(
                    PartRoute.order_id == order.id,
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    by_part: dict[int, list[PartRoute]] = {}
    for r in routes:
        by_part.setdefault(r.part_id, []).append(r)
    packaging = any(r.process_code == 15 for r in routes)  # 15 = Qadoqlash

    #: Har NUSXA uchun: omborga yetib keldimi, kelmagan bo'lsa qaysi postda turibdi.
    stages = await instance_stages(db, order, post)

    accepted: set[int] = set(
        (
            await db.execute(
                select(Scan.instance_id).where(
                    Scan.order_id == order.id,
                    Scan.post_id == post.id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )

    #: Nusxa -> qaysi qadoqda. Qadoqsiz buyurtmada bo'sh qoladi.
    in_pachka: dict[int, Pachka] = {}
    pachka_rows = (
        await db.execute(
            select(Pachka, PachkaItem.instance_id)
            .outerjoin(
                PachkaItem,
                (PachkaItem.pachka_id == Pachka.id) & (PachkaItem.is_deleted == False),  # noqa: E712
            )
            .where(
                Pachka.order_id == order.id,
                Pachka.is_deleted == False,  # noqa: E712
            )
            .order_by(Pachka.id)
        )
    ).all()
    pachkas: dict[int, OmborPachkaRow] = {}
    weights: dict[int, float] = {}
    for pachka, instance_id in pachka_rows:
        row = pachkas.get(pachka.id)
        if row is None:
            row = OmborPachkaRow(
                id=pachka.id,
                code=pachka.code,
                status=pachka.status,
                item_count=0,
                accepted_count=0,
                weight_kg=0,
                shipped_at=pachka.shipped_at,
            )
            pachkas[pachka.id] = row
            weights[pachka.id] = 0.0
        if instance_id is None:
            continue
        in_pachka[instance_id] = pachka
        row.item_count += 1
        if instance_id in accepted:
            row.accepted_count += 1

    instances = (
        await db.execute(
            select(PartInstance, Part, Product.code)
            .join(Part, Part.id == PartInstance.part_id)
            .join(Product, Product.id == Part.product_id)
            .where(
                PartInstance.order_id == order.id,
                PartInstance.is_deleted == False,  # noqa: E712
            )
            .order_by(Product.code, Part.code, PartInstance.instance_no)
        )
    ).all()

    pending: list[OmborPending] = []
    total = 0
    for instance, part, product_code in instances:
        if part.id not in by_part or not any(s.post_id == post.id for s in by_part[part.id]):
            continue  # marshrutida ombor qadami yo'q (eski buyurtma)
        total += 1
        pachka = in_pachka.get(instance.id)
        if pachka is not None:
            weights[pachka.id] = weights.get(pachka.id, 0.0) + _weight(part)
        if instance.id in accepted:
            continue
        pending.append(
            OmborPending(
                instance_id=instance.id,
                qr_text=instance.qr_text,
                part_code=f"{product_code}_{part.code}",
                part_name=part.name,
                pachka_code=pachka.code if pachka else None,
                ready=stages.get(instance.id) == "",
                stage=stages.get(instance.id) or "",
            )
        )
    # Omborga yetib kelganlari tepada: omborchi ish ro'yxati aynan shular.
    pending.sort(key=lambda p: (not p.ready, p.stage, p.part_code))
    for pid, row in pachkas.items():
        row.weight_kg = round(weights.get(pid, 0.0), 1)

    return OmborOrderState(
        order_id=order.id,
        order_number=order.number,
        project_name=order.project_name,
        order_status=order.status,
        packaging=packaging,
        total=total,
        accepted=total - len(pending),
        pachkas=list(pachkas.values()),
        pending=pending,
    )


@router.get("/orders/{order_id}", response_model=OmborOrderState, operation_id="read_ombor_order")
async def read_ombor_order(db: SessionDep, ctx: WhCtx, order_id: int) -> OmborOrderState:
    """Ombor sahifasi: qadoqlar, qabul qilinmagan nusxalar, topshirish holati."""
    _machine, post = ctx
    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)
    return await _state(db, order, post)


async def _pachka_by_code(db: SessionDep, order: Order, code: str) -> Pachka:
    pachka = (
        await db.execute(
            select(Pachka).where(
                Pachka.code == code,
                Pachka.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if pachka is None:
        raise HTTPException(status_code=422, detail={"code": "E001", "message": f"{code} qadog'i topilmadi."})
    if pachka.order_id != order.id:
        raise HTTPException(
            status_code=422,
            detail={"code": "E001", "message": "Bu qadoq boshqa buyurtmaga tegishli."},
        )
    return pachka


@router.post("/orders/{order_id}/accept", response_model=OmborOrderState, operation_id="accept_into_ombor")
async def accept_into_ombor(
    db: SessionDep, user: WhUser, ctx: WhCtx, order_id: int, body: PachkaScan
) -> OmborOrderState:
    """Omborga qabul qilish. QR ikki xil bo'ladi:

    `PK-...` — qadoq: ichidagi HAMMA nusxa bitta skanda qabul qilinadi.
    Boshqasi — bitta detal nusxasi (qadoqlanmagan buyurtma).
    """
    machine, post = ctx
    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)
    qr = body.qr_text.strip()
    session = await active_session(db, user, machine)

    if qr.upper().startswith("PK-"):
        pachka = await _pachka_by_code(db, order, qr)
        if pachka.status == PachkaStatus.OPEN:
            raise ForbiddenException(f"{pachka.code} hali yopilmagan — qadoqlash tugamagan.")
        qrs = list(
            (
                await db.execute(
                    select(PartInstance.qr_text)
                    .join(PachkaItem, PachkaItem.instance_id == PartInstance.id)
                    .where(
                        PachkaItem.pachka_id == pachka.id,
                        PachkaItem.is_deleted == False,  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        )
        note = f"Qadoq qabul qilindi: {pachka.code} ({len(qrs)} detal)"
    else:
        qrs = [qr]
        note = f"Omborga qabul qilindi: {qr}"

    for one in qrs:
        try:
            await record_scan_at(
                db,
                machine=machine,
                post=post,
                session=session,
                qr_text=one,
                client_event_id=f"wh-{order.id}-{one}",
            )
        except ScanRejected as exc:
            await db.rollback()
            raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from None

    log_action(
        db,
        module="ombor",
        action="accepted",
        user_id=user.id,
        entity_type="order",
        entity_id=order.id,
        message=note,
    )
    await db.commit()
    await ws_manager.publish("ombor.accepted", {"order_id": order.id, "qr_text": qr})
    return await _state(db, order, post)


def _deliver_if_done(order: Order, state: OmborOrderState) -> None:
    """Hammasi qabul qilinib topshirilgan bo'lsa — buyurtma yopiladi."""
    if state.pending or order.status == OrderStatus.DELIVERED:
        return
    if any(p.shipped_at is None for p in state.pachkas):
        return
    order.status = OrderStatus.DELIVERED
    order.delivered_at = datetime.now(UTC)


@router.post("/orders/{order_id}/ship", response_model=OmborOrderState, operation_id="ship_pachka")
async def ship_pachka(db: SessionDep, user: WhUser, ctx: WhCtx, order_id: int, body: PachkaScan) -> OmborOrderState:
    """Qadoqni mijozga topshirish — QR skani yoki ro'yxatdagi tugma (ikkalasi ham kod yuboradi)."""
    _machine, post = ctx
    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)
    pachka = await _pachka_by_code(db, order, body.qr_text.strip())
    if pachka.shipped_at is not None:
        raise ForbiddenException(f"{pachka.code} allaqachon topshirilgan.")

    state = await _state(db, order, post)
    row = next((p for p in state.pachkas if p.id == pachka.id), None)
    # Qabul qilinmagan qadoqni topshirib bo'lmaydi: aks holda detal omborga
    # kirmasdan chiqib ketardi va marshrut oxirgi qadamida osilib qolardi.
    if row is None or row.accepted_count < row.item_count:
        raise ForbiddenException(f"{pachka.code} to'liq qabul qilinmagan — avval skanerlang.")

    pachka.status = PachkaStatus.SHIPPED
    pachka.shipped_at = datetime.now(UTC)
    row.status = PachkaStatus.SHIPPED
    row.shipped_at = pachka.shipped_at
    _deliver_if_done(order, state)
    log_action(
        db,
        module="ombor",
        action="shipped",
        user_id=user.id,
        entity_type="pachka",
        entity_id=pachka.id,
        message=f"Qadoq topshirildi: {pachka.code}",
    )
    await db.commit()
    await ws_manager.publish("ombor.shipped", {"order_id": order.id, "code": pachka.code})
    return await _state(db, order, post)


@router.post("/orders/{order_id}/deliver", response_model=Message, operation_id="deliver_ombor_order")
async def deliver_ombor_order(db: SessionDep, user: WhUser, ctx: WhCtx, order_id: int) -> Message:
    """Butun buyurtmani topshirish — qadoqsiz buyurtma uchun (qadoqlanganda har qadoq alohida)."""
    _machine, post = ctx
    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)
    if order.status == OrderStatus.DELIVERED:
        raise ForbiddenException("Buyurtma allaqachon topshirilgan.")
    state = await _state(db, order, post)
    if state.pending:
        raise ForbiddenException(f"{len(state.pending)} detal hali omborga qabul qilinmagan.")
    unshipped = [p for p in state.pachkas if p.shipped_at is None]
    if unshipped:
        raise ForbiddenException(f"{len(unshipped)} qadoq topshirilmagan — avval ularni topshiring.")

    order.status = OrderStatus.DELIVERED
    order.delivered_at = datetime.now(UTC)
    log_action(
        db,
        module="ombor",
        action="delivered",
        user_id=user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"Buyurtma topshirildi: {order.number} ({state.total} detal)",
    )
    await db.commit()
    await ws_manager.publish("ombor.delivered", {"order_id": order.id})
    return Message(message=f"Buyurtma topshirildi: {order.number}")
