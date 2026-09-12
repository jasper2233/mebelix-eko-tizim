"""Scan engine: instance-level pipeline control.

Every physical copy has a unique QR, so validation is exact: a copy can be
scanned at post N only the allowed number of times (per_instance), and — in strict
mode — only after THE SAME copy finished post N−1. Other copies never interfere.
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import TASHKENT_TZ, settings
from app.core.ws import ws_manager
from app.crud import log_action
from app.models import Employee, Machine, Order, Part, PartInstance, PartRoute, Post, Scan, WorkSession
from app.models.enums import (
    POST_ROLES,
    EmployeeStatus,
    MachineStatus,
    OrderStatus,
    PachkaStatus,
    PostCode,
    SessionStatus,
    UserRole,
)
from app.models.user import User
from app.schemas.terminal import ScanResult
from app.services.giblab.models import strip_order_prefix

#: Manbalar-aro dedup oynasi (pastdagi `record_scan_at` izohiga qarang)
CROSS_SOURCE_WINDOW = timedelta(seconds=3)

_QR_RE = re.compile(r"^.+_.+$")  # {productCode}_{partCode}[_{n}] — yagona nusxada suffiks yo'q


def _utc(dt: datetime) -> datetime:
    """Naive `created_at` (SQLite/dev) ni UTC deb belgilaydi — solishtirish yiqilmasin."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def qr_part_code(qr: str, count: int) -> str:
    """Nusxa QR'idan detal kodi (`productCode_partCode`): buyurtma prefiksi va `_n` olib tashlanadi."""
    qr = strip_order_prefix(qr)
    return qr if count == 1 else qr.rsplit("_", 1)[0]


