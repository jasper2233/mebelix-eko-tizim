"""TMO — Tayyor Mahsulot Ombori API (marshrutning ENG OXIRGI qadami).

Bitta ish: QABUL. Omborchi kelgan narsani skanerlaydi va u ro'yxatga tushadi.
Bu ayni paytda marshrutning TMO qadami: shu skansiz detal "oxirgi postda
qolib ketgan" bo'lib qolaverardi va buyurtma hech qachon yopilmasdi.
Qadoqlangan buyurtmada bitta qadoq QR'i ichidagi HAMMA nusxani birdaniga
qabul qiladi — omborchi qadoqni ochib har detalni skanerlamaydi.

TMO buyurtmani TOPSHIRMAYDI. Hamma detal TMO dan o'tgach buyurtma o'zi
COMPLETED (tayyor) bo'ladi (`scanning.record_scan_at`), TOPSHIRILDI esa
managerning amali (`orders.deliver_order`, faqat COMPLETED holatdan).
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.deps import SessionDep, require_roles
from app.core.exceptions import ForbiddenException
from app.core.ws import ws_manager
from app.crud import crud_orders, log_action
from app.models import Machine, Order, Pachka, PachkaItem, Part, PartInstance, PartRoute, Post, Product, Scan
from app.models.enums import POST_ROLES, PachkaStatus, PostCode, UserRole
from app.models.user import User
from app.schemas.terminal import (
    PachkaScan,
    TmoDone,
    TmoOrderState,
    TmoPending,
)
from app.services.scanning import (
    ScanRejected,
    active_session,
    instance_stages,
    log_rejected_scan,
    publish_scan_events,
    record_scan_at,
    resolve_terminal,
    scan_error,
)

router = APIRouter(prefix="/tmo", tags=["tmo"])

WhUser = Annotated[User, Depends(require_roles(UserRole.TERMINAL, *POST_ROLES))]


async def _wh_ctx(db: SessionDep, user: WhUser) -> tuple[Machine, Post]:
    try:
        machine, post = await resolve_terminal(db, user)
    except ScanRejected as exc:
        raise scan_error(exc.code, exc.message) from None
    if post.code != PostCode.TMO:
        raise ForbiddenException("Bu sahifa faqat TMO postida ochiladi.")
    return machine, post


WhCtx = Annotated[tuple[Machine, Post], Depends(_wh_ctx)]


async def _state(db: SessionDep, order: Order, post: Post) -> TmoOrderState:
    """Buyurtmaning TMO holati: qadoqlar, qabul qilinmagan nusxalar, hisob."""
    # Butun buyurtmaning marshruti bir so'rovda — `ready` ni har nusxa uchun
    # alohida COUNT bilan hisoblasak 100 detalga 100 so'rov ketardi.
    routes = (
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

    #: Har NUSXA uchun: TMO ga yetib keldimi, kelmagan bo'lsa qaysi postda turibdi.
    #: Marshrut yuqorida o'qilgan — `by_part` uzatilmasa aynan o'sha so'rov takrorlanardi.
    stages = await instance_stages(db, order, post, by_part)

    #: Nusxa -> TMO da qachon qabul qilingani. Vaqt ham kerak: "Qabul qilingan"
    #: ro'yxati eng oxirgisi tepada bo'lib chiziladi.
    accepted_at: dict[int, datetime] = dict(
        (
            await db.execute(
                select(Scan.instance_id, func.min(Scan.created_at))
                .where(
                    Scan.order_id == order.id,
                    Scan.post_id == post.id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .group_by(Scan.instance_id)
            )
        ).all()  # type: ignore[arg-type]
    )
    accepted: set[int] = set(accepted_at)

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
    # Qadoq faqat YORLIQ sifatida kerak: har detal qatorida "qaysi qadoq cheki
    # bilan keldi" ko'rinadi. Alohida "Qadoqlar" ro'yxati YO'Q — qadoq cheki
    # skanerlanganda `accept_into_tmo` ichidagi hamma nusxani birdan qabul
    # qiladi, ya'ni omborchi uchun natija baribir DETAL ro'yxatida ko'rinadi.
    for pachka, instance_id in pachka_rows:
        if instance_id is not None:
            in_pachka[instance_id] = pachka

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

    pending: list[TmoPending] = []
    done: list[TmoDone] = []
    total = 0
    for instance, part, product_code in instances:
        if part.id not in by_part or not any(s.post_id == post.id for s in by_part[part.id]):
            continue  # marshrutida TMO qadami yo'q (eski buyurtma)
        total += 1
        pachka = in_pachka.get(instance.id)
        if instance.id in accepted:
            done.append(
                TmoDone(
                    instance_id=instance.id,
                    qr_text=instance.qr_text,
                    part_code=f"{product_code}_{part.code}",
                    part_name=part.name,
                    pachka_code=pachka.code if pachka else None,
                    accepted_at=accepted_at[instance.id],
                )
            )
            continue
        pending.append(
            TmoPending(
                instance_id=instance.id,
                qr_text=instance.qr_text,
                part_code=f"{product_code}_{part.code}",
                part_name=part.name,
                pachka_code=pachka.code if pachka else None,
                ready=stages.get(instance.id, (False, ""))[0],
                stage=stages.get(instance.id, (False, ""))[1],
            )
        )
    # TMO ga yetib kelganlari tepada: omborchi ish ro'yxati aynan shular.
    pending.sort(key=lambda p: (not p.ready, p.stage, p.part_code))
    # Eng oxirgi qabul qilingani tepada — omborchi hozirgina nima skanerlaganini ko'radi.
    done.sort(key=lambda d: d.accepted_at, reverse=True)

    return TmoOrderState(
        order_id=order.id,
        order_number=order.number,
        project_name=order.project_name,
        order_status=order.status,
        total=total,
        # Kelganlar = allaqachon qabul qilinganlar + navbatda turgan TAYYORlar.
        arrived=(total - len(pending)) + sum(1 for p in pending if p.ready),
        accepted=total - len(pending),
        done=done,
        pending=pending,
    )


@router.get("/orders/{order_id}", response_model=TmoOrderState, operation_id="read_tmo_order")
async def read_tmo_order(db: SessionDep, ctx: WhCtx, order_id: int) -> TmoOrderState:
    """TMO sahifasi: qadoqlar, qabul qilinmagan nusxalar, topshirish holati."""
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
        raise scan_error("E001", f"{code} qadog'i topilmadi.")
    if pachka.order_id != order.id:
        raise scan_error("E001", "Bu qadoq boshqa buyurtmaga tegishli.")
    return pachka


@router.post("/orders/{order_id}/accept", response_model=TmoOrderState, operation_id="accept_into_tmo")
async def accept_into_tmo(db: SessionDep, user: WhUser, ctx: WhCtx, order_id: int, body: PachkaScan) -> TmoOrderState:
    """TMO ga qabul qilish. QR ikki xil bo'ladi:

    `PK-...` — qadoq: ichidagi HAMMA nusxa bitta skanda qabul qilinadi.
    Boshqasi — bitta detal nusxasi (qadoqlanmagan buyurtma).
    """
    machine, post = ctx
    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)
    qr = body.qr_text.strip()
    qr_upper = qr.upper()  # qadoq kodlari doim UPPERCASE — prefiks ham, qidiruv ham shu registrda
    session = await active_session(db, machine)

    if qr_upper.startswith("PK-"):
        pachka = await _pachka_by_code(db, order, qr_upper)
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
        note = f"TMO ga qabul qilindi: {qr}"

    outcomes = []
    # `user.id` sikldan OLDIN: `record_scan_at` takroriy `client_event_id` poygasida
    # ScanRejected'dan oldin O'ZI rollback qiladi va shundan keyin `user.id` ni o'qish
    # MissingGreenlet -> 500 berardi (qadoqni ikki terminal bir vaqtda qabul qilsa).
    user_id = user.id
    for one in qrs:
        try:
            outcomes.append(
                await record_scan_at(
                    db,
                    machine=machine,
                    post=post,
                    session=session,
                    qr_text=one,
                    client_event_id=f"wh-{order.id}-{one}",
                )
            )
        except ScanRejected as exc:
            # Rad etilgan urinish ham logga — scans.py/pachka.py bilan bir xil:
            # Loglar sahifasidagi "rejected" filtri TMO ni ham ko'rsin.
            # `user_id` sikldan OLDIN olingan: `record_scan_at` takroriy
            # `client_event_id` da ScanRejected'dan oldin O'ZI rollback qiladi va
            # shundan keyin `user.id` ni o'qish MissingGreenlet -> 500 berardi.
            # Kalit barqaror (`wh-{order}-{qr}`), qadoqni ikki TMO terminali bir
            # vaqtda qabul qilsa poyga real.
            await log_rejected_scan(db, exc, one, user_id=user_id)
            raise scan_error(exc.code, exc.message) from None

    log_action(
        db,
        module="tmo",
        action="accepted",
        user_id=user.id,
        entity_type="order",
        entity_id=order.id,
        message=note,
    )
    await db.commit()
    # TMO — har detalning OXIRGI qadami, ya'ni buyurtmani yakunlaydigan skan aynan
    # shu yerdan o'tadi. Eventlarni tarqatmasak `scan.recorded` boshqa terminallarga
    # yetmasdi, `order.completed` esa umuman efirga chiqmasdi.
    await publish_scan_events(outcomes)
    await ws_manager.publish("tmo.accepted", {"order_id": order.id, "qr_text": qr})
    return await _state(db, order, post)
