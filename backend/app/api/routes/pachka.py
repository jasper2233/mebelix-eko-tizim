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
from app.crud import crud_orders, log_action
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
from app.services.scanning import ScanRejected, active_session, record_scan_at, resolve_terminal

router = APIRouter(prefix="/pachka", tags=["pachka"])

#: LDSP zichligi (kg/m3) — taxminiy og'irlik shundan hisoblanadi. Aniq tarozi emas:
#: qadoqlovchiga "og'irmi yoki yengilmi" degan tasavvur berish uchun (TZ Upakovka §5).
DENSITY = 700.0

PackUser = Annotated[User, Depends(require_roles(UserRole.TERMINAL, *POST_ROLES))]


def _weight(part: Part) -> float:
    """Detalning taxminiy og'irligi: hajm × zichlik. O'lchami yo'q bo'lsa 0."""
    if not (part.length and part.width and part.thickness):
        return 0.0
    return round(part.length * part.width * part.thickness / 1e9 * DENSITY, 2)


async def _pack_ctx(db: SessionDep, user: PackUser) -> tuple[Machine, Post]:
    """Qadoqlash posti konteksti — faqat UPAKOVKA terminalidan."""
    try:
        machine, post = await resolve_terminal(db, user)
    except ScanRejected as exc:
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from None
    if post.code != PostCode.UPAKOVKA:
        raise ForbiddenException("Bu sahifa faqat qadoqlash postida ochiladi.")
    return machine, post


PackCtx = Annotated[tuple[Machine, Post], Depends(_pack_ctx)]


async def instance_stages(db: SessionDep, order: Order, post: Post) -> dict[int, str]:
    """Har NUSXA uchun: shu postgacha bo'lgan qadamlar tugadimi, tugamagan bo'lsa qayerda turibdi.

    Qaytadi: `instance_id -> bosqich nomi`, bo'sh satr = shu postga tayyor.
    Faqat marshrutida shu post bor nusxalar kiradi.

    Hisob NUSXA bo'yicha, detal bo'yicha emas: 4 nusxali detalning bittasi
    qadoqlansa, detal jami hali tugamagan bo'ladi — lekin o'sha bitta nusxa
    omborga tayyor. Detal darajasida sanaganda u "sexda" bo'lib qolar edi va
    omborchi qadoqlangan buyumni ro'yxatdan topa olmasdi.
    """
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

    # Bitta agregat so'rov: (nusxa, qadam) -> nechta skan
    counts = {
        (instance_id, route_id): n
        for instance_id, route_id, n in (
            await db.execute(
                select(Scan.instance_id, Scan.route_id, func.count())
                .where(
                    Scan.order_id == order.id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .group_by(Scan.instance_id, Scan.route_id)
            )
        ).all()
    }
    post_names = {p.id: p.name for p in (await db.execute(select(Post))).scalars()}

    stages: dict[int, str] = {}
    for instance_id, part_id in (
        await db.execute(
            select(PartInstance.id, PartInstance.part_id).where(
                PartInstance.order_id == order.id,
                PartInstance.is_deleted == False,  # noqa: E712
            )
        )
    ).all():
        steps = sorted(by_part.get(part_id, []), key=lambda s: s.seq)
        target = next((s for s in steps if s.post_id == post.id), None)
        if target is None:
            continue
        stuck = next(
            (s for s in steps if s.seq < target.seq and counts.get((instance_id, s.id), 0) < s.per_instance),
            None,
        )
        stages[instance_id] = "" if stuck is None else post_names.get(stuck.post_id, "")
    return stages


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
            select(PartInstance, Part, Product.code, PartRoute.seq)
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
    for instance, part, product_code, _seq in pending_rows:
        if instance.id in packed:
            continue
        pending.append(
            UpakovkaPending(
                instance_id=instance.id,
                qr_text=instance.qr_text,
                part_code=f"{product_code}_{part.code}",
                part_name=part.name,
                ready=stages.get(instance.id) == "",
            )
        )
    pending.sort(key=lambda p: (not p.ready, p.part_code))

    return UpakovkaOrderState(
        order_id=order.id,
        order_number=order.number,
        project_name=order.project_name,
        density=DENSITY,
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
    # bilan yangi qadoq bir xil QR beradi va omborda chalkashlik chiqadi.
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
    pachka = await db.get(Pachka, pachka_id)
    if pachka is None or pachka.is_deleted:
        raise NotFoundException("Qadoq topilmadi.")
    if pachka.status != PachkaStatus.OPEN:
        raise ForbiddenException(f"Qadoq {pachka.code} yopilgan — avval qayta oching.")
    return pachka


@router.post("/{pachka_id}/scan", response_model=UpakovkaOrderState, operation_id="scan_into_pachka")
async def scan_into_pachka(
    db: SessionDep, user: PackUser, ctx: PackCtx, pachka_id: int, body: PachkaScan
) -> UpakovkaOrderState:
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
        raise HTTPException(status_code=422, detail={"code": "E001", "message": "Bunday QR topilmadi."})
    if instance.order_id != pachka.order_id:
        raise HTTPException(
            status_code=422,
            detail={"code": "E001", "message": "Bu detal boshqa buyurtmaga tegishli."},
        )
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
        raise HTTPException(
            status_code=422,
            detail={"code": "E001", "message": f"Bu detal allaqachon {name} ichida."},
        )

    session = await active_session(db, user, machine)
    try:
        await record_scan_at(
            db,
            machine=machine,
            post=post,
            session=session,
            qr_text=qr,
            client_event_id=f"pack-{pachka.id}-{instance.id}",
        )
    except ScanRejected as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from None

    db.add(PachkaItem(pachka_id=pachka.id, instance_id=instance.id))
    await db.commit()
    await ws_manager.publish("pachka.item", {"pachka_id": pachka.id, "qr_text": qr})
    return await _state(db, order, post)


@router.delete("/{pachka_id}/items/{instance_id}", response_model=UpakovkaOrderState, operation_id="remove_from_pachka")
async def remove_from_pachka(
    db: SessionDep, user: PackUser, ctx: PackCtx, pachka_id: int, instance_id: int
) -> UpakovkaOrderState:
    """Xato skanni qaytarish: nusxa qadoqdan chiqadi va UPAKOVKA skani bekor bo'ladi."""
    from sqlalchemy import update

    from app.models import Scan

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
        scan.is_cancelled = True
        scan.cancelled_at = now
        await db.execute(
            update(PartRoute)
            .where(PartRoute.id == scan.route_id, PartRoute.total_done > 0)
            .values(total_done=PartRoute.total_done - 1)
        )
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
    """Qadoqni yakunlash: yopiladi va cheki chop etishga yuboriladi."""
    _machine, _post = ctx
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

    from app.core.utils import queue

    if queue.pool is not None:
        await queue.pool.enqueue_job("print_pachka_label", pachka.id)
    await ws_manager.publish("pachka.closed", {"pachka_id": pachka.id, "code": pachka.code})
    return Message(message=f"Qadoq yakunlandi: {pachka.code} ({count} detal)")
