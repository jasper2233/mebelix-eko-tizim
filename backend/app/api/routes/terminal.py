"""Operator terminal API: context, badge sessions, post queue, ARRA cut map, files."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from sqlalchemy import Row, case, func, select, update
from sqlalchemy.orm import defer

from app.api.deps import SessionDep, client_ip, require_roles
from app.core.config import TASHKENT_TZ, upload_root
from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.ws import ws_manager
from app.crud import crud_orders, crud_part_instances, crud_waste_items, log_action
from app.models import (
    PRIORITY_RANK,
    AndonEvent,
    BridgeAgent,
    Employee,
    Machine,
    Order,
    OrderFile,
    Part,
    PartDefect,
    PartInstance,
    PartRoute,
    Post,
    Product,
    Scan,
    WasteItem,
    WorkSession,
)
from app.models import (
    KromkaMeasurement as KromkaMeasurementRecord,
)
from app.models.enums import (
    POST_ROLES,
    DefectStatus,
    EmployeeStatus,
    FileKind,
    OrderStatus,
    PostCode,
    UserRole,
)
from app.models.user import User
from app.schemas.common import Message
from app.schemas.terminal import (
    BandUsage,
    CutmapHole,
    CutmapState,
    KromkaInstance,
    KromkaMeasurement,
    KromkaOrderState,
    KromkaPartRow,
    PostQueueRow,
    PostQueueState,
    PrisadkaFile,
    PrisadkaInstance,
    PrisadkaOrderState,
    PrisadkaPartRow,
    QrOrderRef,
    SessionRead,
    ShiftStart,
    TerminalContext,
    TerminalEmployee,
    TerminalOrderCard,
)
from app.services.giblab.cutmap import arra_parts_query, build_cutmap_state, holes_by_label_num
from app.services.giblab.models import stored_machined_sides
from app.services.scanning import (
    ScanRejected,
    active_session,
    badge_employee,
    crew_sessions,
    end_session,
    finalize_scan,
    instance_stages,
    open_badge_session,
    record_scan_at,
    resolve_terminal,
    revoke_scan,
    scan_error,
)
from app.services.terminal_device import (
    DEVICE_COOKIE,
    pairing_open,
    print_device,
    require_print_device,
    set_device_cookie,
    touch_device,
)
from app.tasks import NoPrinterBound, agent_online, require_printer

router = APIRouter(prefix="/terminal", tags=["terminal"])

TerminalUser = Annotated[User, Depends(require_roles(UserRole.TERMINAL, *POST_ROLES))]


async def _terminal_ctx(db: SessionDep, user: TerminalUser) -> tuple[Machine, Post]:
    """Ish markazi + post. Faqat shu ikkisiga muhtoj route'larga qo'yiladi — router darajasida EMAS:
    yorliq/fayl route'lari ish markazisiz terminal foydalanuvchisi uchun ham ishlashi kerak."""
    try:
        return await resolve_terminal(db, user)
    except ScanRejected as exc:
        raise scan_error(exc.code, exc.message) from None


TerminalCtx = Annotated[tuple[Machine, Post], Depends(_terminal_ctx)]


def _session_read(session: WorkSession, employee_name: str, *, is_me: bool = False) -> SessionRead:
    item = SessionRead.model_validate(session)
    item.employee_name = employee_name
    item.is_me = is_me
    return item


@router.get("/context", response_model=TerminalContext, operation_id="read_terminal_context")
async def read_terminal_context(
    db: SessionDep, user: TerminalUser, ctx: TerminalCtx, request: Request, response: Response
) -> TerminalContext:
    machine, post = ctx
    out = TerminalContext(
        machine_id=machine.id,
        machine_name=machine.name,
        post_id=post.id,
        post_code=post.code,
        post_name=post.name,
    )
    # Agent biriktirilgan postda holati headerda ko'rinadi — operator birinchi
    # chekkacha (yoki yo'qolgan skanlargacha) kutmasdan biladi. `printer_agent`
    # ISHLATILMAYDI: u can_print bilan filtrlaydi, faqat skan-forvard agent esa
    # chetda qolib, o'lgani hech qayerda ko'rinmasdi. Onlaynlik ta'rifi chop
    # etishdagi va paneldagi bilan AYNAN bir xil (6 daqiqalik oyna).

    agent = (
        await db.execute(
            select(BridgeAgent.last_seen_at, BridgeAgent.can_print)
            .where(
                BridgeAgent.machine_id == machine.id,
                BridgeAgent.token_hash.is_not(None),
                BridgeAgent.is_deleted == False,  # noqa: E712
            )
            # DETERMINISTIK, `printer_agent` bilan bir xil tartib: bitta ish
            # markazida ikki agent qolgan eski ma'lumotda eng oxirgi ko'ringani
            # tanlanadi, aks holda header o'lik agentning holatini ko'rsatardi.
            .order_by(BridgeAgent.last_seen_at.desc().nullslast(), BridgeAgent.id.desc())
        )
    ).first()
    if agent is not None:
        out.agent_online = agent_online(agent.last_seen_at)
        out.agent_prints = bool(agent.can_print)
    out.has_andon = (
        await db.execute(
            select(AndonEvent.id)
            .where(AndonEvent.machine_id == machine.id, AndonEvent.happened_at >= datetime.now(UTC) - timedelta(days=7))
            .limit(1)
        )
    ).first() is not None
    # Chek qurilmasi: terminal sarlavhasida «Chek chiqmaydi» / «Qurilmani ulash»
    # belgisi shundan chiqadi. Chek tugmalari yashirilMAYDI — to'siq serverda (E011)
    locked, device = await print_device(db, request, machine)
    out.print_lock = locked
    out.print_allowed = not locked or device is not None
    out.print_pairing = await pairing_open(db, machine)
    if device is not None:
        out.print_device_name = device.name
        await touch_device(db, device)
        # Cookie muddati har ochilishda yangilanadi — ishlab turgan monoblokda
        # u hech qachon tugamaydi (`DEVICE_COOKIE_MAX_AGE` izohi)
        set_device_cookie(response, request.cookies[DEVICE_COOKIE])
    for session in await crew_sessions(db, machine.id):
        employee = await db.get(Employee, session.employee_id)
        out.crew.append(
            _session_read(
                session,
                employee.full_name if employee else "",
                # Qurilma hisobida (TERMINAL) hech bir hodim `user_id` bilan
                # bog'lanmagan - o'shanda hamma chip ko'rinadi, chunki u yerda
                # kim ishlayotganini faqat shu ro'yxat aytadi.
                is_me=bool(employee and employee.user_id == user.id),
            )
        )
    # O'qish tranzaksiyasini yopadi. Ilgari `crew_sessions` muddati o'tgan smenalarni shu
    # yerda yopardi va yozuv saqlanishi kerak edi; 85d5833 dan beri u hech narsa yozmaydi
    await db.commit()
    return out


@router.get("/employees", response_model=list[TerminalEmployee], operation_id="read_terminal_employees")
async def read_terminal_employees(db: SessionDep, _: TerminalUser, ctx: TerminalCtx) -> list[Employee]:
    """Shu postda ishlaydigan faol hodimlar — "Kim ishlayapti?" ro'yxati.

    Monoblok allaqachon TERMINAL hisobi bilan kirgan, ya'ni bu ro'yxat ochiq emas.
    Ismni bosish AUTENTIFIKATSIYA emas, ATRIBUTSIYA: qurilma tanitilgan, endi kim
    ishlayotgani yozib qo'yiladi. Skaneri bor postda beyjik ham shu ishni bajaradi,
    faqat bitta harakat bilan.
    """
    _machine, post = ctx
    rows = (
        await db.execute(
            select(Employee)
            .where(
                Employee.status == EmployeeStatus.ACTIVE,
                Employee.is_deleted == False,  # noqa: E712
                Employee.assigned_post_ids.contains([post.id]),
            )
            .order_by(Employee.full_name)
        )
    ).scalars()
    return list(rows)