class ScanRejected(Exception):
    """Skan xatosi: kod + o'zbekcha xabar (dialogi, 422 detail).

    KOD KIM HARAKAT QILISHINI aytadi — matn beqaror (tahrirlanadi), kod barqaror:
    frontend ovozni, hisobot esa guruhlashni shunga qarab tanlaydi.

      E001 detal/plan mos kelmadi — operator chekni tekshiradi
      E002 QR formati buzuq — chek qayta chop etiladi
      E003 buyurtma bekor qilingan — manager
      E004 navbat buzildi — oldingi bosqichni kutish kerak
      E005 aktiv smena yo'q — beyjik
      E006 beyjik muammosi — admin/hodim
      E008 ish allaqachon bajarilgan — xato emas, ogohlantirish
      E009 SOZLAMA xatosi (post/ish markazi yo'q) — admin tuzatadi, operator emas

    E007 server kodi emas: aloqa uzilganda terminal frontendi o'zi hosil qiladi.

    Frontend `lib/mes.ts` `SCAN_ERROR_LABELS` shu ro'yxatni QO'LDA oynalaydi (Loglar
    paneli kod yonida izoh ko'rsatadi) — kod qo'shilsa/ma'nosi o'zgarsa ikkalasini yangila.
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def scan_error(code: str, message: str) -> HTTPException:
    """xato dialogi shakli: {code, message} — ScanRejected bilan bir xil JSON payload.

    Skan xatosini HTTP ga o'girishning YAGONA joyi: route'lar `raise
    scan_error(exc.code, exc.message) from None` deb yozadi.
    """
    return HTTPException(status_code=422, detail={"code": code, "message": message})


@dataclass
class ScanOutcome:
    scan: Scan
    part: Part
    instance: PartInstance
    qoldiq: int
    duplicate: bool = False
    #: Chek chiqarishdan tug'ilgan avto-skan (finalize_scan(auto=True) qo'yadi) —
    #: WS payload'iga chiqadi, terminal muvaffaqiyat bannerini bosishda ishlatadi
    auto: bool = False
    order_stage_completed: bool = False
    order_completed: bool = False
    events: list[dict[str, Any]] = field(default_factory=list)


#: Avtomatik tanlashda AKTIV birinchi, TA'MIRDA oxirgi. NOAKTIV umuman tanlanmaydi
#: (`post_machine` filtri) — admin uni ataylab o'chirgan.
_STATUS_PREFERENCE = case((Machine.status == MachineStatus.ACTIVE, 0), else_=1)

MACHINE_MISSING = "postida ishga yaroqli ish markazi yo'q — admin qo'shishi yoki NOAKTIV holatidan chiqarishi kerak."


async def post_machine(db: AsyncSession, post: Post) -> Machine | None:
    """Postning ishga yaroqli ish markazi. Login ham, terminal ham SHU qoidadan o'tadi.

    NOAKTIV tanlanmaydi: admin ish markazini ataylab o'chirgan, ish u yerga
    yo'naltirilmasligi kerak. TA'MIRDA esa oxirgi navbatda turadi, lekin
    TANLANADI — buzilgan stanokda ham qo'lda ishlash davom etadi va admin
    belgini qaytarishni unutsa tsex to'xtab qolmasligi kerak.
    """
    return (
        await db.execute(
            select(Machine)
            .where(
                Machine.post_id == post.id,
                Machine.is_deleted == False,  # noqa: E712
                Machine.status != MachineStatus.INACTIVE,
            )
            .order_by(_STATUS_PREFERENCE, Machine.id)
            .limit(1)
        )
    ).scalar_one_or_none()


async def resolve_terminal(db: AsyncSession, user: User) -> tuple[Machine, Post]:
    post_code = POST_ROLES.get(UserRole(user.role))
    if post_code is not None:
        # Operator role (arrachi, kromkachi, ...): post comes from the role itself.
        post = (
            await db.execute(select(Post).where(Post.code == post_code, Post.is_deleted == False))  # noqa: E712
        ).scalar_one_or_none()
        if post is None:
            raise ScanRejected("E009", f"{post_code} posti topilmadi. Admin postlarni sozlashi kerak.")
        machine = None
        if user.machine_id is not None:
            machine = await db.get(Machine, user.machine_id)
            if machine is not None and (machine.is_deleted or machine.status == MachineStatus.INACTIVE):
                machine = None  # biriktirilgani ishlamaydi — postdan boshqasini olamiz
        if machine is None:
            machine = await post_machine(db, post)
        if machine is None:
            raise ScanRejected("E009", f"{post.name} {MACHINE_MISSING}")
        return machine, post

    # Qurilma hisobi emasmi — sabab BOSHQA: ofis hisobiga ish markazi umuman
    # biriktirilmaydi (`users._check_machine`), ya'ni "biriktirilmagan" deyish
    # sozlama buzuqdek ko'rsatardi. Admin va superuser ham shu yerga tushadi:
    # `require_roles` ularni hamma joyga o'tkazadi, lekin terminal huquq
    # darajasi emas — u qurilma ekrani.
    if UserRole(user.role) not in (UserRole.TERMINAL, UserRole.TABLO):
        raise ScanRejected("E009", "Bu ekran monoblok uchun. Tsex hisobi yoki beyjik bilan kiring.")
    if user.machine_id is None:
        raise ScanRejected("E009", "Terminal foydalanuvchisiga ish markazi biriktirilmagan.")
    machine = await db.get(Machine, user.machine_id)
    if machine is None or machine.is_deleted:
        raise ScanRejected("E009", "Terminal ish markazi topilmadi.")
    if machine.status == MachineStatus.INACTIVE:
        # Qurilma hisobi KONKRET ish markaziga bog'langan: admin uni o'chirgan
        # bo'lsa boshqasiga sakrash ham xato bo'lardi — skan boshqa joyga yozilardi
        raise ScanRejected("E009", f"{machine.name} NOAKTIV holatda — admin uni yoqishi kerak.")
    post = await db.get(Post, machine.post_id)
    if post is None:
        raise ScanRejected("E009", "Ish markazining posti topilmadi.")
    return machine, post


async def badge_employee(db: AsyncSession, badge_id: str, post: Post) -> Employee:
    """Beyjik QR -> hodim. Postga biriktirilmagan hodim shu terminalda ishlay olmaydi."""
    employee = (
        await db.execute(
            select(Employee).where(
                Employee.badge_id == badge_id.strip(),
                Employee.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if employee is None:
        raise ScanRejected("E006", "Beyjik topilmadi.")
    if employee.status != EmployeeStatus.ACTIVE:
        raise ScanRejected("E006", "Beyjik nofaol. Adminga murojaat qiling.")
    if post.id not in employee.assigned_post_ids:
        raise ScanRejected("E006", f"{employee.full_name} bu postda ishlay olmaydi ({post.name}).")
    return employee


async def open_badge_session(
    db: AsyncSession, *, user: User, machine: Machine, post: Post, employee: Employee, join: bool = False
) -> WorkSession:
    """Smenani ochadi — beyjik skani ham, ismni bosish ham shu yerga keladi.

    `join=False` (sukut) BRIGADANI ALMASHTIRADI: ish markazidagi ochiq smenalar yopiladi.
    Bu ataylab sukut: ketayotgan odam "chiqish" ni bosishni unutsa, keyingi kirish
    eski smenani yopib qo'yadi — ya'ni unutish xavfsiz tomonga og'adi. Qo'shilish
    esa `join=True` bilan ATAYLAB so'raladi ("+ Qo'shish"), aks holda ikkalasiga
    ham jimgina ish yozilib ketardi.

    Bir odamni ikki marta qo'shib bo'lmaydi: mavjud smenasi qaytariladi.
    """
    crew = await crew_sessions(db, machine.id)
    mine = next((s for s in crew if s.employee_id == employee.id), None)
    if mine is not None:
        return mine
    if not join:
        now = datetime.now(UTC)
        for previous in crew:
            previous.status = SessionStatus.ENDED
            previous.ended_at = now
    session = WorkSession(employee_id=employee.id, user_id=user.id, machine_id=machine.id, post_id=post.id)
    db.add(session)
    await db.flush()
    return session


async def end_session(db: AsyncSession, session: WorkSession) -> None:
    session.status = SessionStatus.ENDED
    session.ended_at = datetime.now(UTC)
    await db.flush()


async def end_employee_sessions(db: AsyncSession, employee_id: int) -> int:
    """Hodimning HAMMA ochiq smenasini yopadi. Nechtasi yopilgani qaytadi.

    Hodimni nofaol qilish yoki o'chirish shuni chaqirishi SHART, aks holda ochiq
    smena ish markazida qolib ketadi: `active_session` brigadaning LANGAR smenasi
    egasini tekshiradi va nofaol hodim langar bo'lsa o'sha ish markazidagi HAR
    skan E006 "Hodim nofaol" bilan rad etiladi — brigadaning qolgan a'zolari
    aybsiz bo'lsa ham post to'liq to'xtaydi.

    `commit` chaqiruvchida — hodim yozuvi bilan bitta tranzaksiyada ketsin.
    """
    open_sessions = (
        (
            await db.execute(
                select(WorkSession).where(
                    WorkSession.employee_id == employee_id,
                    WorkSession.status == SessionStatus.ACTIVE,
                    WorkSession.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    for session in open_sessions:
        session.status = SessionStatus.ENDED
        session.ended_at = now
    return len(open_sessions)


async def crew_sessions(db: AsyncSession, machine_id: int) -> list[WorkSession]:
    """Ish markazidagi OCHIQ smenalar — brigada, ochilish tartibida.

    "Bitta ish markazi = bitta smena" farazi noto'g'ri edi: ARRA da ikki kishi birga
    ishlaydi (biri varaqni beradi, ikkinchisi detalni oladi va taxlaydi) va detalni
    qaysi biri olganini bilishning ILOJI YO'Q — ish qo'shma. Ilgari ikkinchi kirish
    birinchisining smenasini jimgina yopardi, ya'ni undan keyingi hamma skan bitta
    odamga yozilardi.

    Smena MUDDATI YO'Q va bu yerda hech narsa yopilmaydi — faqat ACTIVE qatorlar
    o'qiladi. Smena «Chiqish», logout yoki shu ish markazidagi keyingi kirish bilan
    yopiladi (`active_session` bilan bir xil qoida; 12 soatlik avto-yopish 85d5833
    da olib tashlangan, docs/04).
    """
    rows = list(
        (
            await db.execute(
                select(WorkSession)
                .where(
                    WorkSession.machine_id == machine_id,
                    WorkSession.status == SessionStatus.ACTIVE,
                    WorkSession.is_deleted == False,  # noqa: E712
                )
                .order_by(WorkSession.id)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def active_session(db: AsyncSession, machine: Machine) -> WorkSession:
    """Skan qaysi smenaga yoziladi — brigadaning BIRINCHI (smenani ochgan) a'zosi.

    Skan qatorida bitta `employee_id` bor — langar smena egasi; hisobot ham skanni
    unga to'liq yozadi (smena vaqti bo'yicha bo'lish yo'q — 2026-09-03 qarori).
    Smena muddati YO'Q: u faqat «Chiqish», logout yoki keyingi kirish bilan yopiladi.

    Smena YAGONA yo'l bilan ochiladi — terminalda beyjik skani yoki ismni bosish
    (`open_badge_session`). Ilgari post rollari uchun "login = smena" shoxi bor
    edi: u hisobga soxta hodim yozuvi yaratib ("arrachi", "omborchi") smenani o'sha
    nomdan ochardi va olib tashlandi (`c7e2b4f81d39`).
    """
    crew = await crew_sessions(db, machine.id)
    if not crew:
        raise ScanRejected("E005", "Aktiv smena yo'q. Terminalda ismingizni bosing yoki beyjikni skanerlang.")
    session = crew[0]
    employee = await db.get(Employee, session.employee_id)
    if employee is None or employee.status != EmployeeStatus.ACTIVE:
        raise ScanRejected("E006", "Hodim nofaol. Adminga murojaat qiling.")
    return session


async def instance_stages(
    db: AsyncSession, order: Order, post: Post, by_part: dict[int, list[PartRoute]] | None = None
) -> dict[int, tuple[bool, str]]:
    """Har NUSXA uchun: `(shu postga tayyormi, OXIRGI bajarilgan bosqich nomi)`.

    Bosqich nomi — ishi TUGAGAN post, kutilayotgani emas: detal jismonan o'sha
    postdan keyin turadi, omborchi uni aynan o'sha yerdan topib oladi. Hali
    hech qanday qadami bajarilmagan nusxada bo'sh satr qaytadi.

    Hisob NUSXA bo'yicha, detal bo'yicha emas: 4 nusxali detalning bittasi
    qadoqlansa, detal jami hali tugamagan bo'ladi — lekin o'sha bitta nusxa
    TMO ga tayyor. Detal darajasida sanaganda u tsexda qolib ketardi va
    omborchi qadoqlangan buyumni ro'yxatdan topa olmasdi.

    `by_part` — chaqiruvchi marshrutni ALLAQACHON o'qigan bo'lsa (TMO sahifasi
    uni `packaging` va TMO qadami uchun o'qiydi) o'sha lug'at uzatiladi, aks
    holda aynan o'sha so'rov har sahifa so'rovida ikki marta ketardi.
    """
    if by_part is None:
        by_part = {}
        for r in (
            await db.execute(
                select(PartRoute).where(
                    PartRoute.order_id == order.id,
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                )
            )
        ).scalars():
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

    stages: dict[int, tuple[bool, str]] = {}
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
        before = [s for s in steps if s.seq < target.seq]
        done = [s for s in before if counts.get((instance_id, s.id), 0) >= s.per_instance]
        ready = len(done) == len(before)
        last = post_names.get(done[-1].post_id, "") if done else ""
        stages[instance_id] = (ready, last)
    return stages


async def _scans_done_map(db: AsyncSession, instance_id: int) -> dict[int, int]:
    """Shu nusxaning HAR qadamdagi skan soni — bitta so'rovda.

    Kalit `route_id` — post emas: bitta post marshrutda ikki marta bo'lsa
    (kromka -> prisadka -> kromka) qadamlar hisobi aralashib ketardi.

    `record_scan_at` ilgari har qadam uchun alohida COUNT yuborardi, qat'iy
    tartib tekshiruvi esa oldingi qadamlarni ham birma-bir so'rardi — ya'ni
    bitta skanga o'nlab round-trip. Qadoq QR'i skanerlanganda (TMO qabuli)
    bu sikl ichida takrorlanib, 40 detalli qadoqda yuzlab so'rov berardi.
    """
    rows = await db.execute(
        select(Scan.route_id, func.count(Scan.id))
        .where(
            Scan.instance_id == instance_id,
            Scan.is_cancelled == False,  # noqa: E712
            Scan.is_deleted == False,  # noqa: E712
        )
        .group_by(Scan.route_id)
    )
    return dict(rows.all())  # type: ignore[arg-type]


async def _close_assembly_children(
    db: AsyncSession,
    *,
    scan: Scan,
    part: Part,
    post: Post,
    route: PartRoute,
    session: WorkSession,
    machine: Machine,
) -> None:
    """Asosiy detal skani unga biriktirilgan MAYDA detallarni ham yopadi.

    Mayda detal marshruti aynan birikish qadamida tugaydi (`orders._set_custom_route`
    unga qadoqlash/TMO dumini qo'shmaydi), shuning uchun birikish nuqtasi — mayda
    detalning OXIRGI qadami. U shu postda bo'lsa, bu skan o'sha qadamni yopadi.

    Chala detaldan yaxlit buyum yig'ib bo'lmaydi: mayda detalning oldingi bosqichi
    tugamagan bo'lsa butun skan rad etiladi (E004), ya'ni asosiy detal ham o'tmaydi.
    """
    children = (
        (
            await db.execute(
                select(Part).where(
                    Part.assembly_parent_id == part.id,
                    Part.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    if not children:
        return
    # Asosiy detalning shu qadamdagi OXIRGI nusxasi qolgan maydalarning hammasini
    # yopadi: sonlar bo'linmasa (5 mayda / 2 asosiy) qoldiq osilib qolmasin.
    last_parent_scan = route.total_done >= route.total_required

    for child in children:
        steps = list(
            (
                await db.execute(
                    select(PartRoute)
                    .where(
                        PartRoute.part_id == child.id,
                        PartRoute.is_enabled == True,  # noqa: E712
                        PartRoute.is_deleted == False,  # noqa: E712
                    )
                    .order_by(PartRoute.seq)
                )
            )
            .scalars()
            .all()
        )
        if not steps or steps[-1].post_id != post.id:
            continue  # birikish boshqa postda (yoki marshrut chizilmagan)
        merge = steps[-1]

        # Har nusxa uchun BITTA hisob so'rovi: birikish qadami ham, undan oldingi
        # qadamlar tekshiruvi ham shu xaritadan o'qiydi.
        open_instances = []
        for inst in (
            (
                await db.execute(
                    select(PartInstance)
                    .where(
                        PartInstance.part_id == child.id,
                        PartInstance.is_deleted == False,  # noqa: E712
                    )
                    .order_by(PartInstance.instance_no)
                )
            )
            .scalars()
            .all()
        ):
            done = await _scans_done_map(db, inst.id)
            if done.get(merge.id, 0) < merge.per_instance:
                open_instances.append((inst, done))
        if not open_instances:
            continue

        per_parent = max(1, child.count // part.count) if part.count else len(open_instances)
        take = open_instances if last_parent_scan else open_instances[:per_parent]

        for inst, done in take:
            for prev in steps[:-1]:
                if done.get(prev.id, 0) < prev.per_instance:
                    prev_post = await db.get(Post, prev.post_id)
                    nom = prev_post.name if prev_post is not None else f"{prev.seq}-qadam"
                    raise ScanRejected(
                        "E004",
                        f"Mayda detal {inst.qr_text} hali {nom} bosqichidan o'tmagan — yig'ib bo'lmaydi.",
                    )
            db.add(
                Scan(
                    order_id=child.order_id,
                    part_id=child.id,
                    instance_id=inst.id,
                    route_id=merge.id,
                    post_id=post.id,
                    machine_id=machine.id,
                    employee_id=session.employee_id,
                    session_id=session.id,
                    client_event_id=f"asm-{scan.id}-{inst.id}",
                    parent_scan_id=scan.id,
                )
            )
            await db.execute(
                update(PartRoute).where(PartRoute.id == merge.id).values(total_done=PartRoute.total_done + 1)
            )
    await db.flush()


async def record_scan(
    db: AsyncSession,
    *,
    user: User,
    qr_text: str,
    client_event_id: str,
) -> ScanOutcome:
    """Validate and register one work unit. Caller commits and publishes outcome.events."""
    machine, post = await resolve_terminal(db, user)
    # QADOQLASH posti umumiy yo'ldan skan olmaydi: qadoqsiz UPAKOVKA skani qadamni
    # yopadi-yu, detal hech bir qadoqda bo'lmaydi — keyin uni qadoqqa skanerlab ham
    # bo'lmaydi (E008). 2026-09-04 da proyekt tanlanmagan terminalda bajarilib
    # tasdiqlangan. Qadoq skani faqat `pachka.scan_into_pachka` orqali.
    if post.code == PostCode.UPAKOVKA:
        raise ScanRejected("E001", "Qadoqlash skani faqat qadoq ichiga tushadi — buyurtmani tanlab, qadoq yarating.")
    session = await active_session(db, machine)
    return await record_scan_at(
        db, machine=machine, post=post, session=session, qr_text=qr_text, client_event_id=client_event_id
    )


async def record_scan_at(
    db: AsyncSession,
    *,
    machine: Machine,
    post: Post,
    session: WorkSession,
    qr_text: str,
    client_event_id: str,
) -> ScanOutcome:
    """Core yozuv — kontekst tayyor bo'lganda. Terminal (user orqali) ham,
    bridge-agent skan-forvardi (stanok bog'lami orqali) ham shu yo'ldan o'tadi."""
    qr = qr_text.strip()
    if not _QR_RE.match(qr):
        raise ScanRejected("E002", "QR kodi noto'g'ri formatda. Chekni qaytadan chop eting.")

    # Idempotent replay (tarmoq qayta urinishi): bir xil `client_event_id` → bir xil
    # muvaffaqiyat, qayta sanamasdan.
    #
    # BEKOR QILINGAN skan bu tekshiruvga KIRMAYDI. Kalit doimiy bo'lgan yagona
    # yo'lda (`pachka`: `pack-{qadoq}-{nusxa}`) bekor qilingan qator o'z kaliti
    # bilan bazada qolardi: qadoqdan chiqarilgan nusxa O'SHA qadoqqa qayta
    # skanerlanganda mana shu qator topilib `duplicate` qaytardi — yangi skan
    # yozilmas, `total_done` kamaygan holicha qolar, UPAKOVKA qadami esa hech
    # qachon yopilmasdi. Bekor qilingan ish "bajarilgan" emas, ya'ni takrorni
    # to'sishi ham mantiqsiz.
    existing = (
        await db.execute(
            select(Scan).where(
                Scan.client_event_id == client_event_id,
                Scan.is_cancelled == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        part = await db.get(Part, existing.part_id)
        instance = await db.get(PartInstance, existing.instance_id)
        route = await db.get(PartRoute, existing.route_id)
        assert part is not None and instance is not None and route is not None
        return ScanOutcome(
            scan=existing,
            part=part,
            instance=instance,
            qoldiq=route.total_required - route.total_done,
            duplicate=True,
        )

    # Locate the copy among live orders — AYNAN moslik. 2026-08-02 gacha yagona nusxa
    # ham `_1` bilan chop etilgan va shu uchun `qr[:-2]` fallback bor edi; 2026-09-04
    # prod nusxasida bunday jonli nusxa 0 ta — olib tashlandi (u haqiqiy `_1` nusxani
    # boshqa detalga moslashtirib yuborishi ham mumkin edi).
    rows = list(
        (
            await db.execute(
                select(PartInstance, Order)
                .join(Order, Order.id == PartInstance.order_id)
                .where(
                    PartInstance.qr_text == qr,
                    PartInstance.is_deleted == False,  # noqa: E712
                    Order.is_deleted == False,  # noqa: E712
                    Order.status.in_([OrderStatus.PRODUCTION, OrderStatus.CANCELLED]),
                )
            )
        ).all()
    )
    if not rows:
        raise ScanRejected("E001", "Bu chek hech bir buyurtmada topilmadi — chekni tekshiring.")
    # QR buyurtmaga bog'lanmagan (docs/11): ikki jonli buyurtma bitta QR ni ulashishi mumkin — jimgina
    # eng yangisiga yozish o'rniga rad etamiz. CANCELLED faqat E003 xabari uchun, to'qnashuv emas.
    live = [r for r in rows if r[1].status == OrderStatus.PRODUCTION]
    if len(live) > 1:
        raise ScanRejected("E001", "Bu QR bir nechta buyurtmada uchradi — menejerga murojaat qiling.")
    instance, order = live[0] if live else rows[0]
    if order.status == OrderStatus.CANCELLED:
        raise ScanRejected("E003", "Buyurtma bekor qilingan. Menejerga murojaat qiling.")

    part = await db.get(Part, instance.part_id)
    assert part is not None

    # Shu postdagi qadamlar navbat bo'yicha: birinchi TUGALLANMAGANI shu skanniki.
    # Post marshrutda takrorlanishi mumkin, shuning uchun bitta qator kutilmaydi.
    steps = (
        (
            await db.execute(
                select(PartRoute)
                .where(
                    PartRoute.part_id == part.id,
                    PartRoute.post_id == post.id,
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                )
                .order_by(PartRoute.seq)
            )
        )
        .scalars()
        .all()
    )
    if not steps:
        raise ScanRejected("E001", "Bu post bu detal marshrutida yo'q. Chekni tekshiring.")

    # Nusxaning hamma qadam hisobi bitta so'rovda — pastdagi qat'iy tartib
    # tekshiruvi ham shu xaritadan o'qiydi.
    done = await _scans_done_map(db, instance.id)
    route = None
    for step in steps:
        if done.get(step.id, 0) < step.per_instance:
            route = step
            break
    if route is None:
        # Yalang'och "allaqachon yakunlangan" ishchini adashtirardi: QAYSI postda,
        # NECHTA skan bilan, QACHON? Egizak detallar (05_009 va 05_009-2 kabi bir
        # nomli cheklar) holatida bu javob ishchining o'ziga xatoni ko'rsatadi —
        # "men 2 marta skan qildim" degan taxmin 4/4 va vaqt qarshisida yechiladi.
        jami = sum(st.per_instance for st in steps)
        oxirgi = (
            await db.execute(
                select(func.max(Scan.created_at)).where(
                    Scan.instance_id == instance.id,
                    Scan.route_id.in_([st.id for st in steps]),
                    Scan.is_cancelled == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        vaqt = f", oxirgi skan {oxirgi.astimezone(TASHKENT_TZ):%H:%M}" if oxirgi else ""
        raise ScanRejected(
            "E008",
            f"Bu detal {post.name} postida allaqachon yakunlangan ({jami}/{jami} skan{vaqt}).",
        )
    if route.machine_id is not None and route.machine_id != machine.id:
        raise ScanRejected("E001", "Bu detal boshqa ish markaziga biriktirilgan.")

    # Qat'iy tartib (E004): postlarning global tartibi emas, detalning
    # O'Z marshruti bo'yicha — nostandart marshrut roverdan boshlanishi mumkin.
    if settings.STRICT_STAGE_ORDER:
        pending = (
            await db.execute(
                select(PartRoute)
                .where(
                    PartRoute.part_id == part.id,
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                    PartRoute.seq < route.seq,
                )
                .order_by(PartRoute.seq)
            )
        ).scalars()
        for prev in pending:
            if done.get(prev.id, 0) < prev.per_instance:
                prev_post = await db.get(Post, prev.post_id)
                nom = prev_post.name if prev_post is not None else f"{prev.seq}-qadam"
                raise ScanRejected("E004", f"Avval {nom} — oldingi bosqich hali yakunlanmagan.")

    # MANBALAR-ARO DEDUP. Bitta fizik skan IKKI yo'ldan kelishi mumkin: brauzer
    # terminali (`/scans`, client_event_id = crypto.randomUUID()) va stanok
    # agentining klaviatura kuzatuvchisi (`/bridge-agents/scan`, uuid4().hex).
    # `client_event_id` dedupi bu yerda ishlamaydi — ikki yo'l ikki xil id beradi.
    # `per_instance == 1` qadamda ikkinchisi E008 bilan to'xtaydi, lekin
    # per_instance > 1 (KROMKA qirralari, PRISADKA tomonlari) da u JIMGINA
    # ikkinchi qirrani ham yopib qo'yardi: detal bir tomoni ishlanmasdan
    # "tugagan" bo'lardi. Bir xil (nusxa, qadam) bo'yicha 3 soniya ichidagi
    # ikkinchi yozuv takror deb qabul qilinadi — qirra/tomon ishlovi soniyalarda
    # tugamaydi, ya'ni oyna qonuniy ishni yutib yubormaydi.
    yaqin = (
        (
            await db.execute(
                select(Scan)
                .where(
                    Scan.instance_id == instance.id,
                    Scan.route_id == route.id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                    Scan.created_at > datetime.now(UTC) - CROSS_SOURCE_WINDOW,
                )
                .order_by(Scan.created_at.desc())
            )
        )
        .scalars()
        .first()
    )
    if yaqin is not None:
        return ScanOutcome(
            scan=yaqin,
            part=part,
            instance=instance,
            qoldiq=route.total_required - route.total_done,
            duplicate=True,
        )

    scan = Scan(
        order_id=order.id,
        part_id=part.id,
        instance_id=instance.id,
        route_id=route.id,
        post_id=post.id,
        machine_id=machine.id,
        employee_id=session.employee_id,
        session_id=session.id,
        client_event_id=client_event_id,
    )
    db.add(scan)
    # Flush AYNAN shu yerda: sessiyada `autoflush=True`, ya'ni keyingi har qanday
    # `execute()` kutilayotgan INSERT'ni o'zi yuvadi va `client_event_id` unikal
    # indeksi poygasi guard tashqarisida 500 bo'lib chiqardi.
    try:
        await db.flush()
    except IntegrityError:  # client_event_id race — treat as replay
        await db.rollback()
        raise ScanRejected("E001", "Takroriy skan — qayta urining.") from None

    # Inkrement SQL tomonda: ikki terminal bir vaqtda skanlasa Python tomonda
    # o'qib-yozish (`+= 1`) bittasini yo'qotardi va qadam `total_required` ga
    # hech qachon yetmasdi — buyurtma abadiy "tugamagan" bo'lib qolardi.
    await db.execute(update(PartRoute).where(PartRoute.id == route.id).values(total_done=PartRoute.total_done + 1))
    await db.refresh(route, ["total_done"])

    # Yig'ma buyum: shu qadamda asosiy detalga mayda detallar yopishtiriladi.
    # Ular alohida skanerlanmaydi — asosiy detalning skani ularnikini ham yopadi.
    await _close_assembly_children(db, scan=scan, part=part, post=post, route=route, session=session, machine=machine)

    outcome = ScanOutcome(
        scan=scan,
        part=part,
        instance=instance,
        qoldiq=route.total_required - route.total_done,
    )

    outcome.events.append(
        {
            "type": "scan.recorded",
            "payload": {
                "order_id": order.id,
                "order_number": order.number,
                "part_id": part.id,
                "part_code": qr_part_code(instance.qr_text, part.count),
                # Nusxaning TO'LIQ QR'i: `part_code` ko'p nusxali detalda `_n`
                # siz keladi, terminal esa takroriy xabarni aynan QR bo'yicha
                # ajratadi (bitta fizik skan brauzer va stanok agenti orqali
                # ikki marta kelishi mumkin).
                "qr_text": instance.qr_text,
                "instance_no": instance.instance_no,
                "post_id": post.id,
                "machine_id": machine.id,
                "qoldiq": outcome.qoldiq,
                "pattern_no": instance.pattern_no,
                "cell_index": instance.cell_index,
            },
            "post_id": post.id,
            "machine_id": machine.id,
        }
    )

    # Stage / order completion.
    stage_left = (
        await db.execute(
            select(func.count(PartRoute.id)).where(
                PartRoute.order_id == order.id,
                PartRoute.post_id == post.id,
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
                PartRoute.total_done < PartRoute.total_required,
            )
        )
    ).scalar_one()
    if stage_left == 0:
        outcome.order_stage_completed = True
        outcome.events.append(
            {
                "type": "order.stage_completed",
                "payload": {"order_id": order.id, "order_number": order.number, "post_id": post.id},
            }
        )
        all_left = (
            await db.execute(
                select(func.count(PartRoute.id)).where(
                    PartRoute.order_id == order.id,
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                    PartRoute.total_done < PartRoute.total_required,
                )
            )
        ).scalar_one()
        if all_left == 0:
            order.status = OrderStatus.COMPLETED
            order.completed_at = datetime.now(UTC)
            outcome.order_completed = True
            outcome.events.append(
                {
                    "type": "order.completed",
                    "payload": {"order_id": order.id, "order_number": order.number},
                }
            )
    return outcome


async def publish_scan_events(outcomes: list[ScanOutcome]) -> None:
    """Yig'ilgan skanlarning WS eventlarini tarqatadi — FAQAT commitdan keyin.

    `finalize_scan` bitta skan uchun shuni chaqiradi. TMO qabuli va qadoqqa skan
    esa bir nechta skanni bitta tranzaksiyada yozadi va o'z javobini qaytaradi,
    shuning uchun ular ham aynan shu yerni chaqiradi — aks holda `scan.recorded`,
    `order.stage_completed` va `order.completed` eventlari jimgina yo'qolardi
    (ilgari shunday edi: `ScanOutcome` umuman tashlab yuborilardi).
    """
    for outcome in outcomes:
        for event in outcome.events:
            # `scan_id` payload'ga aynan shu yerda — publish oldidan — qo'yiladi.
            # U brauzerga o'z skanini begonasidan ajratish uchun kerak: stanok
            # skaneridan kelgan skan ham shu event bilan keladi va terminal uni
            # bannerda ko'rsatadi, lekin o'zi qilgan skanni ikki marta
            # ko'rsatmasligi kerak.
            if event["type"] == "scan.recorded":
                event["payload"]["scan_id"] = outcome.scan.id
                # `auto` — skan QO'L skanidan emas, chek chiqarishdan tug'ilgan
                # (ARRA doim, ROVER roverda kesiladigan detalda). Terminal bunga
                # qarab muvaffaqiyat bannerini bosadi: katakning yashil bo'lishi
                # o'zi tasdiq. Post nomi bo'yicha emas — ROVER ham chek chiqaradi,
                # ham qo'lda skan oladi, farq postda emas, skanning kelib
                # chiqishida.
                event["payload"]["auto"] = outcome.auto
            await ws_manager.publish(
                event["type"], event["payload"], post_id=event.get("post_id"), machine_id=event.get("machine_id")
            )


async def finalize_scan(
    db: AsyncSession,
    outcome: ScanOutcome,
    *,
    user_id: int | None = None,
    source: str = "",
    agent_id: int | None = None,
    auto: bool = False,
) -> ScanResult:
    """Muvaffaqiyatli skanning YAKUNI — log + commit + WS publish + ScanResult.
    Terminal (scans.py) va stanok skan-forvardi (bridge_agents.py) aynan shu
    yo'ldan o'tadi: ikki nusxa drift bergani uchun bitta joyga yig'ildi."""
    outcome.auto = auto
    if not outcome.duplicate:
        meta: dict[str, Any] = {"post_id": outcome.scan.post_id, "machine_id": outcome.scan.machine_id}
        if agent_id is not None:
            meta["agent_id"] = agent_id
        log_action(
            db,
            module="scan",
            action="recorded",
            user_id=user_id,
            employee_id=outcome.scan.employee_id,
            entity_type="scan",
            entity_id=outcome.scan.id,
            message=f"Skan{source}: {outcome.instance.qr_text} — {outcome.part.name}",
            meta=meta,
        )
    await db.commit()
    await publish_scan_events([outcome])
    return ScanResult(
        scan_id=outcome.scan.id,
        duplicate=outcome.duplicate,
        qr_text=outcome.instance.qr_text,
        part_code=qr_part_code(outcome.instance.qr_text, outcome.part.count),
        part_name=outcome.part.name,
        instance_no=outcome.instance.instance_no,
        qoldiq=outcome.qoldiq,
        order_stage_completed=outcome.order_stage_completed,
        order_completed=outcome.order_completed,
    )


async def log_rejected_scan(
    db: AsyncSession,
    exc: ScanRejected,
    qr_text: str,
    *,
    user_id: int | None = None,
    source: str = "",
    meta_extra: dict[str, Any] | None = None,
) -> None:
    """Rad etilgan skan YAKUNI — rollback + audit-log + commit.
    Terminal (scans.py) va stanok skan-forvardi (bridge_agents.py) bir xil blokni
    takrorlardi; HTTPException(422) esa har bir chaqiruv joyining o'zida qoladi."""
    await db.rollback()
    log_action(
        db,
        module="scan",
        action="rejected",
        user_id=user_id,
        message=f"Skan rad etildi{source}: {qr_text} — {exc.message}",
        meta={"code": exc.code, **(meta_extra or {})},
    )
    await db.commit()


async def revoke_scan(db: AsyncSession, scan: Scan, *, at: datetime | None = None) -> PartRoute | None:
    """Bitta skanni QAYTARADI: o'zi, hosilalari, hisoblagichlar va buyurtma holati.

    Skanni bekor qilish UCH joyda bo'ladi — terminaldagi BEKOR QILISH tugmasi
    (`cancel_scan`), chekni bekor qilish (`terminal.cancel_instance_label`) va
    qadoqdan chiqarish (`pachka.remove_from_pachka`). Ilgari uchalasi alohida
    yozilgan edi va ikkitasida ikki qadam YETISHMASDI:

      * hosila skanlar (`parent_scan_id`) qaytmasdi — yig'ma buyumda asosiy detal
        ochilib, unga yopishtirilgan maydalari yopiq qolib ketardi;
      * COMPLETED buyurtma PRODUCTION ga qaytmasdi — marshrutda ochiq qadam
        paydo bo'lsa ham buyurtma "tayyor" bo'lib turaverardi, ya'ni TABLO ham,
        hisobot ham yolg'on ko'rsatardi.

    Qaytaradi: skanning O'Z marshrut qadami (hisoblagichi yangilangan holda),
    chaqiruvchi undan `qoldiq` ni hisoblaydi.
    """
    now = at or datetime.now(UTC)
    scan.is_cancelled = True
    scan.cancelled_at = now
    # Idempotentlik kaliti BO'SHATILADI. U doim yagona (`ix_scan_client_event_id`)
    # va faqat TIRIK skan uchun ma'noga ega. Doimiy kalitli yagona yo'lda
    # (`pachka`: `pack-{qadoq}-{nusxa}`) bekor qilingan qator kalitni band qilib
    # turardi: qadoqdan chiqarilgan nusxani O'SHA qadoqqa qayta skanerlaganda
    # yo takror deb rad etilar, yo unique indeksga urilardi — ikkala holda ham
    # UPAKOVKA qadami yopilmay qolardi.
    scan.client_event_id = None

    derived = (
        (
            await db.execute(
                select(Scan).where(
                    Scan.parent_scan_id == scan.id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    for child_scan in derived:
        child_scan.is_cancelled = True
        child_scan.cancelled_at = now
        await db.execute(
            update(PartRoute)
            .where(PartRoute.id == child_scan.route_id, PartRoute.total_done > 0)
            .values(total_done=PartRoute.total_done - 1)
        )

    route = await db.get(PartRoute, scan.route_id)
    if route is not None:
        # Kamaytirish ham SQL tomonda — parallel skan/bekor qilishda drift bo'lmasin
        await db.execute(
            update(PartRoute)
            .where(PartRoute.id == route.id, PartRoute.total_done > 0)
            .values(total_done=PartRoute.total_done - 1)
        )
        await db.refresh(route, ["total_done"])

    order = await db.get(Order, scan.order_id)
    if order is not None and order.status == OrderStatus.COMPLETED:
        order.status = OrderStatus.PRODUCTION
        order.completed_at = None
    return route


async def cancel_scan(db: AsyncSession, *, user: User, scan_id: int) -> tuple[Scan, list[dict[str, Any]]]:
    """BEKOR QILISH: only the last N seconds, same terminal session."""
    machine, _ = await resolve_terminal(db, user)
    session = await active_session(db, machine)

    scan = await db.get(Scan, scan_id)
    if scan is None or scan.is_deleted or scan.session_id != session.id:
        raise ScanRejected("E001", "Skan topilmadi yoki boshqa smenada yozilgan — bekor qilib bo'lmaydi.")
    if scan.is_cancelled:
        raise ScanRejected("E001", "Bu skan allaqachon bekor qilingan.")
    if datetime.now(UTC) - _utc(scan.created_at) > timedelta(seconds=settings.SCAN_UNDO_SECONDS):
        raise ScanRejected("E001", f"{settings.SCAN_UNDO_SECONDS} sekunddan ko'p o'tdi — faqat admin bekor qila oladi.")

    # Qadoq skani (`pack-{qadoq}-{nusxa}`): detal qadoq ICHIDA turadi. Faqat skanni
    # qaytarish detalni «qadoqda, lekin qadami ochiq» holatga tashlardi — qadoqlovchi
    # uni qayta skanerlay olmaydi (allaqachon ichida), omborchi qabul qila olmaydi
    # (E004): 2026-09-04 da lokalda BEKOR QILISH bilan bajarilib tasdiqlangan.
    # Ochiq qadoqdan chiqariladi (`pachka.remove_from_pachka` bilan bir), yopiq
    # qadoqda rad etiladi — avval «Qayta ochish».
    if (scan.client_event_id or "").startswith("pack-"):
        from app.models.pachka import Pachka, PachkaItem

        row = (
            await db.execute(
                select(PachkaItem, Pachka.status, Pachka.code)
                .join(Pachka, Pachka.id == PachkaItem.pachka_id)
                .where(
                    PachkaItem.instance_id == scan.instance_id,
                    PachkaItem.is_deleted == False,  # noqa: E712
                )
            )
        ).first()
        if row is not None:
            item, status, code = row
            if status != PachkaStatus.OPEN:
                raise ScanRejected("E001", f"Detal yopiq qadoqda ({code}) — avval qadoqni qayta oching.")
            item.is_deleted = True
            item.deleted_at = datetime.now(UTC)

    route = await revoke_scan(db, scan)
    events: list[dict[str, Any]] = [
        {
            "type": "scan.cancelled",
            "payload": {
                "scan_id": scan.id,
                "order_id": scan.order_id,
                "part_id": scan.part_id,
                "post_id": scan.post_id,
                "qoldiq": (route.total_required - route.total_done) if route else None,
            },
            "post_id": scan.post_id,
            "machine_id": scan.machine_id,
        }
    ]
    return scan, events
