"""Qadoqlash API (TZ Upakovka): qadoq yaratish, detal skanerlash, yakunlash.

Qadoqni ALGORITM emas, qadoqlovchi yig'adi. Tizim faqat ikkita ish qiladi:
detalning oldingi bosqichlari tugaganini tekshiradi (bu odatdagi skan orqali
o'z-o'zidan bo'ladi) va taxminiy og'irlikni KO'RSATADI. Og'irlik, o'lcham,
xona — hech biri bloklamaydi: qaror qadoqlovchida.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from app.api.deps import SessionDep, require_roles
from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.ws import ws_manager
from app.crud import crud_orders, crud_pachkas, log_action
from app.models import Machine, Order, Pachka, PachkaItem, Part, PartInstance, PartRoute, Post, Product, Scan
from app.models.enums import POST_ROLES, PachkaStatus, PostCode, UserRole
from app.models.user import User
from app.schemas.common import Message
from app.schemas.terminal import (
    PachkaItemRow,
    PachkaRow,
    PachkaScan,
    UpakovkaOrderState,
    UpakovkaPending,
)
from app.services.scanning import (
    ScanRejected,
    active_session,
    instance_stages,
    publish_scan_events,
    record_scan_at,
    resolve_terminal,
    revoke_scan,
    scan_error,
)

router = APIRouter(prefix="/pachka", tags=["pachka"])

#: LDSP zichligi (kg/m3) — taxminiy og'irlik shundan hisoblanadi. Aniq tarozi emas:
#: qadoqlovchiga "og'irmi yoki yengilmi" degan tasavvur berish uchun (TZ Upakovka §5).
DENSITY = 700.0

PackUser = Annotated[User, Depends(require_roles(UserRole.TERMINAL, *POST_ROLES))]


def _weight(part: Part) -> float:
    if not (part.length and part.width and part.thickness):
        return 0.0
    return round(part.length * part.width * part.thickness / 1e9 * DENSITY, 2)


async def _pack_ctx(db: SessionDep, user: PackUser) -> tuple[Machine, Post]:
    try:
        machine, post = await resolve_terminal(db, user)
    except ScanRejected as exc:
        raise scan_error(exc.code, exc.message) from None
    if post.code != PostCode.UPAKOVKA:
        raise ForbiddenException("Bu sahifa faqat qadoqlash postida ochiladi.")
    return machine, post


PackCtx = Annotated[tuple[Machine, Post], Depends(_pack_ctx)]


async def _state(db: SessionDep, order: Order, post: Post) -> UpakovkaOrderState:
    """Buyurtmaning qadoqlash holati: qadoqlar + hali qadoqlanmagan nusxalar."""
    rows = (
        await db.execute(
            select(Pachka, PachkaItem, PartInstance, Part, Product.code)
            .outerjoin(
                PachkaItem,
                (PachkaItem.pachka_id == Pachka.id) & (PachkaItem.is_deleted == False),  # noqa: E712
            )
            .outerjoin(PartInstance, PartInstance.id == PachkaItem.instance_id)
            .outerjoin(Part, Part.id == PartInstance.part_id)
            .outerjoin(Product, Product.id == Part.product_id)
            .where(
                Pachka.order_id == order.id,
                Pachka.is_deleted == False,  # noqa: E712
            )
            .order_by(Pachka.id, PachkaItem.id)
        )
    ).all()

    pachkas: dict[int, PachkaRow] = {}
    packed: set[int] = set()
    for pachka, item, instance, part, product_code in rows:
        row = pachkas.get(pachka.id)
        if row is None:
            row = PachkaRow(id=pachka.id, code=pachka.code, status=pachka.status)
            pachkas[pachka.id] = row
        if item is None or instance is None or part is None:
            continue
        packed.add(instance.id)
        row.items.append(
            PachkaItemRow(
                instance_id=instance.id,
                qr_text=instance.qr_text,
                part_code=f"{product_code}_{part.code}",
                part_name=part.name,
                length=part.length,
                width=part.width,
                thickness=part.thickness,
                weight_kg=_weight(part),
            )
        )
    for row in pachkas.values():
        row.weight_kg = round(sum(i.weight_kg for i in row.items), 1)

    # Qadoqlanishi kerak bo'lgan nusxalar: marshrutida UPAKOVKA bor detallar.
    # `ready` — oldingi qadamlar tugaganmi; tugamagan bo'lsa skan baribir rad
    # etiladi, lekin ro'yxatda ko'rinib turgani qadoqlovchiga nima kutayotganini aytadi.
    pending_rows = (
        await db.execute(
            select(PartInstance, Part, Product.code)
            .join(Part, Part.id == PartInstance.part_id)
            .join(Product, Product.id == Part.product_id)
            .join(PartRoute, (PartRoute.part_id == Part.id) & (PartRoute.post_id == post.id))
            .where(
                PartInstance.order_id == order.id,
                PartInstance.is_deleted == False,  # noqa: E712
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
            )
            .order_by(Product.code, Part.code, PartInstance.instance_no)
        )
    ).all()

    stages = await instance_stages(db, order, post)
    pending: list[UpakovkaPending] = []
    for instance, part, product_code in pending_rows:
        if instance.id in packed:
            continue
        pending.append(
            UpakovkaPending(
                instance_id=instance.id,
                qr_text=instance.qr_text,
                part_code=f"{product_code}_{part.code}",
                part_name=part.name,
                ready=stages.get(instance.id, (False, ""))[0],
            )
        )
    pending.sort(key=lambda p: (not p.ready, p.part_code))

    return UpakovkaOrderState(
        order_id=order.id,
        order_number=order.number,
        project_name=order.project_name,
        pachkas=list(pachkas.values()),
        pending=pending,
    )


@router.get("/orders/{order_id}", response_model=UpakovkaOrderState, operation_id="read_upakovka_order")
async def read_upakovka_order(db: SessionDep, ctx: PackCtx, order_id: int) -> UpakovkaOrderState:
    """Qadoqlash sahifasi: buyurtmaning qadoqlari va qolgan detallari."""
    _machine, post = ctx
    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)
    return await _state(db, order, post)


@router.post("/orders/{order_id}", response_model=UpakovkaOrderState, operation_id="create_pachka")
async def create_pachka(db: SessionDep, user: PackUser, ctx: PackCtx, order_id: int) -> UpakovkaOrderState:
    """Yangi qadoq ochish. Kod `PK-{buyurtma}-{NN}` — chekdagi QR matni ham shu."""
    _machine, post = ctx
    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)
    # Tartib raqami O'CHIRILGANLARNI ham sanaydi: kod qayta ishlatilsa eski chek
    # bilan yangi qadoq bir xil QR beradi va TMO da chalkashlik chiqadi.
    used = (await db.execute(select(func.count()).select_from(Pachka).where(Pachka.order_id == order.id))).scalar_one()
    pachka = Pachka(order_id=order.id, code=f"PK-{order.number}-{used + 1:02d}", created_by_id=user.id)
    db.add(pachka)
    await db.flush()
    log_action(
        db,
        module="pachka",
        action="created",
        user_id=user.id,
        entity_type="pachka",
        entity_id=pachka.id,
        message=f"Qadoq ochildi: {pachka.code}",
    )
    await db.commit()
    return await _state(db, order, post)


async def _open_pachka(db: SessionDep, pachka_id: int) -> Pachka:
    pachka = await crud_pachkas.get_or_404(db, "Qadoq topilmadi.", id=pachka_id)
    if pachka.status != PachkaStatus.OPEN:
        raise ForbiddenException(f"Qadoq {pachka.code} yopilgan — avval qayta oching.")
    return pachka


@router.post("/{pachka_id}/scan", response_model=UpakovkaOrderState, operation_id="scan_into_pachka")
async def scan_into_pachka(db: SessionDep, ctx: PackCtx, pachka_id: int, body: PachkaScan) -> UpakovkaOrderState:
    """Detalni qadoqqa skanerlash — bu AYNI PAYTDA marshrutning UPAKOVKA qadami.

    Skanni odatdagi dvijok yozadi, ya'ni qat'iy tartib shu yerda ham ishlaydi:
    oldingi bosqichi tugamagan detal qadoqqa tushmaydi. Shu tufayli yopiq qadoq
    ichida chala detal bo'lishi mumkin emas — omborchi ochib tekshirmaydi.
    """
    machine, post = ctx
    pachka = await _open_pachka(db, pachka_id)
    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=pachka.order_id)

    qr = body.qr_text.strip()
    instance = (
        await db.execute(
            select(PartInstance).where(
                PartInstance.qr_text == qr,
                PartInstance.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if instance is None:
        raise scan_error("E001", "Bunday QR topilmadi.")
    if instance.order_id != pachka.order_id:
        raise scan_error("E001", "Bu detal boshqa buyurtmaga tegishli.")
    already = (
        await db.execute(
            select(PachkaItem).where(
                PachkaItem.instance_id == instance.id,
                PachkaItem.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if already is not None:
        other = await db.get(Pachka, already.pachka_id)
        name = other.code if other else "boshqa qadoq"
        raise scan_error("E001", f"Bu detal allaqachon {name} ichida.")

    session = await active_session(db, machine)
    try:
        outcome = await record_scan_at(
            db,
            machine=machine,
            post=post,
            session=session,
            qr_text=qr,
            client_event_id=f"pack-{pachka.id}-{instance.id}",
        )
    except ScanRejected as exc:
        await db.rollback()
        raise scan_error(exc.code, exc.message) from None

    db.add(PachkaItem(pachka_id=pachka.id, instance_id=instance.id))
    await db.commit()
    # UPAKOVKA skani ham odatdagi skan: `scan.recorded` boshqa terminallarga borishi
    # va bosqich/buyurtma yakunlanishi efirga chiqishi kerak.
    await publish_scan_events([outcome])
    await ws_manager.publish("pachka.item", {"pachka_id": pachka.id, "qr_text": qr})
    return await _state(db, order, post)


@router.delete("/{pachka_id}/items/{instance_id}", response_model=UpakovkaOrderState, operation_id="remove_from_pachka")
async def remove_from_pachka(
    db: SessionDep, user: PackUser, ctx: PackCtx, pachka_id: int, instance_id: int
) -> UpakovkaOrderState:
    """Xato skanni qaytarish: nusxa qadoqdan chiqadi va UPAKOVKA skani bekor bo'ladi."""
    _machine, post = ctx
    pachka = await _open_pachka(db, pachka_id)
    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=pachka.order_id)

    item = (
        await db.execute(
            select(PachkaItem).where(
                PachkaItem.pachka_id == pachka.id,
                PachkaItem.instance_id == instance_id,
                PachkaItem.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundException("Bu detal qadoq ichida emas.")
    now = datetime.now(UTC)
    item.is_deleted = True
    item.deleted_at = now

    # Qadoqqa qo'shilganda yozilgan skan ham qaytariladi, aks holda UPAKOVKA
    # qadami yopiq qolib, detal boshqa qadoqqa tushsa ikki marta sanalardi.
    scan = (
        await db.execute(
            select(Scan).where(
                Scan.client_event_id == f"pack-{pachka.id}-{instance_id}",
                Scan.is_cancelled == False,  # noqa: E712
                Scan.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if scan is not None:
        # Bekor qilishning yagona shakli (`services/scanning.revoke_scan`):
        # hosila skanlar va COMPLETED -> PRODUCTION qaytishi ham shunda.
        await revoke_scan(db, scan, at=now)
    log_action(
        db,
        module="pachka",
        action="item_removed",
        user_id=user.id,
        entity_type="pachka",
        entity_id=pachka.id,
        message=f"Qadoqdan chiqarildi: nusxa {instance_id} ({pachka.code})",
    )
    await db.commit()
    return await _state(db, order, post)


@router.post("/{pachka_id}/close", response_model=Message, operation_id="close_pachka")
async def close_pachka(db: SessionDep, user: PackUser, ctx: PackCtx, pachka_id: int) -> Message:
    """Qadoqni yakunlash: yopiladi va cheki chop etishga yuboriladi.

    Chek chiqara olmasak (navbat o'chgan yoki postga printer biriktirilmagan)
    qadoq ATAYLAB yopilmaydi — yopilgan qadoqning chekini qayta chiqarish yo'li
    yo'q, shuning uchun xato aytiladi va qadoqlovchi qayta urinadi.
    """
    machine, post = ctx
    pachka = await _open_pachka(db, pachka_id)
    count = (
        await db.execute(
            select(func.count())
            .select_from(PachkaItem)
            .where(
                PachkaItem.pachka_id == pachka.id,
                PachkaItem.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one()
    if count == 0:
        raise ForbiddenException("Bo'sh qadoqni yakunlab bo'lmaydi.")

    from app.core.utils import queue
    from app.tasks import NoPrinterBound, require_printer

    # Chek chiqmaydigan bo'lsa qadoq YOPILMAYDI: yopilgan qadoqni qayta yopib
    # bo'lmaydi va chekni qayta chiqarish yo'li yo'q — shuning uchun to'siq
    # commitdan OLDIN tekshiriladi, qadoq esa ochiq qolib qayta urinishga imkon beradi.
    if queue.pool is None:
        # 503, 403 emas: navbat (arq/Redis) o'chgani infratuzilma nosozligi.
        raise HTTPException(
            status_code=503,
            detail="Chop etish navbati ishlamayapti — qadoq yopilmadi. Adminga murojaat qilib qayta urinib ko'ring.",
        )
    # Qadoq cheki qadoqlash stansiyasining printeridan chiqsin. Printer
    # biriktirilmagan bo'lsa chek YUBORILMAYDI: umumiy navbatda uni boshqa
    # postdagi agent tortib olardi va chek noto'g'ri joyda chiqardi.
    try:
        agent = await require_printer(db, machine.id)
    except NoPrinterBound:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{post.name} ish markaziga printer biriktirilmagan — qadoq yopilmadi. "
                "Admin printerni bog'lagach qayta urinib ko'ring."
            ),
        ) from None

    pachka.status = PachkaStatus.CLOSED
    pachka.closed_at = datetime.now(UTC)
    log_action(
        db,
        module="pachka",
        action="closed",
        user_id=user.id,
        entity_type="pachka",
        entity_id=pachka.id,
        message=f"Qadoq yakunlandi: {pachka.code} ({count} detal)",
    )
    await db.commit()

    # Enqueue commitdan KEYIN: worker yopilgan qadoqni bazadan o'qiy olishi kerak.
    await queue.pool.enqueue_job("print_pachka_label", pachka.id, agent.id)
    await ws_manager.publish("pachka.closed", {"pachka_id": pachka.id, "code": pachka.code})
    return Message(message=f"Qadoq yakunlandi: {pachka.code} ({count} detal)")