@router.post("/session", response_model=SessionRead, operation_id="start_terminal_session")
async def start_terminal_session(
    db: SessionDep, user: TerminalUser, ctx: TerminalCtx, body: ShiftStart, request: Request
) -> SessionRead:
    """Smenani boshlaydi: beyjik skani (`badge_id`) yoki ismni bosish (`employee_id`).

    `join=true` — brigadaga QO'SHILISH (ARRA da ikki kishi birga ishlaydi). Sukut
    bo'yicha esa almashtiradi: ketayotgan odam chiqishni unutsa, keyingi kirish
    eski smenani yopadi.
    """
    machine, post = ctx
    if body.badge_id:
        try:
            employee = await badge_employee(db, body.badge_id, post)
        except ScanRejected as exc:
            raise scan_error(exc.code, exc.message) from None
    elif body.employee_id is not None:
        found = await db.get(Employee, body.employee_id)
        if found is None or found.is_deleted or found.status != EmployeeStatus.ACTIVE:
            raise NotFoundException("Hodim topilmadi yoki nofaol.")
        employee = found
        if post.id not in employee.assigned_post_ids:
            raise scan_error("E006", f"{employee.full_name} bu postda ishlay olmaydi ({post.name}).")
    else:
        raise NotFoundException("Hodim ko'rsatilmagan.")

    session = await open_badge_session(db, user=user, machine=machine, post=post, employee=employee, join=body.join)
    log_action(
        db,
        module="sessions",
        action="started",
        user_id=user.id,
        employee_id=employee.id,
        entity_type="session",
        entity_id=session.id,
        message=f"Smena boshlandi: {employee.full_name} — {machine.name}",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(session)
    await ws_manager.publish(
        "session.started",
        {"session_id": session.id, "employee": employee.full_name, "machine_id": machine.id, "post_id": post.id},
    )
    return _session_read(session, employee.full_name)


@router.post("/session/end", response_model=Message, operation_id="end_terminal_session")
async def end_terminal_session(
    db: SessionDep, user: TerminalUser, ctx: TerminalCtx, request: Request, employee_id: int | None = None
) -> Message:
    """Smenani yakunlaydi. `employee_id` berilsa FAQAT o'shaniki — brigadaning
    qolgani ishlayveradi (biri ketib, ikkinchisi qolishi odatiy hol)."""
    machine, _post = ctx
    crew = await crew_sessions(db, machine.id)
    if employee_id is not None:
        crew = [s for s in crew if s.employee_id == employee_id]
    if not crew:
        raise NotFoundException("Aktiv smena yo'q.")
    for session in crew:
        await end_session(db, session)
        log_action(
            db,
            module="sessions",
            action="ended",
            user_id=user.id,
            employee_id=session.employee_id,
            entity_type="session",
            entity_id=session.id,
            ip=client_ip(request),
        )
    await db.commit()
    for session in crew:
        await ws_manager.publish("session.ended", {"session_id": session.id, "machine_id": machine.id})
    return Message(message="Smena yakunlandi.")


def _bandlar(order: Order) -> list[BandUsage]:
    """Buyurtmadagi kromka lentalari va sarfi (metr), ko'pdan ozga.

    Manba — GibLab'ning O'Z hisobi (`material_usage`, `kind="band"`), qirralarni
    qo'shib chiqish EMAS: GibLab qirqim zaxirasini qo'shadi va ikki buyurtmada
    o'lchanganda farq 7-11% bo'ldi. Texnolog GibLab hisobotida shu sonni ko'radi.

    Guruhlash NOM bo'yicha — `code` ko'pincha bo'sh (prodda 3 tadan 2 tasida).
    """
    bandlar = [
        BandUsage(
            name=(m.get("name") or "?").strip(),
            code=(m.get("code") or None),
            metres=round(float(m.get("count") or 0), 1),
        )
        for m in (order.material_usage or [])
        if m.get("kind") == "band"
    ]
    return sorted(bandlar, key=lambda b: -b.metres)


def _own_sheets(order: Order, own_nos: set[int] | None) -> int:
    """Kartadagi "N list" — SHU postniki. `mult` (bir naqsh necha marta kesiladi) sanaladi.

    `own_nos=None` — post kesish posti emas (kromka, prisadka...), hamma list sanaladi.
    Bo'sh to'plam esa "bu postga bog'langan list yo'q" — 0.
    """
    return sum(
        int(s.get("mult") or 1)
        for mat in (order.cutmap or {}).get("materials", [])
        for s in mat.get("sheets", [])
        if own_nos is None or s.get("no") in own_nos
    )


@router.get("/orders", response_model=list[TerminalOrderCard], operation_id="read_terminal_orders")
async def read_terminal_orders(db: SessionDep, ctx: TerminalCtx) -> list[TerminalOrderCard]:
    """Shu postga tegishli aktiv buyurtmalar — har post terminalining buyurtma tanlagichi uchun."""
    machine, post = ctx
    # SHOSHILINCH tepada tursin: prioritet birinchi, keyin deadline (nulls oxirida)
    rows = (
        await db.execute(
            select(
                Order,
                func.sum(PartRoute.total_done),
                func.sum(PartRoute.total_required),
            )
            .join(PartRoute, PartRoute.order_id == Order.id)
            .where(
                Order.status == OrderStatus.PRODUCTION,
                Order.is_deleted == False,  # noqa: E712
                PartRoute.post_id == post.id,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
                # boshqa ish markaziga biriktirilgan yo'nalishlar bu terminalda ko'rinmasin
                # (aynan shu shart `_post_route_rows()` orqali /kromka va /prisadka da ham)
                (PartRoute.machine_id == machine.id) | (PartRoute.machine_id.is_(None)),
            )
            # `cutmap` va `material_usage` kartada kerak (has_cutmap, sheets_total,
            # materials), qolgan ikki og'ir JSONB bu yerda umuman o'qilmaydi
            .options(defer(Order.survey), defer(Order.machine_assignments))
            .group_by(Order.id)
            .order_by(PRIORITY_RANK, Order.deadline.asc().nulls_last(), Order.id)
        )
    ).all()

    # Agregatlar faqat ro'yxatdagi buyurtmalar bo'yicha — filtrisiz butun bazadagi
    # BARCHA nusxa/skan tarixi har so'rovda qayta hisoblanardi
    order_ids = [o.id for o, *_ in rows]

    # ARRA'da "bajarildi" = chek chiqarilgan YOKI skan qilingan nusxa (kartadagi
    # foiz xarita bilan bir xil o'lchov bo'lsin). Boshqa postlarda faqat skan.
    # Jami ham NUSXA bo'yicha: `sum(total_required)` qadam bo'yicha edi — ikki ARRA qadamli
    # detal (raspil + 45°) hech qachon tugamas, proyekt arrachi ro'yxatidan tushmasdi.
    arra_counts: dict[int, tuple[int, int]] = {}
    if post.code == PostCode.ARRA and order_ids:
        arra_counts = {
            oid: (int(d or 0), int(t or 0))
            for oid, d, t in (
                await db.execute(
                    select(
                        PartInstance.order_id,
                        func.count(
                            func.distinct(
                                case(
                                    (
                                        (PartInstance.label_printed_at.isnot(None)) | (Scan.id.isnot(None)),
                                        PartInstance.id,
                                    )
                                )
                            )
                        ),
                        func.count(func.distinct(PartInstance.id)),
                    )
                    # Faqat ARRA marshruti BOR detallar: aks holda arradan o'tmaydigan
                    # detalning cheki (masalan roverchi o'zi chiqargani) arra hisobini
                    # shishirib, jami'dan oshib ketardi va proyekt arrachi ro'yxatidan
                    # yo'qolardi — listlar hali kesilmagan bo'lsa ham.
                    .join(
                        PartRoute,
                        (PartRoute.part_id == PartInstance.part_id)
                        & (PartRoute.post_id == post.id)
                        & (PartRoute.is_enabled == True)  # noqa: E712
                        & (PartRoute.is_deleted == False),  # noqa: E712
                    )
                    .outerjoin(
                        Scan,
                        (Scan.instance_id == PartInstance.id)
                        & (Scan.post_id == post.id)
                        & (Scan.is_cancelled == False)  # noqa: E712
                        & (Scan.is_deleted == False),  # noqa: E712
                    )
                    .where(
                        PartInstance.order_id.in_(order_ids),
                        PartInstance.is_deleted == False,  # noqa: E712
                    )
                    .group_by(PartInstance.order_id)
                )
            ).all()
        }
    # Kartadagi "N list" faqat SHU postnikini sanashi kerak. Giyotina kesimi listni
    # chetdan chetgacha kesadi, ya'ni listning egasi bitta: yo arra (detallar
    # marshrutida ARRA qadami bor), yo rover (butun listni frezer kesadi).
    # Ilgari hamma list sanalardi — arrachi kartada "7 list" ko'rar, o'ziniki esa
    # 3 ta bo'lar va reja noto'g'ri chamalanardi.
    own_sheet_nos: dict[int, set[int]] | None = None
    if post.code in (PostCode.ARRA, PostCode.ROVER) and order_ids:
        arra_parts = arra_parts_query(PartRoute.order_id.in_(order_ids)).scalar_subquery()
        seen: dict[int, dict[int, set[bool]]] = {}
        for oid, pattern_no, has_arra in (
            await db.execute(
                select(
                    PartInstance.order_id,
                    PartInstance.pattern_no,
                    PartInstance.part_id.in_(arra_parts),
                ).where(
                    PartInstance.order_id.in_(order_ids),
                    PartInstance.pattern_no.isnot(None),
                    PartInstance.is_deleted == False,  # noqa: E712
                )
            )
        ).all():
            seen.setdefault(oid, {}).setdefault(pattern_no, set()).add(bool(has_arra))
        mine = post.code == PostCode.ARRA
        own_sheet_nos = {oid: {no for no, flags in sheets.items() if flags == {mine}} for oid, sheets in seen.items()}

    # KROMKA kartasida hisob DETAL bo'yicha (tomon emas): nusxaning hamma tomoni
    # skan qilingan bo'lsa — qilingan; jami = kromkali nusxalar soni
    kromka_counts: dict[int, tuple[int, int]] = {}
    if post.code == PostCode.KROMKA and order_ids:
        scans_sq = (
            select(Scan.instance_id, func.count(Scan.id).label("cnt"))
            .where(
                Scan.order_id.in_(order_ids),
                Scan.post_id == post.id,
                Scan.is_cancelled == False,  # noqa: E712
                Scan.is_deleted == False,  # noqa: E712
            )
            .group_by(Scan.instance_id)
            .subquery()
        )
        # Kromka marshrutda ikki marta bo'lishi mumkin (kromka -> prisadka -> kromka):
        # detalga to'g'ridan-to'g'ri JOIN qilinsa nusxa ikki marta sanalardi. Shuning
        # uchun avval qadamlar detal bo'yicha yig'iladi — bitta detal, bitta qator.
        need_sq = (
            select(PartRoute.part_id.label("part_id"), func.sum(PartRoute.per_instance).label("need"))
            .where(
                # `part_id` buyurtmaga xos, ya'ni natija o'zgarmaydi — lekin filtrsiz
                # agregat butun `part_route` jadvalini har so'rovda skanerlardi
                PartRoute.order_id.in_(order_ids),
                PartRoute.post_id == post.id,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
            )
            .group_by(PartRoute.part_id)
            .subquery()
        )
        kromka_counts = {
            oid: (int(d or 0), int(t or 0))
            for oid, t, d in (
                await db.execute(
                    select(
                        PartInstance.order_id,
                        func.count(PartInstance.id),
                        func.sum(case((func.coalesce(scans_sq.c.cnt, 0) >= need_sq.c.need, 1), else_=0)),
                    )
                    .join(need_sq, need_sq.c.part_id == PartInstance.part_id)
                    .outerjoin(scans_sq, scans_sq.c.instance_id == PartInstance.id)
                    .where(
                        PartInstance.order_id.in_(order_ids),
                        PartInstance.is_deleted == False,  # noqa: E712
                    )
                    .group_by(PartInstance.order_id)
                )
            ).all()
        }
    result: list[TerminalOrderCard] = []
    for o, done, total in rows:
        done_val = int(done or 0)
        total_val = int(total or 0)
        if post.code == PostCode.ARRA:
            done_val, total_val = arra_counts.get(o.id, (0, 0))
        elif post.code == PostCode.KROMKA:
            done_val, total_val = kromka_counts.get(o.id, (0, 0))
        # Ishi TUGAGAN proyekt ro'yxatni band qilmasin — qolgani keyingi
        # postlarning ishi. `done/total` shu POST bo'yicha hisoblanadi
        # (so'rovda `PartRoute.post_id == post.id`), ya'ni har terminal faqat
        # o'z ishini ko'radi. Ilgari bu qoida faqat ARRA'da ishlardi va boshqa
        # postlarda tugagan proyektlar ro'yxatda abadiy turaverardi.
        if total_val > 0 and done_val >= total_val:
            continue
        result.append(
            TerminalOrderCard(
                id=o.id,
                number=o.number,
                project_name=o.project_name,
                deadline=o.deadline,
                priority=o.priority,
                done=done_val,
                total=total_val,
                # karta uchun: arrachi plita bo'yicha partiyalab kesadi
                materials=[m["name"] for m in o.material_usage if m.get("kind") == "sheet"],
                sheets_total=_own_sheets(o, own_sheet_nos.get(o.id, set()) if own_sheet_nos is not None else None),
                has_cutmap=o.cutmap is not None,
            )
        )
    return result


@router.get("/qr/{qr_text}/order", response_model=QrOrderRef, operation_id="resolve_terminal_qr")
async def resolve_terminal_qr(db: SessionDep, user: TerminalUser, qr_text: str) -> QrOrderRef:
    """Proyekt ro'yxatida turib QR skan qilinsa — qaysi buyurtmaga tegishli ekanini topadi
    (terminal o'sha proyekt sahifasini ochib yuboradi)."""
    qr = qr_text.strip()
    # Aynan moslik — eski `_1` fallback olib tashlandi (scanning.py bilan bir sabab)
    row = (
        await db.execute(
            select(PartInstance.order_id, Order.number)
            .join(Order, Order.id == PartInstance.order_id)
            .where(
                PartInstance.qr_text == qr,
                PartInstance.is_deleted == False,  # noqa: E712
                Order.is_deleted == False,  # noqa: E712
                Order.status == OrderStatus.PRODUCTION,
            )
            .order_by(Order.id.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        raise NotFoundException("Bu QR uchun aktiv buyurtma topilmadi.")
    return QrOrderRef(order_id=row.order_id, order_number=row.number)


async def _post_route_rows(
    db: SessionDep, order_id: int, post_id: int, machine_id: int
) -> Sequence[Row[tuple[PartRoute, Part, str]]]:
    """Buyurtmaning shu post(+ish markazi)dagi marshrutlari: (PartRoute, Part, product_code) qatorlar.
    KROMKA va CNC sahifalari bir xil so'rovni ishlatadi."""
    return (
        await db.execute(
            select(PartRoute, Part, Product.code)
            .join(Part, Part.id == PartRoute.part_id)
            .join(Product, Product.id == Part.product_id)
            .where(
                PartRoute.order_id == order_id,
                PartRoute.post_id == post_id,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
                (PartRoute.machine_id == machine_id) | (PartRoute.machine_id.is_(None)),
            )
            .order_by(Part.code, PartRoute.seq)
        )
    ).all()


async def _joylashuv(
    db: SessionDep, order_id: int
) -> tuple[dict[tuple[int, int], tuple[bool, str | None]], dict[int, list[PartInstance]]]:
    """Har (nusxa, qadam) uchun: shu qadamga YETIB KELGANMI va kelmagan bo'lsa QAYERDA.

    Javob `({(instance_id, route_id): (ready, at)}, nusxalar)`. `ready` — shu
    qadamdan oldingi yoqilgan qadamlarning HAMMASI tugagan; `at` — tugamaganlarining
    birinchisi (ya'ni detal jismonan o'sha postda), `ready` bo'lsa `None`.
    Nusxalar ham qaytariladi: chaqiruvchiga ular baribir kerak va ikki marta
    yuklash bitta so'rovni bekorga takrorlardi.

    Nega postga emas, QADAMGA tayanadi: bitta post marshrutda ikki marta uchraydi
    (kromka -> prisadka -> kromka) va post bo'yicha hisoblasak birinchi o'tishning
    skanlari ikkinchisini ham «tugagan» qilib ko'rsatardi.

    Nega ARRA'ga qotirib bo'lmaydi: prodda 3002 kromka qadamidan 33 tasida oldingi
    qadam ARRA emas (23 PRISADKA, 10 STOLYARKA — nostandart marshrutlar,
    `ARRA -> PRISADKA -> KROMKA` kabi).
    """
    qadamlar = (
        await db.execute(
            select(PartRoute.id, PartRoute.part_id, PartRoute.seq, PartRoute.per_instance, Post.code)
            .join(Post, Post.id == PartRoute.post_id)
            .where(
                PartRoute.order_id == order_id,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
            )
            .order_by(PartRoute.part_id, PartRoute.seq)
        )
    ).all()
    detal_qadamlari: dict[int, list[Any]] = {}
    for q in qadamlar:
        detal_qadamlari.setdefault(q.part_id, []).append(q)

    # Butun buyurtma bo'yicha bitta so'rov: (nusxa, qadam) -> skan soni
    sanoq: dict[tuple[int, int], int] = {
        (iid, rid): int(n)
        for iid, rid, n in (
            await db.execute(
                select(Scan.instance_id, Scan.route_id, func.count(Scan.id))
                .where(
                    Scan.order_id == order_id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .group_by(Scan.instance_id, Scan.route_id)
            )
        ).all()
    }
    nusxalar = await _order_instances_by_part(db, order_id)

    natija: dict[tuple[int, int], tuple[bool, str | None]] = {}
    for part_id, steps in detal_qadamlari.items():
        for i in nusxalar.get(part_id, []):
            oldingilar: list[Any] = []
            for q in steps:
                # Skaner bilan BITTA qoida: `scanning.py` ham xom `per_instance`
                # bilan solishtiradi (`done < step.per_instance`). `max(1, ...)`
                # qo'ysak, nol qadamda ikki joy ikki xil hukm chiqarardi.
                tugamagan = next(
                    (o for o in oldingilar if sanoq.get((i.id, o.id), 0) < o.per_instance),
                    None,
                )
                natija[(i.id, q.id)] = (tugamagan is None, None if tugamagan is None else tugamagan.code)
                oldingilar.append(q)
    return natija, nusxalar


async def _ochiq_braklar(db: SessionDep, order_id: int) -> set[int]:
    """Ochiq braki bor nusxalar. `rejected` — «brak emas», kirmaydi."""
    return set(
        (
            await db.execute(
                select(PartDefect.instance_id).where(
                    PartDefect.order_id == order_id,
                    PartDefect.status.in_((DefectStatus.PENDING, DefectStatus.CONFIRMED)),
                    PartDefect.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )


async def _post_scan_counts(db: SessionDep, order_id: int, post_id: int) -> dict[tuple[int, int], int]:
    """Har nusxaning shu postdagi haqiqiy skanlari QADAM bo'yicha: {(instance_id, route_id): count}.

    Kalit qadam (route_id) — post emas: bitta post marshrutda ikki marta bo'lsa
    (kromka -> prisadka -> yana kromka) birinchi o'tishning skanlari ikkinchisini
    ham "bajarildi" qilib ko'rsatardi va operator qaytib kelmasdi."""
    rows = (
        (
            await db.execute(
                select(Scan.instance_id, Scan.route_id, func.count(Scan.id))
                .where(
                    Scan.order_id == order_id,
                    Scan.post_id == post_id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
                .group_by(Scan.instance_id, Scan.route_id)
            )
        )
        .tuples()
        .all()
    )
    return {(instance_id, route_id): count for instance_id, route_id, count in rows}


async def _order_instances_by_part(db: SessionDep, order_id: int) -> dict[int, list[PartInstance]]:
    """Buyurtmaning jonli nusxalari detal bo'yicha guruhlangan, instance_no tartibida."""
    by_part: dict[int, list[PartInstance]] = {}
    for inst in (
        (
            await db.execute(
                select(PartInstance)
                .where(
                    PartInstance.order_id == order_id,
                    PartInstance.is_deleted == False,  # noqa: E712
                )
                .order_by(PartInstance.part_id, PartInstance.instance_no)
            )
        )
        .scalars()
        .all()
    ):
        by_part.setdefault(inst.part_id, []).append(inst)
    return by_part


def _teshik(xarita: dict[int, dict[str, Any]], label_num: int | None) -> CutmapHole | None:
    """JSONB dan kelgan xom dict ni sxemaga o'giradi (mypy uchun ham aniq tur)."""
    if label_num is None:
        return None
    raw = xarita.get(label_num)
    return CutmapHole.model_validate(raw) if raw else None


@router.get("/orders/{order_id}/kromka", response_model=KromkaOrderState, operation_id="read_terminal_kromka")
async def read_terminal_kromka(db: SessionDep, ctx: TerminalCtx, order_id: int) -> KromkaOrderState:
    """KROMKA/OVAL sahifasi: buyurtmaning shu postdagi detallari, har nusxada tomon-progress
    (OVAL'da 0/1) va YETIB KELGANLIK — marshrutdagi oldingi qadam tugaganmi (`_joylashuv`).
    Kelmagan nusxa ham qaytariladi, `at` bilan: kromkachi yetishmayotgani qaysi detal
    ekanini va qayerdaligini ko'rishi kerak."""
    machine, post = ctx
    if post.code not in (PostCode.KROMKA, PostCode.OVAL):
        raise ForbiddenException("Bu sahifa faqat KROMKA yoki OVAL postida ko'rsatiladi.")

    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)

    rows = await _post_route_rows(db, order.id, post.id, machine.id)
    kromka_done = await _post_scan_counts(db, order.id, post.id)

    joy, by_part = await _joylashuv(db, order.id)
    braklar = await _ochiq_braklar(db, order.id)

    qirra_amali = {part.id: stored_machined_sides(part.xnc_summary) for _, part, _ in rows}
    # Teshik o'rinlari CHEK bilan bitta manbadan — kromkachi qo'lidagi detalni
    # eskizga moslab, qaysi qirra lentalanishini aniqlaydi. Xarita BIR MARTA
    # quriladi: har detal uchun alohida qidirish O(detal x katak) bo'lardi.
    teshiklar = holes_by_label_num(order.cutmap)

    return KromkaOrderState(
        order_id=order.id,
        order_number=order.number,
        project_name=order.project_name,
        bands=_bandlar(order),
        parts=[
            KromkaPartRow(
                part_id=part.id,
                route_id=route.id,
                code=f"{product_code}_{part.code}",
                name=part.name,
                length=part.length,
                width=part.width,
                thickness=part.thickness,
                sides=route.per_instance,
                edges=part.edges,
                paz_sides=qirra_amali[part.id].paz,
                frez_sides=qirra_amali[part.id].frez,
                holes=_teshik(teshiklar, part.label_num),
                process_code=route.process_code,
                total_done=route.total_done,
                total_required=route.total_required,
                instances=[
                    KromkaInstance(
                        instance_id=i.id,
                        instance_no=i.instance_no,
                        qr_text=i.qr_text,
                        done=int(kromka_done.get((i.id, route.id), 0)),
                        ready=joy.get((i.id, route.id), (True, None))[0],
                        at=joy.get((i.id, route.id), (True, None))[1],
                        defect=i.id in braklar,
                    )
                    for i in by_part.get(part.id, [])
                ],
            )
            for route, part, product_code in rows
        ],
    )


#: Terminal ekranida ko'rsatiladigan oxirgi o'lchovlar soni — tasmaga shuncha sig'adi.
_KROMKA_OLCHOV_N = 8


@router.get("/kromka/measurements", response_model=list[KromkaMeasurement], operation_id="read_kromka_measurements")
async def read_kromka_measurements(db: SessionDep, _: TerminalUser, ctx: TerminalCtx) -> list[KromkaMeasurement]:
    """Kromka stansiyasi o'lchagan oxirgi detallar — SHU ish markazida, hukmi bilan.

    Hukm o'lchov kelganda qo'yiladi (`services/kromka.py`): o'lchov o'sha lahzadagi
    oxirgi skanga bog'lanadi. Stansiya ulanmagan postda bo'sh ro'yxat qaytadi va
    ekranda hech narsa chizilmaydi."""
    machine, _post = ctx
    rows = (
        (
            await db.execute(
                select(
                    KromkaMeasurementRecord,
                    Part.name,
                    PartInstance.qr_text,
                )
                .outerjoin(PartInstance, PartInstance.id == KromkaMeasurementRecord.instance_id)
                .outerjoin(Part, Part.id == PartInstance.part_id)
                .where(
                    KromkaMeasurementRecord.machine_id == machine.id,
                    KromkaMeasurementRecord.is_deleted == False,  # noqa: E712
                )
                .order_by(KromkaMeasurementRecord.measured_at.desc(), KromkaMeasurementRecord.id.desc())
                .limit(_KROMKA_OLCHOV_N)
            )
        )
        .tuples()
        .all()
    )

    def son(v: float | None) -> float | None:
        # Numeric ustun Decimal bo'lib keladi — JSON uchun float
        return float(v) if v is not None else None

    return [
        KromkaMeasurement(
            at=row.measured_at,
            length_mm=son(row.measured_mm),
            code=row.code,
            verdict=row.verdict.value,
            expected_mm=son(row.expected_mm),
            delta_mm=son(row.delta_mm),
            part_name=part_name,
            qr_text=qr_text,
            scan_id=row.scan_id,
            pack_n=row.pack_n,
        )
        for row, part_name, qr_text in rows
    ]


@router.get("/orders/{order_id}/prisadka", response_model=PrisadkaOrderState, operation_id="read_terminal_prisadka")
async def read_terminal_prisadka(db: SessionDep, ctx: TerminalCtx, order_id: int) -> PrisadkaOrderState:
    """CNC post sahifasi (PRISADKA/ROVER): shu postga tegishli detallar +
    SCX fayllari (stanok kompyuteriga yuklab olish uchun). ROVER'da
    jarayon arradan EMAS, roverdan boshlanishi ham mumkin — shunday detallarga
    QR chekni shu sahifadan chiqarish uchun arra_route belgisi ham beriladi."""
    machine, post = ctx
    if post.code not in (PostCode.PRISADKA, PostCode.ROVER):
        raise ForbiddenException("Bu sahifa faqat CNC postlarida (PRISADKA/ROVER) ko'rsatiladi.")

    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)

    rows = await _post_route_rows(db, order.id, post.id, machine.id)

    files_by_part: dict[int, list[PrisadkaFile]] = {}
    for f in (
        (
            await db.execute(
                select(OrderFile).where(
                    OrderFile.order_id == order.id,
                    OrderFile.kind == FileKind.SCX,
                    OrderFile.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    ):
        if f.part_id is not None:
            files_by_part.setdefault(f.part_id, []).append(PrisadkaFile(id=f.id, filename=f.filename))

    # Har nusxaning shu postdagi holati: 2/4 ko'rsatishning o'zi QAYSI nusxalar
    # qolganini aytmaydi — fayl (nomi = nusxa QR'i) yashil/kulrang bo'lib ko'rsatadi
    scan_counts = await _post_scan_counts(db, order.id, post.id)
    insts_by_part = await _order_instances_by_part(db, order.id)

    # ROVER'da jarayon arradan boshlanmasligi mumkin: marshrutida ARRA yo'q
    # detalning QR cheki shu sahifadan chiqariladi. ARRA'li detalga bu yerdan
    # chek chiqarish TAQIQ — arra statistikasi ("chek chiqarilgan = kesilgan")
    # buzilardi, chek arrachi tomonidan chiqadi.
    arra_part_ids = set((await db.execute(arra_parts_query(PartRoute.order_id == order.id))).scalars().all())

    # Teshiklar SAHIFADAGI detallar bo'yicha — `rows` allaqachon shu postga
    # marshrutlangan; boshqa manbadan olinsa karta va ro'yxat farq qilardi.
    teshikli = {part.id: part for _, part, _ in rows}
    return PrisadkaOrderState(
        order_id=order.id,
        order_number=order.number,
        project_name=order.project_name,
        holes_face=sum(int((p.xnc_summary or {}).get("bores") or 0) * p.count for p in teshikli.values()),
        holes_edge=sum(int((p.xnc_summary or {}).get("edge_bores") or 0) * p.count for p in teshikli.values()),
        parts=[
            PrisadkaPartRow(
                part_id=part.id,
                route_id=route.id,
                code=f"{product_code}_{part.code}",
                name=part.name,
                length=part.length,
                width=part.width,
                thickness=part.thickness,
                done=route.total_done,
                total=route.total_required,
                files=files_by_part.get(part.id, []),
                arra_route=part.id in arra_part_ids,
                # Nusxa darajasi: QR chiqarish tugmasi va holat uchun (helper instance_no bo'yicha saralaydi)
                instances=[
                    PrisadkaInstance(
                        instance_id=i.id,
                        qr_text=i.qr_text,
                        label_printed=i.label_printed_at is not None,
                        done=scan_counts.get((i.id, route.id), 0) >= route.per_instance,
                        scans=scan_counts.get((i.id, route.id), 0),
                        need=route.per_instance,
                    )
                    for i in insts_by_part.get(part.id, [])
                ],
            )
            for route, part, product_code in rows
        ],
    )


@router.get("/orders/{order_id}/cutmap", response_model=CutmapState, operation_id="read_terminal_cutmap")
async def read_terminal_cutmap(db: SessionDep, ctx: TerminalCtx, order_id: int) -> CutmapState:
    """Kesish xaritasi. Katak holati serverda — terminal qayta yonganda saqlanadi.

    ROVER ham ochadi: marshruti arradan boshlanmagan detallar butun listni frezerda
    kesish bilan chiqadi, ya'ni roverchiga ham joylashuv kerak. Har post O'Z skanlarini
    ko'radi (`done`), listlarni esa frontend `arra_route` bo'yicha ajratadi.
    """
    _machine, post = ctx
    if post.code not in (PostCode.ARRA, PostCode.ROVER):
        raise ForbiddenException("Kesish xaritasi faqat arra va rover postida ko'rsatiladi.")

    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)
    return await build_cutmap_state(db, order, post.id)


@router.get("/orders/{order_id}/queue", response_model=PostQueueState, operation_id="read_terminal_post_queue")
async def read_terminal_post_queue(db: SessionDep, ctx: TerminalCtx, order_id: int) -> PostQueueState:
    """Post navbati NUSXA darajasida (BOYOQ): kelganlar, kutilayotganlar, bajarilganlar.

    Umumiy "Navbatdagi vazifalar" ro'yxati detal darajasida agregat berardi
    ("qoldiq 6/6") — bo'yoqchi qaysi buyumni bo'yaganini undan bilib bo'lmasdi.
    Bu yerda har nusxa alohida qator: skan qilinganda o'sha qator ro'yxatdan
    chiqadi. Material ham beriladi — bo'yoqchi uchun bu RANG.
    """
    _machine, post = ctx
    order = await crud_orders.get_or_404(db, "Buyurtma topilmadi.", id=order_id)
    stages = await instance_stages(db, order, post)

    rows = (
        await db.execute(
            select(PartInstance, Part, Product.code, PartRoute)
            .join(Part, Part.id == PartInstance.part_id)
            .join(Product, Product.id == Part.product_id)
            .join(
                PartRoute,
                (PartRoute.part_id == Part.id)
                & (PartRoute.post_id == post.id)
                & (PartRoute.is_enabled == True)  # noqa: E712
                & (PartRoute.is_deleted == False),  # noqa: E712
            )
            .where(
                PartInstance.order_id == order.id,
                PartInstance.is_deleted == False,  # noqa: E712
            )
            .order_by(Product.code, Part.code, PartInstance.instance_no)
        )
    ).all()
    if not rows:
        return PostQueueState(
            order_id=order.id,
            order_number=order.number,
            project_name=order.project_name,
            post_code=post.code,
            rows=[],
        )

    counts = await _post_scan_counts(db, order.id, post.id)
    # Yig'ma qatori HAR BIR ota nusxaga nechta bola detal tushishini aytadi:
    # `child.count` butun buyurtma bo'yicha (10 ota × 2 = 20), stolyar esa bitta
    # buyumni yig'adi — «×20» uni chalg'itardi. Bo'linmasa jami bilan yoziladi.
    parent_count = {p.id: p.count for _i, p, _pc, _r in rows}
    children: dict[int, list[str]] = {}
    for child, product_code in (
        await db.execute(
            select(Part, Product.code)
            .join(Product, Product.id == Part.product_id)
            .where(
                Part.assembly_parent_id.in_({p.id for _i, p, _pc, _r in rows}),
                Part.is_deleted == False,  # noqa: E712
            )
            .order_by(Part.code)
        )
    ).all():
        assert child.assembly_parent_id is not None
        pc = parent_count.get(child.assembly_parent_id) or 0
        per = child.count // pc if pc and child.count % pc == 0 else None
        label = f"×{per}" if per is not None else f"×{child.count} jami"
        children.setdefault(child.assembly_parent_id, []).append(f"{product_code}_{child.code} {label}")

    out = [
        PostQueueRow(
            instance_id=instance.id,
            qr_text=instance.qr_text,
            part_code=f"{product_code}_{part.code}",
            part_name=part.name,
            length=part.length,
            width=part.width,
            thickness=part.thickness,
            material=part.material_name,
            note=part.note,
            process_code=route.process_code,
            ready=stages.get(instance.id, (False, ""))[0],
            stage=stages.get(instance.id, (False, ""))[1],
            done=counts.get((instance.id, route.id), 0) >= route.per_instance,
            assembly=children.get(part.id, []),
        )
        for instance, part, product_code, route in rows
    ]
    # Ishga tayyorlari tepada, bajarilganlari pastda — bo'yoqchi tepadan ishlaydi.
    out.sort(key=lambda r: (r.done, not r.ready, r.part_code, r.qr_text))
    return PostQueueState(
        order_id=order.id,
        order_number=order.number,
        project_name=order.project_name,
        post_code=post.code,
        rows=out,
    )


async def _require_print_device(db: SessionDep, request: Request, user: User, machine: Machine | None) -> None:
    try:
        await require_print_device(db, request, user, machine)
    except ScanRejected as exc:
        raise scan_error(exc.code, exc.message) from None


async def _claim_label(db: SessionDep, model: type[PartInstance] | type[WasteItem], row_id: int, **values: Any) -> None:
    """BIR NUSXA — BIR CHEK: `label_printed_at` faqat bo'sh bo'lsa yoziladi (atomik).

    Ilgari server tekshirmasdi: katak bosilganda xarita eskirgan bo'lsa (ikki
    qurilmada ochiq, yoki tugma ikki marta bosilgan) bitta nusxaning ikki cheki
    chiqardi — 2026-09-24 da ular ikki xil detalga yopishtirilgan va kromkada
    detal "chiqmagan" ko'rinib qolgan. Ikki parallel so'rovda ikkinchisining
    UPDATE'i birinchisining commit'ini kutadi va 0 qator qaytaradi.
    Qayta chiqarish — faqat bekor qilish orqali (terminal ham shunday qiladi).
    """
    claimed = (
        await db.execute(
            update(model)
            .where(model.id == row_id, model.label_printed_at.is_(None))
            .values(label_printed_at=datetime.now(UTC), **values)
            .returning(model.id)
        )
    ).first()
    if claimed is not None:
        return
    printed_at = (await db.execute(select(model.label_printed_at).where(model.id == row_id))).scalar_one_or_none()
    vaqt = f" ({printed_at.astimezone(TASHKENT_TZ).strftime('%d-%m %H:%M')})" if printed_at else ""
    raise scan_error(
        "E012",
        f"Bu chek allaqachon chiqarilgan{vaqt}. Qayta chiqarish kerak bo'lsa — avval eskisini bekor qiling.",
    )


@router.post("/waste/{waste_id}/label", response_model=Message, operation_id="print_waste_item_label")
async def print_waste_item_label(db: SessionDep, user: TerminalUser, waste_id: int, request: Request) -> Message:
    """FOYDALI ATXOT cheki (GibLab `business` qoldig'i, GibSaw'dagi "Деловой
    остаток" chekining muqobili): kesish xaritasidagi atxot katagidan chiqariladi.

    Detal chekidan farqi: marshrut/skan tekshiruvi yo'q — atxot ish bosqichi
    emas, saqlanadigan material. QR prefiksi ATX- bo'lgani uchun skan dvijoki
    uni detal deb qidirmaydi.
    """
    w = await crud_waste_items.get_or_404(db, "Atxot yozuvi topilmadi.", id=waste_id)

    print_machine: Machine | None = None
    try:
        print_machine, _waste_post = await resolve_terminal(db, user)
    except ScanRejected:
        pass
    await _require_print_device(db, request, user, print_machine)

    from app.core.utils import queue

    try:
        agent = await require_printer(db, print_machine.id if print_machine else None)
    except NoPrinterBound:
        raise HTTPException(
            status_code=422,
            detail="Bu ish markaziga printer biriktirilmagan — atxot cheki yuborilmadi.",
        ) from None

    log_action(
        db,
        module="print",
        action="waste_label_sent",
        user_id=user.id,
        entity_type="waste_item",
        entity_id=w.id,
        message=f"Qoldiq cheki yuborildi: {w.qr_text} ({w.length:g}x{w.width:g})",
    )
    # `label_printed_at` SHU YERDA — detal cheki bilan bir xil (`print_instance_label`).
    # Ilgari uni ARQ vazifasi yozardi: javob qaytgach terminal darhol qayta so'rasa
    # worker hali ishlamagan bo'lar va katak rangi o'zgarmasdi — faqat keyingi
    # yangilashda ko'rinardi. Detal chekida bunday muammo yo'q edi, ya'ni bitta
    # xaritada ikki xil xulq.
    await _claim_label(db, WasteItem, w.id)
    printer_kutilmoqda = not agent_online(agent.last_seen_at)
    if queue.pool is not None:
        await queue.pool.enqueue_job("print_waste_label", waste_id, agent.id)
    await db.commit()
    return Message(
        message=(
            f"Printer ulanmagan. Atxot cheki saqlandi — printer ulanganda chiqadi: {w.qr_text}"
            if printer_kutilmoqda
            else f"Atxot cheki yuborildi: {w.qr_text}"
        )
    )


@router.post("/labels/{instance_id}", response_model=Message, operation_id="print_instance_label")
async def print_instance_label(db: SessionDep, user: TerminalUser, instance_id: int, request: Request) -> Message:
    """YORLIQ CHOP ETISH: on-demand, per selected cell. Queued to the bridge-agent."""
    instance = await crud_part_instances.get_or_404(db, "Nusxa topilmadi.", id=instance_id)

    # Post aniqlanmasa `print_post=None` — faqat ARRA/ROVER tekshiruvlari o'tkazib yuboriladi;
    # ish markazisiz terminal pastda `require_printer` da 422 oladi (chek chiqmaydi)
    print_machine: Machine | None = None
    try:
        print_machine, print_post = await resolve_terminal(db, user)
    except ScanRejected:
        print_post = None
    await _require_print_device(db, request, user, print_machine)
    arra_route = (await db.execute(arra_parts_query(PartRoute.part_id == instance.part_id))).first()
    # Marshruti arradan boshlanmagan detal arrachiga TEGISHLI EMAS: uning listini
    # frezer butunlay o'zi kesadi. Ilgari chek jimgina chiqar, skan esa E001 bilan
    # yutilar edi — katak "kesildi" bo'lib yashil qolar, roverchining chek tugmasi
    # esa `label_printed` sababli yo'qolardi va u qo'lda skanerlashga majbur bo'lardi.
    if print_post is not None and print_post.code == PostCode.ARRA and arra_route is None:
        raise scan_error("E001", "Bu detal roverda kesiladi — chekni rover terminalidan chiqaring.")

    # CHEK = BOSQICH. Kesish postlarida chop etishning O'ZI bosqichni yopadi —
    # pastda avto-skan yoziladi. Skan esa smenasiz YOZILMAYDI (`Scan.employee_id`
    # va `session_id` NOT NULL: ish kimga yozilishi ma'lum bo'lishi kerak).
    # Shuning uchun smena SHU YERDA, chek chiqishidan OLDIN talab qilinadi.
    #
    # Ilgari tekshiruv faqat pastda edi: chek chiqar, avto-skan esa E005 bilan
    # JIMGINA yutilardi (`except ScanRejected` — na xabar, na log). Natijada
    # qog'oz arrachining qo'lida, katak xaritada yashil (`label_printed_at`),
    # lekin `total_done` 0 — detal boshqa hamma ekranda "o'tmagan" bo'lib
    # qolardi. Prodda B-2026-037 buyurtmasida smena yopiq 32 daqiqada aynan
    # shunday 19 ta detal yo'qolgan.
    cut_by_print = print_post is not None and (
        print_post.code == PostCode.ARRA or (print_post.code == PostCode.ROVER and arra_route is None)
    )
    crew_session = None
    if cut_by_print and print_machine is not None:
        try:
            crew_session = await active_session(db, print_machine)
        except ScanRejected as exc:
            raise scan_error(exc.code, exc.message) from None

    # `qr_text` SHU YERDA olinadi: quyida `record_scan` rad etilsa `db.rollback()`
    # chaqiriladi va u identity map'dagi HAMMA obyektni expire qiladi. O'shandan
    # keyin `instance.qr_text` ni o'qish lazy refresh talab qilib, async kontekstda
    # `MissingGreenlet` bilan yiqilardi: chek fizik chiqib turib, terminal xato
    # ko'rsatardi va operator chek chiqmadi deb o'ylardi.
    qr_text = instance.qr_text
    # `user.id` ham SHU YERDA: `log_action` quyida rollbackdan KEYIN chaqiriladi va
    # o'shanda `user` ham expire bo'lgan bo'ladi — o'qish MissingGreenlet berardi.
    user_id = user.id
    # Chekni kim chiqargani nusxaning O'ZIDA qoladi — bekor qilish huquqi shundan
    await _claim_label(db, PartInstance, instance.id, label_post_id=print_post.id if print_post is not None else None)
    log_action(
        db,
        module="print",
        action="label_sent",
        user_id=user.id,
        entity_type="part_instance",
        entity_id=instance.id,
        message=f"Chek chop etishga yuborildi: {qr_text}",
    )

    from app.core.utils import queue

    # Chek SO'RAGAN ish markazining printeriga manzillanadi. Printer biriktirilmagan
    # bo'lsa chek YUBORILMAYDI: ilgari u umumiy navbatga tushib, boshqa postdagi —
    # hatto ofisdagi test — printeri uni tortib olardi. Jim noto'g'ri printerdan
    # chiqqan chek, ochiq xatodan yomonroq: operator qog'ozni kutib turaveradi.
    try:
        agent = await require_printer(db, print_machine.id if print_machine else None)
    except NoPrinterBound:
        raise HTTPException(
            status_code=422,
            detail=(
                f"{print_post.name if print_post else 'Bu post'} ish markaziga printer biriktirilmagan — "
                "chek yuborilmadi. Admin /agents sahifasida agentni ish markaziga bog'lashi kerak."
            ),
        ) from None
    print_agent_id = agent.id
    # Printer ulanmagan bo'lsa buni AYTAMIZ. Ilgari xabar doim bir xil edi
    # ("yuborildi"), operator esa qog'oz kutib turardi va sababini bilmasdi.
    # Job Redisda saqlanadi — agent ulanganda chiqadi, ya'ni yo'qolmaydi.
    printer_kutilmoqda = not agent_online(agent.last_seen_at)
    # Navbatga qo'yish COMMIT'DAN OLDIN. Teskari tartibda Redis uzilib qolsa
    # `label_printed_at` allaqachon yozilgan bo'lardi: qog'oz chiqmaydi, lekin
    # katak "chiqarilgan" bo'lib qulflanadi va operator faqat bekor qilish orqali
    # chiqa olardi. Bu tartibda esa eng yomon holat — ortiqcha yorliq, u qulfdan
    # ancha arzon.
    if queue.pool is not None:
        await queue.pool.enqueue_job("print_label", instance_id, print_agent_id)
    await db.commit()
    await ws_manager.publish("label.printed", {"instance_id": instance_id, "qr_text": qr_text})
    natija = (
        f"Printer ulanmagan. Chek saqlandi — printer ulanganda o'zi chiqadi: {qr_text}"
        if printer_kutilmoqda
        else f"Chek chop etishga yuborildi: {qr_text}"
    )

    # "CHEK = ISH BAJARILDI" — kesish postlarida chop etishning o'zi bosqichni yopadi.
    # ARRA'da arrachi xaritada katakni bosib chek chiqaradi va alohida skan qilmaydi
    # (xarita ochiqda terminalning skan maydoni ham yashirin). ROVER'da esa marshruti
    # arradan boshlanmagan detal roverning O'ZIDA kesiladi.
    #
    # Skan yozuvisiz `PartRoute.total_done` hech qachon o'smaydi: buyurtma COMPLETED
    # bo'lmaydi va qat'iy tartibda KEYINGI postlarning hammasi E004 bilan rad etiladi.
    # Shuning uchun chop etish shu yerda skan ham yozadi — "bajarildi" ta'rifi
    # hamma joyda (total_done, TABLO, ish haqi, tartib nazorati) bitta bo'lsin.
    # Rad etilsa (oldingi bosqich tugamagan) chek baribir chiqqan bo'ladi — operator
    # keyin qo'lda skan bilan yakunlaydi.
    # Ish markazi yo'q terminal bu yergacha yetmaydi (`require_printer` 422 beradi) —
    # shart faqat `record_scan_at` uchun tiplarni toraytiradi.
    if print_post is None or print_machine is None:
        return Message(message=natija)
    if cut_by_print and crew_session is not None:
        try:
            # Har chop etish ALOHIDA hodisa: `cutprint-{id}` doimiy bo'lganda
            # chek bekor qilinib qayta chiqarilsa, idempotentlik tekshiruvi eski
            # (bekor qilingan) qatorni topib `duplicate` qaytarardi — yangi skan
            # yozilmas, `total_done` o'smas, holat "Bajarilmagan" bo'lib qolardi.
            # Kontekst tepada allaqachon hal qilingan — `record_scan` uni `user`dan
            # QAYTA topardi (pachka.py/tmo.py ham shu yo'ldan boradi)
            outcome = await record_scan_at(
                db,
                machine=print_machine,
                post=print_post,
                session=crew_session,
                qr_text=qr_text,
                client_event_id=f"cutprint-{instance.id}-{int(datetime.now(UTC).timestamp())}",
            )
            await finalize_scan(db, outcome, user_id=user.id, source=" (chek chiqarish bilan)", auto=True)
        except ScanRejected as exc:
            # Smena tepada tekshirilgan, ya'ni bu yerga faqat BOSHQA sabab
            # yetib keladi (masalan E004 — oldingi bosqich yopilmagan).
            # Jimgina yutish AYNAN shu nuqsonni bergan edi: chek qo'lda,
            # bosqich esa yopilmagan. Endi operator sababini ko'radi va
            # audit izida ham qoladi.
            await db.rollback()
            log_action(
                db,
                module="print",
                action="rejected",
                user_id=user_id,
                entity_type="part_instance",
                entity_id=instance_id,
                message=f"Chek chiqdi, lekin bosqich yopilmadi: {qr_text} — {exc.message}",
                meta={"code": exc.code},
            )
            await db.commit()
            natija = f"{natija}. DIQQAT: bosqich yopilmadi — {exc.message}"

    return Message(message=natija)


# Bekor qilishga admin webdagi xarita egalari ham kiradi: proyekt ro'yxatdan
# tushib bo'lgach arrachi xaritani ocholmaydi — oxirgi xato chekni texnolog tuzatadi
LabelCancelUser = Annotated[
    User, Depends(require_roles(UserRole.TERMINAL, *POST_ROLES, UserRole.MANAGER, UserRole.TEXNOLOG))
]


def _is_office(user: User) -> bool:
    """Ofis rollari (menejer/texnolog/admin) chekni admin webdagi xaritadan bekor qiladi —
    ularga post/qurilma tekshiruvi qo'llanmaydi (terminal konteksti yo'q, E009 bo'lardi)."""
    return user.is_superuser or UserRole(user.role) in (UserRole.MANAGER, UserRole.TEXNOLOG, UserRole.ADMIN)


@router.delete("/waste/{waste_id}/label", response_model=Message, operation_id="cancel_waste_item_label")
async def cancel_waste_item_label(db: SessionDep, user: LabelCancelUser, waste_id: int, request: Request) -> Message:
    """Qoldiq chekini bekor qilish: `label_printed_at` tozalanadi.

    Detal chekidan farqi — bu yerda qaytariladigan skan yo'q (qoldiq ish
    bosqichi emas), shuning uchun faqat belgi tozalanadi va katak xaritada
    yana "chek chiqarilmagan" rangga qaytadi.

    Chek qurilmasi: bekor qilish ham chop etish bilan bir xil to'siladi (E011) —
    aks holda telefon chekni bekor qilar, monoblok esa o'sha qoldiqqa ikkinchi,
    bir xil chek chiqarardi (E012 faqat BEKOR QILINMAGAN chekni himoya qiladi).
    """
    w = await crud_waste_items.get_or_404(db, "Qoldiq yozuvi topilmadi.", id=waste_id)
    if not _is_office(user):
        cancel_machine: Machine | None = None
        try:
            cancel_machine, _cancel_post = await resolve_terminal(db, user)
        except ScanRejected:
            pass
        await _require_print_device(db, request, user, cancel_machine)
    w.label_printed_at = None
    log_action(
        db,
        module="print",
        action="waste_label_cancelled",
        user_id=user.id,
        entity_type="waste_item",
        entity_id=w.id,
        message=f"Qoldiq cheki bekor qilindi: {w.qr_text}",
    )
    await db.commit()
    return Message(message=f"Qoldiq cheki bekor qilindi: {w.qr_text}")


@router.delete("/labels/{instance_id}", response_model=Message, operation_id="cancel_instance_label")
async def cancel_instance_label(db: SessionDep, user: LabelCancelUser, instance_id: int, request: Request) -> Message:
    """Chekni bekor qilish (long press / admin xarita): noto'g'ri chiqarilgan yorliq
    katakni chop etilmagan holatga qaytaradi."""
    instance = await crud_part_instances.get_or_404(db, "Nusxa topilmadi.", id=instance_id)

    # Kesish postlarida chek chiqarish skan ham yozadi ("chek = kesildi"), shuning
    # uchun bekor qilish o'sha skanni ham qaytarishi shart — aks holda katak yashil
    # bo'lib qolar va qadam hisobi (`total_done`) oshgan holida qolardi. Faqat
    # chop etish yozgan skan bekor bo'ladi: operator qo'lda qilgan skanga tegilmaydi.
    auto_scans = (
        (
            await db.execute(
                select(Scan).where(
                    Scan.instance_id == instance.id,
                    # Eski shakl (`cutprint-12`) ham, yangisi (`cutprint-12-1755…`)
                    # ham: har chop etish o'z hodisa nomi bilan yoziladi
                    Scan.client_event_id.in_([f"cutprint-{instance.id}", f"rvprint-{instance.id}"])
                    | Scan.client_event_id.like(f"cutprint-{instance.id}-%"),
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )

    # HAR KIM FAQAT O'Z POSTINI BEKOR QILADI. Ilgari tekshiruv umuman yo'q edi:
    # roverchi ro'yxatida arradan kelgan detallar ham turadi va ularda uzoq bosish
    # ishlar edi — ya'ni roverchi arrachining kesish skanini qaytarib, katakni
    # "kesilmagan" holatga tushira olardi (va aksincha, API orqali arrachi
    # rovernikini). Skanning O'ZIDAGI `post_id` dalil bo'lib xizmat qiladi:
    # marshrutdan taxmin qilinmaydi.
    #
    # Menejer/texnolog/admin — ataylab istisno: proyekt ro'yxatdan tushib
    # bo'lgach arrachi xaritani ocholmaydi, oxirgi xato chekni texnolog tuzatadi.
    if not _is_office(user):
        try:
            caller_machine, caller_post = await resolve_terminal(db, user)
        except ScanRejected as exc:
            raise scan_error(exc.code, exc.message) from None
        # Chek qurilmasi: telefondan bekor qilib, monoblokdan ikkinchi bir xil
        # chek chiqarish yo'li yopiladi (chop etish bilan bir xil qoida, E011)
        await _require_print_device(db, request, user, caller_machine)
        if caller_post.code not in (PostCode.ARRA, PostCode.ROVER):
            raise ForbiddenException("Chekni faqat kesish posti (ARRA yoki ROVER) bekor qila oladi.")
        # Skan dalili — bajarilgan ISHNI himoya qiladi (`total_done` qaytmasin)
        foreign = next((sc for sc in auto_scans if sc.post_id != caller_post.id), None)
        if foreign is not None:
            owner = await db.get(Post, foreign.post_id)
            raise ForbiddenException(
                f"Bu detalni {owner.name if owner else 'boshqa post'} kesgan — bekor qilishni o'sha post bajaradi."
            )
        # Nusxadagi yozuv — CHEKNING o'zini himoya qiladi. Chek chiqib, skan
        # yozilmasligi mumkin (roverchi arradan keladigan detalning chekini
        # chiqarsa, `record_scan` E001 bilan rad etadi) — o'shanda skanda dalil
        # qolmaydi va ilgari boshqa post chekni tozalab yubora olardi.
        if instance.label_post_id is not None and instance.label_post_id != caller_post.id:
            owner = await db.get(Post, instance.label_post_id)
            raise ForbiddenException(
                f"Bu chekni {owner.name if owner else 'boshqa post'} chiqargan — bekor qilishni o'sha post bajaradi."
            )

    instance.label_printed_at = None
    instance.label_post_id = None
    # `revoke_scan` — bekor qilishning YAGONA shakli: hosila skanlar ham qaytadi
    # va COMPLETED buyurtma PRODUCTION ga tushadi. Ilgari bu yerda faqat
    # hisoblagich kamayardi, ya'ni chek bekor qilingan buyurtma "tayyor" bo'lib
    # turaverardi.
    for scan in auto_scans:
        await revoke_scan(db, scan)
    log_action(
        db,
        module="print",
        action="label_cancelled",
        user_id=user.id,
        entity_type="part_instance",
        entity_id=instance.id,
        message=f"Chek bekor qilindi: {instance.qr_text}",
    )
    await db.commit()
    await ws_manager.publish("label.cancelled", {"instance_id": instance_id, "qr_text": instance.qr_text})
    return Message(message=f"Chek bekor qilindi: {instance.qr_text}")


# Chek rasmi FAQAT ofisga (menejer/texnolog; admin va superuser `require_roles`
# da o'zi o'tadi). Terminal va post hisoblari uni ko'rmaydi: rasm istalgan
# printerdan chiqariladigan to'liq chek — telefondagi arrachi uni olib, E011 va
# E012 ni aylanib o'tib chekni o'zi chop eta olardi. Tsexda uni hech kim
# chaqirmaydi: terminal chekni GoDEX agenti orqali chiqaradi.
LabelImageUser = Annotated[User, Depends(require_roles(UserRole.MANAGER, UserRole.TEXNOLOG))]


@router.get("/labels/{instance_id}.png", operation_id="render_instance_label")
async def render_instance_label(db: SessionDep, _: LabelImageUser, instance_id: int) -> Response:
    """Yorliqning PNG ko'rinishi (ofis uchun) — brauzerdan istalgan printerga chop etish (GoDEX shart emas)."""
    from app.services.labels import load_label_data, render_label_png

    data = await load_label_data(db, instance_id)
    if data is None:
        raise NotFoundException("Nusxa topilmadi.")
    return Response(content=render_label_png(data), media_type="image/png")


@router.get("/files/{file_id}", operation_id="download_terminal_file")
async def download_terminal_file(db: SessionDep, user: TerminalUser, file_id: int) -> FileResponse:
    """SCX download at the machine browser — served fresh on every scan."""
    row = (
        await db.execute(
            select(OrderFile).where(
                OrderFile.id == file_id,
                OrderFile.kind == FileKind.SCX,  # faqat SCX: boshqa turdagi fayllar ofis endpointidan, order-scoped
                OrderFile.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundException("Fayl topilmadi.")
    full_path = upload_root() / row.path
    if not full_path.is_file():
        raise NotFoundException("Fayl diskda topilmadi.")
    return FileResponse(full_path, filename=row.filename, media_type="application/xml")
