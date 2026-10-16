"""Reports: productivity, machine time (OEE), order status, material consumption.

These four return JSON by default; `?format=xlsx` streams an Excel file. Access:
manager/director (admin and superuser always). `/dashboard` is JSON only and is also
open to texnolog — its money block stays management-only.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import ColumnElement, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, defer

from app.api.deps import SessionDep, require_roles
from app.core.config import TASHKENT_TZ
from app.models import (
    ORDER_FAT_COLUMNS,
    AndonEvent,
    Client,
    Downtime,
    DowntimeReason,
    Employee,
    Machine,
    Order,
    Part,
    PartDefect,
    PartRoute,
    Post,
    Scan,
    WorkSession,
)
from app.models.enums import (
    POST_UNIT_LABELS,
    DefectStatus,
    DowntimeKind,
    MachineStatus,
    OrderStatus,
    PostCode,
    PostUnit,
    SessionStatus,
    UserRole,
)
from app.models.user import User
from app.schemas.reports import (
    AvailabilityReason,
    DashboardMoney,
    DashboardOrders,
    DashboardStats,
    DashboardToday,
    EmployeeProductivity,
    MachineTimeDay,
    MachineTimeReport,
    MachineTimeRow,
    MaterialsReport,
    MaterialUsageRow,
    OrderReportRow,
    OrdersReport,
    PostLoad,
    ProductivityReport,
    ReadyOrder,
    TrendDay,
)
from app.schemas.settings import IdealCycleRover
from app.services.andon import (
    ANDON_STATES,
    AndonSpan,
    andon_spans,
    cut_spans,
    kromka_power_gaps,
    machine_time,
    read_live,
    rover_spans,
    split_idle,
    uskuna_spans,
)
from app.services.availability import Availability, DayTotals, StopRun, availability, inside, plan_windows
from app.services.excel import xlsx_response
from app.services.metrics import VolumeShare, part_volume
from app.services.performance import (
    ideal_seconds,
    kromka_ideal_seconds,
    oee_pct,
    quality_pct,
    rover_ideal_seconds,
)
from app.services.settings_service import (
    KROMKA_IDLE_MINUTES,
    STOP_PROMPT_IDLE_MINUTES,
    get_ideal_cycle,
    get_ideal_cycle_kromka,
    get_ideal_cycle_rover,
    get_oee_start,
    get_setting,
    get_work_schedule,
)

router = APIRouter(prefix="/reports", tags=["reports"])

ReportsUser = Annotated[User, Depends(require_roles(UserRole.MANAGER, UserRole.DIRECTOR))]
# Boshqaruv paneli texnologga ham ochiq (ishlab chiqarish manzarasi uning ham ishi);
# pul bloki esa faqat boshqaruvga — `report_dashboard` ichida ajratiladi.
DashboardUser = Annotated[User, Depends(require_roles(UserRole.MANAGER, UserRole.DIRECTOR, UserRole.TEXNOLOG))]

# `material_usage[].kind` uch qiymatli (giblab/models.py: "sheet" | "band" | "hardware").
_KIND_LABELS = {"sheet": "List", "band": "Kromka", "hardware": "Furnitura"}


def _range(date_from: date | None, date_to: date | None) -> tuple[datetime, datetime]:
    """Default: last 30 days. Bounds are inclusive local (Asia/Tashkent) days."""
    end_day = date_to or datetime.now(TASHKENT_TZ).date()
    # 29, 30 emas: chegaralar inklyuziv, ya'ni end_day - 29 … end_day = aynan 30 kalendar kun.
    start_day = date_from or (end_day - timedelta(days=29))
    start = datetime.combine(start_day, time.min, tzinfo=TASHKENT_TZ)
    end = datetime.combine(end_day, time.max, tzinfo=TASHKENT_TZ)
    return start, end


# ---------- 11.1.1 Hodim mahsuldorligi ----------


@router.get("/productivity", operation_id="report_productivity", response_model=ProductivityReport)
async def report_productivity(
    db: SessionDep,
    _: ReportsUser,
    date_from: date | None = None,
    date_to: date | None = None,
    format: Annotated[Literal["json", "xlsx"], Query()] = "json",
) -> ProductivityReport | StreamingResponse:
    start, end = _range(date_from, date_to)

    # Skan uni urgan hodimga (langar smena egasi, `scan.employee_id`) TO'LIQ yoziladi —
    # smena vaqt oynasi bo'yicha brigada orasida bo'lish olib tashlangan (2026-09-03).
    day = func.date_trunc("day", func.timezone(TASHKENT_TZ.key, Scan.created_at))
    hour = func.date_trunc("hour", func.timezone(TASHKENT_TZ.key, Scan.created_at))
    total_scans = func.count(Scan.id)
    rows = (
        await db.execute(
            select(
                Employee.id,
                Employee.full_name,
                Employee.position,
                total_scans,
                func.count(func.distinct(day)),
                func.count(func.distinct(hour)),
            )
            .join(Scan, Scan.employee_id == Employee.id)
            .where(
                Scan.created_at.between(start, end),
                Scan.is_cancelled == False,  # noqa: E712
                Scan.is_deleted == False,  # noqa: E712
            )
            .group_by(Employee.id, Employee.full_name, Employee.position)
            .order_by(total_scans.desc())
        )
    ).all()

    employees = [
        EmployeeProductivity(
            employee_id=eid,
            full_name=name,
            position=position,
            total_scans=int(total),
            active_days=days,
            per_day=round(float(total) / days, 1) if days else 0.0,
            per_hour=round(float(total) / hours, 1) if hours else 0.0,
        )
        for eid, name, position, total, days, hours in rows
    ]
    report = ProductivityReport(date_from=start.date(), date_to=end.date(), employees=employees)
    if format == "xlsx":
        return xlsx_response(
            "Mahsuldorlik",
            ["Hodim", "Lavozim", "Jami scan", "Faol kunlar", "Kuniga o'rtacha", "Soatiga o'rtacha"],
            [[e.full_name, e.position or "", e.total_scans, e.active_days, e.per_day, e.per_hour] for e in employees],
            f"mahsuldorlik_{report.date_from}_{report.date_to}.xlsx",
        )
    return report


# ---------- Stanok vaqti (andon — signal ustuni) ----------

#: Oraliq tugagandan keyin kelgan hodisa ham oraliq ichidagi holatni yopgan bo'lishi
#: mumkin (masalan tungi OFF ertalab tugaydi) — shuncha kun keyingacha hodisa olinadi.
_ANDON_TAIL = timedelta(days=3)


def _reason_lookup(
    rows: Sequence[tuple[int, datetime, datetime | None, int, str, bool]], now: datetime
) -> Callable[[StopRun], tuple[int, str, bool] | None]:
    """To'xtashga sabab: shu ish markazining sababi kiritilgan `downtime` yozuvlaridan ENG KO'P ustma-ust
    tushgani. Kalit bo'yicha emas, vaqt bo'yicha: hisobot oralig'i to'xtash o'rtasidan boshlansa ham topiladi."""

    def find(run: StopRun) -> tuple[int, str, bool] | None:
        best: tuple[float, tuple[int, str, bool]] | None = None
        for _mid, began, ended, reason_id, name, is_planned in rows:
            overlap = (min(run.ended, ended or now) - max(run.began, began)).total_seconds()
            if overlap > 0 and (best is None or overlap > best[0]):
                best = (overlap, (reason_id, name, is_planned))
        return best[1] if best else None

    return find


def _machine_time_xlsx(report: MachineTimeReport) -> StreamingResponse:
    """Excel varianti — ustunlar sahifadagi jadval bilan AYNAN bir xil.
    Ikki joyda ikki xil raqam chiqmasin uchun bitta funksiyada."""
    return xlsx_response(
        "Stanok vaqti",
        [
            "Stanok",
            "Reja vaqti (soat)",
            "To'xtash (soat)",
            "Ishladi (soat)",
            "Availability, %",
            "Detallar",
            "Ideal vaqt (soat)",
            "Performance, %",
            "Brak",
            "Quality, %",
            "OEE, %",
        ],
        [
            [
                r.machine_name,
                round(r.planned_s / 3600, 2),
                round((r.unplanned_stop_s + r.no_data_s) / 3600, 2),
                round(r.run_s / 3600, 2),
                r.availability_pct if r.availability_pct is not None else "",
                r.parts,
                round(r.ideal_s / 3600, 2),
                r.performance_pct if r.performance_pct is not None else "",
                r.defects,
                r.quality_pct if r.quality_pct is not None else "",
                r.oee_pct if r.oee_pct is not None else "",
            ]
            for r in report.rows
        ],
        f"stanok_vaqti_{report.date_from}_{report.date_to}.xlsx",
    )


@router.get("/machine-time", operation_id="report_machine_time", response_model=MachineTimeReport)
async def report_machine_time(
    db: SessionDep,
    _: ReportsUser,
    date_from: date | None = None,
    date_to: date | None = None,
    format: Annotated[Literal["json", "xlsx"], Query()] = "json",
) -> MachineTimeReport | StreamingResponse:
    """Stanok vaqti va OEE Availability: signal ustuni (andon) bo'yicha qancha ishladi, kutdi, to'xtadi.

    Availability = ishlagan / reja vaqti (`services/availability.py`): reja vaqti ish jadvalidan,
    to'xtashlar chiroq holatlaridan, sabab va «rejali» belgisi `downtime` jadvalidan. Ish vaqtidan
    tashqaridagi holat (tungi OFF, tushlik) hisobga kirmaydi; ish vaqtida ma'lumot yo'qligi — to'xtash.

    Davomiyliklarni Pico o'zi o'lchaydi (`prev_duration_s`), hisob `services/andon.py`
    dagi sof funksiyada. Hozir davom etayotgan holat faqat jonli holat (Redis) hali
    tirik bo'lsa hozirgacha qo'shiladi — agent bilan aloqa yo'q bo'lsa noma'lum vaqt
    taxmin qilinmaydi va "jami qayd" dan tushib qoladi.
    """
    report = await build_machine_time_report(db, date_from, date_to)
    return _machine_time_xlsx(report) if format == "xlsx" else report


async def uskuna_machine_spans(
    db: AsyncSession, start: datetime, end: datetime, now: datetime, faqat: ColumnElement[bool]
) -> list[AndonSpan]:
    """KROMKA va ROVER holat oraliqlari (`uskuna` — RUN kirishi; chiroq yo'q, davomiylikni
    hodisalar orasidan quramiz). Oxirgi oraliq faqat agent hozir aloqada bo'lsa ochiq qoladi.

    - ROVER: `andon.rover_spans` — agent hodisalari faqat bitta ulanish ichida davom etadi,
      ulanishlar orasidagi vaqt Pico'ning fleshdagi davrlaridan (POWER_ON, POWER_CYCLE,
      SPINDLE_IDLE ...) va qayta ulanishdagi `on_sec`/`idle_sec` dan tiklanadi.
    - KROMKA: Pico agent uzilsa hodisalarni RAM da saqlaydi — davomiylik to'g'ri; faqat tok
      uzilib qayta yonganda (`andon.kromka_power_gaps`) oxirgi hodisadan yonishgacha noma'lum.
      Lenta yuryapti-yu detal o'tmagan qism — BO'SH YURISH (`split_idle`)."""
    lo, hi = start - _ANDON_TAIL, end + _ANDON_TAIL
    rows = (
        (
            await db.execute(
                select(
                    AndonEvent.machine_id,
                    AndonEvent.kind,
                    AndonEvent.payload,
                    AndonEvent.happened_at,
                    AndonEvent.session,
                )
                .where(
                    AndonEvent.kind.in_(("uskuna", "rover", "boot")),
                    AndonEvent.is_deleted == False,  # noqa: E712
                    # Oraliqdan OLDINGI oxirgi hodisa ham kerak: u oraliq boshidagi
                    # holatni belgilaydi (stanok kecha yoqilgan bo'lsa bugun ham ishlayapti).
                    AndonEvent.happened_at >= lo,
                    AndonEvent.happened_at <= hi,
                    faqat,
                )
                .order_by(AndonEvent.happened_at, AndonEvent.id)
            )
        )
        .tuples()
        .all()
    )
    rover_mids = {mid for mid, kind, p, _at, _s in rows if kind == "rover" or (p or {}).get("manba") == "rover"}
    uskuna = [(mid, p or {}, at, s) for mid, kind, p, at, s in rows if kind == "uskuna"]
    tirik = set(await read_live({mid for mid, *_ in uskuna} | rover_mids)) if uskuna or rover_mids else set()
    spans = rover_spans(
        [u for u in uskuna if u[0] in rover_mids],
        [(mid, p or {}) for mid, kind, p, _at, _s in rows if kind == "rover" and mid in rover_mids],
        tirik & rover_mids,
        now,
    )
    kromka = uskuna_spans([(mid, p, at) for mid, p, at, _s in uskuna if mid not in rover_mids], tirik)
    if not kromka:
        return spans
    kromka_mids = {sp.machine_id for sp in kromka}
    boots = [(mid, p or {}, at) for mid, kind, p, at, _s in rows if kind == "boot" and mid in kromka_mids]
    last_before: dict[tuple[int, datetime], datetime] = {}
    for mid, _p, at in boots:
        oldingi = (
            await db.execute(
                select(func.max(AndonEvent.happened_at)).where(
                    AndonEvent.machine_id == mid,
                    AndonEvent.is_deleted == False,  # noqa: E712
                    AndonEvent.happened_at < at,
                    AndonEvent.happened_at >= at - _ANDON_TAIL,
                )
            )
        ).scalar()
        if oldingi is not None:
            last_before[(mid, at)] = oldingi
    kromka = cut_spans(kromka, kromka_power_gaps(boots, last_before), now)
    # Lenta yuryapti, lekin uzoq vaqt detal o'tmagan qismi — BO'SH YURISH (`IDLE`):
    # u «ishladi» ga kirmasligi kerak (`services/andon.split_idle`). Yo'qotish shu bilan
    # Availability'ga ko'chadi, Performance maxraji (`run_s`) esa qisqaradi — ya'ni
    # bitta yo'qotish ikki marta jazolanmaydi.
    olchov_vaqtlari: dict[int, list[datetime]] = {}
    for olchov_mid, olchov_at in (
        (
            await db.execute(
                select(AndonEvent.machine_id, AndonEvent.happened_at)
                .where(
                    AndonEvent.kind == "olchov",
                    AndonEvent.is_deleted == False,  # noqa: E712
                    AndonEvent.machine_id.in_(kromka_mids),
                    AndonEvent.happened_at >= lo,
                    AndonEvent.happened_at <= hi,
                )
                .order_by(AndonEvent.happened_at)
            )
        )
        .tuples()
        .all()
    ):
        olchov_vaqtlari.setdefault(olchov_mid, []).append(olchov_at)
    kromka_gap = timedelta(minutes=int(await get_setting(db, KROMKA_IDLE_MINUTES)))
    return spans + split_idle(kromka, olchov_vaqtlari, kromka_gap, now)


async def _rover_parts(
    db: AsyncSession,
    rover_ids: set[int],
    avail: dict[int, Availability],
    start: datetime,
    end: datetime,
    cycle: IdealCycleRover,
    ideal_by: dict[tuple[int, date], list[float]],
) -> None:
    """ROVER Performance: birlik — DETAL (2026-10-16 qarori), `ideal_by` ga qo'shadi.

    Manba — shu stanokdagi skanlar: chek chiqarish (`rvprint-*` avto-skani, roverda
    kesiladigan detal) ham, ARRA'dan keyin oddiy skan ham. Ideal vaqt kontur uzunligidan
    (`services/performance.rover_ideal_seconds`). Filtr Prisadkadagi bilan bir xil:
    faqat KUZATILGAN ish vaqtidagi skan, brak tasdig'i bekor qilgani ham sanaladi."""
    rows = (
        (
            await db.execute(
                select(Scan.machine_id, Scan.created_at, Part.length, Part.width)
                .join(Part, Part.id == Scan.part_id)
                .where(
                    Scan.machine_id.in_(rover_ids),
                    or_(Scan.is_cancelled == False, Scan.defect_id.is_not(None)),  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                    Scan.created_at >= start,
                    Scan.created_at <= end,
                )
            )
        )
        .tuples()
        .all()
    )
    for mid, at, length, width in rows:
        if mid is not None and inside(avail[mid].observed, at):
            cell = ideal_by.setdefault((mid, at.astimezone(TASHKENT_TZ).date()), [0.0, 0])
            cell[0] += rover_ideal_seconds(cycle, length, width)
            cell[1] += 1


async def build_machine_time_report(
    db: AsyncSession, date_from: date | None, date_to: date | None, only: frozenset[int] | None = None
) -> MachineTimeReport:
    """«Stanok vaqti» hisobining o'zi — route (JSON/xlsx) va tablo umumiy, qoidasi yuqorida.

    `only` berilsa faqat shu ish markazlarining ma'lumoti o'qiladi. Hisob har ish markazi
    uchun mustaqil, ya'ni ularning qatorlari `only` siz hisobdagi bilan AYNAN bir xil —
    tablodagi bitta stanok oynasi butun tsexni uch marta (1/7/30 kun) hisoblamasin."""

    def faqat(col: InstrumentedAttribute[int]) -> ColumnElement[bool]:
        return col.in_(only) if only is not None else true()

    start, end = _range(date_from, date_to)
    # OEE kesim sanasi: undan oldingi kunlar hisobotga UMUMAN kirmaydi (sozlamada,
    # `settings_service.OEE_START_DATE`). Tsexda OEE jadval/sabab/ideal sikl sozlangandan
    # keyin ma'no kasb etadi — undan oldingi qayd o'rtachani pastga tortardi.
    oee_start = await get_oee_start(db)
    if oee_start is not None:
        start = max(start, datetime.combine(oee_start, time.min, tzinfo=TASHKENT_TZ))
    now = datetime.now(UTC)
    if start > end:
        # So'ralgan oraliq BUTUNLAY kesimdan oldin — hisoblanadigan narsa yo'q
        bosh = MachineTimeReport(
            date_from=start.date(),
            date_to=end.date(),
            rows=[],
            days=[],
            schedule_set=bool((await get_work_schedule(db)).shifts),
            idle_threshold_min=int(await get_setting(db, STOP_PROMPT_IDLE_MINUTES)),
            ideal_cycle=await get_ideal_cycle(db),
            ideal_cycle_kromka=await get_ideal_cycle_kromka(db),
            ideal_cycle_rover=await get_ideal_cycle_rover(db),
            oee_start=oee_start,
        )
        return bosh
    events = (
        (
            await db.execute(
                select(AndonEvent.machine_id, AndonEvent.prev_state, AndonEvent.prev_duration_s, AndonEvent.happened_at)
                .where(
                    AndonEvent.kind == "state",
                    AndonEvent.is_deleted == False,  # noqa: E712
                    AndonEvent.happened_at >= start,
                    AndonEvent.happened_at <= end + _ANDON_TAIL,
                    faqat(AndonEvent.machine_id),
                )
                .order_by(AndonEvent.machine_id, AndonEvent.happened_at, AndonEvent.id)
            )
        )
        .tuples()
        .all()
    )

    # Tugamagan oxirgi holat — agent hali tirik bo'lsa, so'ralgan oraliq qanday bo'lmasin (docs/12 §4.21).
    # Ilgari faqat `end >= now` da qo'shilardi: «Kecha» so'rovida kechagi 15:00 da boshlanib hali
    # davom etayotgan holat yo'qolib, o'sha kun «Kecha + bugun» so'rovidagidan boshqacha chiqardi.
    # Kesish `machine_time` da: oraliq `min(end, now)` da to'xtaydi.
    # Har ish markazining OXIRGI holati — «guruhdagi oxirgi qator» LATERAL + LIMIT 1 bilan:
    # `ix_andon_event_live (kind, machine_id, happened_at)` dan har stanokka bitta qator
    # o'qiladi. `DISTINCT ON` butun `state` tarixini o'qib saralardi — narxi tarix bilan
    # o'sardi (2026-09-26 da 6 282 qator, 7,5 ms), bu esa stanok soniga bog'liq xolos.
    oxirgi = (
        select(AndonEvent.state, AndonEvent.happened_at)
        .where(
            AndonEvent.machine_id == Machine.id,
            AndonEvent.kind == "state",
            AndonEvent.is_deleted == False,  # noqa: E712
            AndonEvent.state.is_not(None),
        )
        .order_by(AndonEvent.happened_at.desc(), AndonEvent.id.desc())
        .limit(1)
        .lateral()
    )
    last_states = (
        await db.execute(
            select(Machine.id, oxirgi.c.state, oxirgi.c.happened_at)
            .join(oxirgi, true())
            # Oraliqdan keyin boshlangan holat bu hisobotga tegishli emas
            .where(faqat(Machine.id), oxirgi.c.happened_at <= end)
            .order_by(Machine.id)
        )
    ).all()
    live = await read_live(mid for mid, _state, _at in last_states)
    ongoing: dict[int, tuple[str, datetime]] = {
        mid: (state, at)
        for mid, state, at in last_states
        if state is not None and live.get(mid, {}).get("state") == state
    }

    spans = andon_spans(events, ongoing) + await uskuna_machine_spans(db, start, end, now, faqat(AndonEvent.machine_id))
    result = machine_time(spans, start, end, now)

    # OEE Availability: ish jadvali + to'xtashlar. Signal ustuni ulangan HAR ish markazi kiradi —
    # butun davr o'chiq turgan stanok hisobotdan tushib qolmay, 0% bo'lib ko'rinsin.
    andon_ids = (
        (
            await db.execute(
                select(Machine.id).where(
                    Machine.is_deleted == False,  # noqa: E712
                    select(AndonEvent.id).where(AndonEvent.machine_id == Machine.id).exists(),
                    faqat(Machine.id),
                )
            )
        )
        .scalars()
        .all()
    )
    ids = set(result.seconds) | set(andon_ids)
    schedule = await get_work_schedule(db)
    idle_minutes = int(await get_setting(db, STOP_PROMPT_IDLE_MINUTES))
    windows = plan_windows(schedule, start, min(end, now))
    reason_rows = (
        (
            await db.execute(
                select(
                    Downtime.machine_id,
                    Downtime.started_at,
                    Downtime.ended_at,
                    DowntimeReason.id,
                    DowntimeReason.name,
                    DowntimeReason.is_planned,
                )
                .join(DowntimeReason, DowntimeReason.id == Downtime.reason_id)
                .where(
                    Downtime.is_deleted == False,  # noqa: E712
                    # Qulf (LOCK) vaqt tashimaydi: stanokning o'zi to'xtaganini Pico yozadi va
                    # qulf ostida boshlangan to'xtash sababni `sync_machine` da allaqachon olgan.
                    Downtime.kind != DowntimeKind.LOCK,
                    Downtime.started_at <= end,
                    or_(Downtime.ended_at.is_(None), Downtime.ended_at >= start),
                    faqat(Downtime.machine_id),
                )
            )
        )
        .tuples()
        .all()
    )
    avail = {
        mid: availability(
            [s for s in spans if s.machine_id == mid],
            windows,
            timedelta(minutes=idle_minutes),
            now,
            _reason_lookup([r for r in reason_rows if r[0] == mid], now),
        )
        for mid in ids
    }
    names = dict((await db.execute(select(Machine.id, Machine.name).where(Machine.id.in_(ids)))).tuples().all())

    post_kodi = dict(
        (
            await db.execute(
                select(Machine.id, Post.code)
                .join(Post, Post.id == Machine.post_id)
                .where(Machine.id.in_(ids), Post.code.in_((PostCode.PRISADKA, PostCode.KROMKA, PostCode.ROVER)))
            )
        )
        .tuples()
        .all()
    )
    prisadka_ids = {mid for mid, kod in post_kodi.items() if kod == PostCode.PRISADKA}
    kromka_ids = {mid for mid, kod in post_kodi.items() if kod == PostCode.KROMKA}
    rover_ids = {mid for mid, kod in post_kodi.items() if kod == PostCode.ROVER}
    #: Quality hisoblanadigan stanoklar. Kromkada BITTA SKAN = BITTA QIRRA o'tishi
    #: (`per_instance` = qirralar soni), o'lchov ham qirra bo'yicha keladi — ya'ni surat
    #: va maxraj bir xil birlikda. ROVER'da birlik — DETAL (skan), Prisadkadagi kabi.
    #: Boshqa postlarda o'lchov manbasi yo'q, Quality `—`.
    quality_ids = prisadka_ids | kromka_ids | rover_ids

    # OEE Quality: BRAK — SKANNING xossasi (2026-10-16, docs/12 §4.17). U skan qilingan VAQTDA va
    # STANOKDA sanaladi, BRAK tugmasi bosilgan paytda emas: tushlikda, smenadan keyin yoki ertasi
    # kuni bosilgan brak ham o'z detalining kuniga tushadi. Surat (brak) shu bilan doim maxraj
    # (sanalgan detallar) ichida — Quality 0..100 dan chiqmaydi. Skansiz eski yozuv — o'z vaqti.
    # Brak kiritilmagan bo'lsa Quality 100%: ayiriladigan narsa yo'q.
    defects_by: dict[tuple[int, date], int] = {}
    if quality_ids:
        brak_stanok = func.coalesce(Scan.machine_id, PartDefect.machine_id)
        brak_vaqt = func.coalesce(Scan.created_at, PartDefect.created_at)
        defect_rows = (
            (
                await db.execute(
                    select(brak_stanok, brak_vaqt)
                    .select_from(PartDefect)
                    .outerjoin(Scan, Scan.id == PartDefect.scan_id)
                    .where(
                        brak_stanok.in_(quality_ids),
                        # «Brak emas» deb rad etilgani sanalmaydi; tasdiq kutayotgani SANALADI —
                        # aks holda tasdiq kechikkanda OEE aslidan yaxshi ko'rinib turardi
                        PartDefect.status != DefectStatus.REJECTED,
                        PartDefect.is_deleted == False,  # noqa: E712
                        # Skani sanalgan bo'lsin (detallar bilan bir xil shart) — operator skanni
                        # brakdan keyin o'zi bekor qilsa, brak ham maxrajdan tashqarida qolmasin
                        or_(Scan.id.is_(None), Scan.is_cancelled == False, Scan.defect_id.is_not(None)),  # noqa: E712
                        brak_vaqt >= start,
                        brak_vaqt <= end,
                    )
                )
            )
            .tuples()
            .all()
        )
        for mid, at in defect_rows:
            if mid is not None and mid in avail and inside(avail[mid].observed, at):
                key = (mid, at.astimezone(TASHKENT_TZ).date())
                defects_by[key] = defects_by.get(key, 0) + 1

    # OEE Performance (Prisadka): KUZATILGAN ish vaqtida skanerlangan detallarning ideal vaqti ÷ ishlagan vaqt.
    # Ma'lumotsiz vaqtdagi skan sanalmaydi — o'sha vaqt `run_s` ga ham kirmagan, aks holda foiz shishardi.
    ideal = await get_ideal_cycle(db)
    # KROMKA: ideal vaqtni lenta belgilaydi — har O'TISH uchun `L / v + oraliq`
    # (`services/performance.kromka_ideal_seconds`). Uzunlikni stansiyaning o'zi o'lchaydi,
    # ya'ni bu yerda taxminiy koeffitsiyent yo'q; sozlanadigani — detallar oralig'i.
    ideal_kromka = await get_ideal_cycle_kromka(db)
    ideal_by: dict[tuple[int, date], list[float]] = {}  # (stanok, kun) -> [ideal soniya, detallar]
    measured: dict[int, list[float]] = {}  # stanok -> [o'lchangan sikl soniya, sikllar]
    if prisadka_ids:
        counts = [
            func.coalesce(Part.xnc_summary[key].as_integer(), 0) for key in ("bores", "edge_bores", "grooves", "mills")
        ]
        scan_rows = (
            (
                await db.execute(
                    select(Scan.machine_id, Scan.created_at, *counts)
                    .join(Part, Part.id == Scan.part_id)
                    .where(
                        Scan.machine_id.in_(prisadka_ids),
                        # Brak TASDIG'I bekor qilgan skan ham sanaladi: ish qilingan (docs/12 §4.17)
                        or_(Scan.is_cancelled == False, Scan.defect_id.is_not(None)),  # noqa: E712
                        Scan.is_deleted == False,  # noqa: E712
                        Scan.created_at >= start,
                        Scan.created_at <= end,
                    )
                )
            )
            .tuples()
            .all()
        )
        for mid, at, bores, edge_bores, grooves, mills in scan_rows:
            if mid is not None and inside(avail[mid].observed, at):
                cell = ideal_by.setdefault((mid, at.astimezone(TASHKENT_TZ).date()), [0.0, 0])
                cell[0] += ideal_seconds(ideal, bores, edge_bores, grooves, mills)
                cell[1] += 1
        cycle_rows = (
            (
                await db.execute(
                    select(AndonEvent.machine_id, AndonEvent.happened_at, AndonEvent.payload).where(
                        AndonEvent.kind == "cycle",
                        AndonEvent.is_deleted == False,  # noqa: E712
                        AndonEvent.machine_id.in_(prisadka_ids),
                        AndonEvent.happened_at >= start,
                        AndonEvent.happened_at <= end,
                    )
                )
            )
            .tuples()
            .all()
        )
        for mid, at, payload in cycle_rows:
            # `payload` — Pico'dan kelgan xom JSON (`AndonEventIn` extra="allow"):
            # maydon yo'q yoki son emas bo'lishi mumkin
            seconds = sum(
                v for v in (payload.get("wait_s"), payload.get("process_s")) if type(v) in (int, float) and v > 0
            )
            if payload.get("completed") is not False and seconds > 0 and inside(avail[mid].observed, at):
                cell = measured.setdefault(mid, [0.0, 0])
                cell[0] += seconds
                cell[1] += 1

    if kromka_ids:
        # Manba — STANSIYA o'lchovlari: har hodisa bitta jismoniy o'tish. Detal to'rt
        # qirrali bo'lsa to'rt marta o'tadi va to'rtalasi ham sanaladi — stanok rostdan
        # shuncha ish qilgan. Skanlar bu yerda ishlatilmaydi: ular odam harakatiga
        # bog'liq, o'lchov esa lentaning o'ziga.
        olchov_rows = (
            (
                await db.execute(
                    select(AndonEvent.machine_id, AndonEvent.happened_at, AndonEvent.payload).where(
                        AndonEvent.kind == "olchov",
                        AndonEvent.is_deleted == False,  # noqa: E712
                        AndonEvent.machine_id.in_(kromka_ids),
                        AndonEvent.happened_at >= start,
                        AndonEvent.happened_at <= end,
                    )
                )
            )
            .tuples()
            .all()
        )
        for mid, at, payload in olchov_rows:
            if mid is None or not inside(avail[mid].observed, at):
                continue
            uzunlik = payload.get("L")
            tezlik = payload.get("v_nom") or payload.get("v_olch")
            sek = kromka_ideal_seconds(
                ideal_kromka,
                float(uzunlik) if type(uzunlik) in (int, float) else None,
                float(tezlik) if type(tezlik) in (int, float) else None,
            )
            if sek is None:
                continue
            cell = ideal_by.setdefault((mid, at.astimezone(TASHKENT_TZ).date()), [0.0, 0])
            cell[0] += sek
            cell[1] += 1

    ideal_rover = await get_ideal_cycle_rover(db)
    if rover_ids:
        await _rover_parts(db, rover_ids, avail, start, end, ideal_rover, ideal_by)

    def perf(mid: int, ideal_s: float, run_s: int) -> float | None:
        return round(ideal_s * 100 / run_s, 1) if mid in quality_ids and run_s > 0 else None

    rows = []
    for mid in sorted(ids, key=lambda m: names.get(m, "")):
        a = avail[mid].total
        ideal_total = sum(v[0] for (m, _d), v in ideal_by.items() if m == mid)
        parts_total = int(sum(v[1] for (m, _d), v in ideal_by.items() if m == mid))
        defects_total = sum(n for (m, _d), n in defects_by.items() if m == mid)
        # Quality FAQAT brak sanaladigan ish markazida (Prisadka va Kromka — `quality_ids`);
        # boshqa postlarda o'lchov manbasi yo'q, ya'ni Quality `None`.
        row_quality = quality_pct(parts_total, defects_total) if mid in quality_ids else None
        rows.append(
            MachineTimeRow(
                machine_id=mid,
                machine_name=names.get(mid, f"#{mid}"),
                shift_s=a.shift_s,
                planned_s=a.planned_s,
                unplanned_stop_s=a.unplanned_stop_s,
                no_data_s=a.no_data_s,
                run_s=a.run_s,
                availability_pct=a.availability_pct,
                reasons=[
                    AvailabilityReason(
                        reason_id=r.reason_id,
                        name=r.name or "Sabab kiritilmagan",
                        is_planned=r.is_planned,
                        seconds=r.seconds,
                        count=r.count,
                    )
                    for r in avail[mid].reasons
                ],
                parts=parts_total,
                ideal_s=round(ideal_total),
                performance_pct=perf(mid, ideal_total, a.run_s),
                cycles=int(measured.get(mid, [0.0, 0])[1]),
                measured_cycle_s=round(measured.get(mid, [0.0, 0])[0]),
                defects=defects_total,
                quality_pct=row_quality,
                oee_pct=oee_pct(a.availability_pct, perf(mid, ideal_total, a.run_s), row_quality),
            )
        )
    empty_day = DayTotals()
    day_keys = set(result.days) | {(mid, day) for mid, a_m in avail.items() for day in a_m.days}
    days = []
    for mid, day in sorted(day_keys):
        d = avail[mid].days.get(day, empty_day)
        day_parts = int(ideal_by.get((mid, day), [0.0, 0])[1])
        day_defects = defects_by.get((mid, day), 0)
        day_quality = quality_pct(day_parts, day_defects) if mid in quality_ids else None
        days.append(
            MachineTimeDay(
                machine_id=mid,
                day=day,
                seconds=result.days.get((mid, day)) or dict.fromkeys(ANDON_STATES, 0),
                planned_s=d.planned_s,
                run_s=d.run_s,
                availability_pct=d.availability_pct,
                parts=day_parts,
                defects=day_defects,
                quality_pct=day_quality,
                oee_pct=oee_pct(
                    d.availability_pct,
                    perf(mid, ideal_by.get((mid, day), [0.0, 0])[0], d.run_s),
                    day_quality,
                ),
            )
        )
    return MachineTimeReport(
        date_from=start.date(),
        date_to=end.date(),
        rows=rows,
        days=days,
        schedule_set=bool(schedule.shifts),
        idle_threshold_min=idle_minutes,
        ideal_cycle=ideal,
        ideal_cycle_kromka=ideal_kromka,
        ideal_cycle_rover=ideal_rover,
        oee_start=oee_start,
    )


# ---------- 11.2 Buyurtmalar holati ----------


@router.get("/orders", operation_id="report_orders", response_model=OrdersReport)
async def report_orders(
    db: SessionDep,
    _: ReportsUser,
    date_from: date | None = None,
    date_to: date | None = None,
    format: Annotated[Literal["json", "xlsx"], Query()] = "json",
) -> OrdersReport | StreamingResponse:
    start, end = _range(date_from, date_to)
    today = datetime.now(TASHKENT_TZ).date()
    rows = (
        await db.execute(
            select(Order, Client.full_name)
            .join(Client, Client.id == Order.client_id)
            .options(*(defer(c) for c in ORDER_FAT_COLUMNS))
            .where(Order.created_at.between(start, end), Order.is_deleted == False)  # noqa: E712
            .order_by(Order.id.desc())
        )
    ).all()
    data = [
        OrderReportRow(
            number=o.number,
            client_name=client_name,
            status=str(o.status),
            created_at=o.created_at,
            deadline=o.deadline,
            production_started_at=o.production_started_at,
            completed_at=o.completed_at,
            delivered_at=o.delivered_at,
            overdue=(
                o.deadline is not None
                and o.deadline < today
                and o.status in (OrderStatus.DRAFT, OrderStatus.TECHNICAL_REVIEW, OrderStatus.PRODUCTION)
            ),
            cancel_reason=o.cancel_reason,
        )
        for o, client_name in rows
    ]
    report = OrdersReport(date_from=start.date(), date_to=end.date(), rows=data)
    if format == "xlsx":
        return xlsx_response(
            "Buyurtmalar",
            [
                "Raqam",
                "Mijoz",
                "Holat",
                "Ochilgan",
                "Muddat",
                "Ishga tushgan",
                "Tayyor",
                "Topshirilgan",
                "Kechikkan",
                "Bekor sababi",
            ],
            [
                [
                    r.number,
                    r.client_name,
                    r.status,
                    r.created_at,
                    r.deadline,
                    r.production_started_at,
                    r.completed_at,
                    r.delivered_at,
                    "HA" if r.overdue else "",
                    r.cancel_reason or "",
                ]
                for r in data
            ],
            f"buyurtmalar_{report.date_from}_{report.date_to}.xlsx",
        )
    return report


# ---------- 11.3 Material sarfi ----------


@router.get("/materials", operation_id="report_materials", response_model=MaterialsReport)
async def report_materials(
    db: SessionDep,
    _: ReportsUser,
    date_from: date | None = None,
    date_to: date | None = None,
    format: Annotated[Literal["json", "xlsx"], Query()] = "json",
) -> MaterialsReport | StreamingResponse:
    start, end = _range(date_from, date_to)
    orders = (
        (
            await db.execute(
                select(Order.material_usage).where(
                    Order.project_loaded_at.between(start, end),
                    Order.status != OrderStatus.CANCELLED,
                    Order.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    agg: dict[tuple[str, str], MaterialUsageRow] = {}
    for usage in orders:
        # `orders` — buyurtmalar soni, JSONB yozuvlar soni emas: bitta buyurtmada bir material
        # bir necha marta uchrashi mumkin, ammo u faqat bir marta sanaladi.
        seen: set[tuple[str, str]] = set()
        for item in usage or []:
            # Barqaror kalit — katalog kodi (SKU); eski eksportlarda `code` yo'q, o'shanda nomga qaytamiz.
            key = (item.get("code") or item["name"], item["kind"])
            row = agg.get(key)
            if row is None:
                row = MaterialUsageRow(
                    name=item["name"],
                    code=item.get("code"),
                    kind=item["kind"],
                    unit=item.get("unit", ""),
                    total=0.0,
                    orders=0,
                )
                agg[key] = row
            row.total += float(item.get("count") or 0)
            if key not in seen:
                seen.add(key)
                row.orders += 1
    data = sorted(agg.values(), key=lambda r: (-r.total, r.name))
    report = MaterialsReport(date_from=start.date(), date_to=end.date(), rows=data)
    if format == "xlsx":
        return xlsx_response(
            "Material sarfi",
            ["Material", "Turi", "Birlik", "Jami sarf", "Buyurtmalar soni"],
            [[r.name, _KIND_LABELS.get(r.kind, r.kind), r.unit, round(r.total, 2), r.orders] for r in data],
            f"materiallar_{report.date_from}_{report.date_to}.xlsx",
        )
    return report


# ---------- Boshqaruv paneli ----------

_MANAGEMENT = (UserRole.ADMIN, UserRole.MANAGER, UserRole.DIRECTOR)


@router.get("/dashboard", operation_id="report_dashboard")
async def report_dashboard(db: SessionDep, current_user: DashboardUser) -> DashboardStats:
    """Bir so'rov — butun panel: bugungi puls, buyurtma sonlari, tayyorlar ro'yxati,
    post yuklamasi, 14 kunlik skan tendensiyasi va (boshqaruvga) qoldiq to'lovlar.

    Ilgari faqat ish markazi navbatini qaytarardi; panel qolganini 45 ta buyurtma
    kartasini chizib «ko'rsatardi» — bu Tablo'ning ishi, panel esa javob berishi
    kerak: bugun nima bo'lyapti, nima kechikdi, nimani topshirish kerak.
    """
    today = datetime.now(TASHKENT_TZ).date()
    today_start = datetime.combine(today, time.min, tzinfo=TASHKENT_TZ).astimezone(UTC)
    trend_start = today_start - timedelta(days=13)
    kun = func.date(func.timezone(TASHKENT_TZ.key, Scan.created_at))
    live_scan = (Scan.is_cancelled == False, Scan.is_deleted == False)  # noqa: E712

    # --- skanlar: 14 kunlik tendensiya (bugun va kecha ham shundan) ---
    trend_rows: dict[date, int] = {
        d: int(n)
        for d, n in (
            await db.execute(
                select(kun, func.count(Scan.id)).where(Scan.created_at >= trend_start, *live_scan).group_by(kun)
            )
        ).all()
    }
    trend = [
        TrendDay(day=d, scans=int(trend_rows.get(d, 0))) for d in (today - timedelta(days=i) for i in range(13, -1, -1))
    ]

    # --- smenada: bugun ochilgan, hali yopilmagan ---
    on_shift = (
        await db.execute(
            select(func.count(func.distinct(WorkSession.employee_id))).where(
                WorkSession.status == SessionStatus.ACTIVE,
                WorkSession.created_at >= today_start,
                WorkSession.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one()

    # --- buyurtma sonlari: bitta o'tish, filtrli agregatlar ---
    in_prod = Order.status == OrderStatus.PRODUCTION
    counts = (
        await db.execute(
            select(
                func.count(Order.id).filter(in_prod),
                func.count(Order.id).filter(in_prod, Order.deadline < today),
                func.count(Order.id).filter(in_prod, Order.deadline == today),
                func.count(Order.id).filter(in_prod, Order.deadline.is_(None)),
                func.count(Order.id).filter(Order.status == OrderStatus.COMPLETED),
                func.count(Order.id).filter(Order.production_started_at >= today_start),
                func.count(Order.id).filter(Order.completed_at >= today_start),
                func.count(Order.id).filter(Order.delivered_at >= today_start),
            ).where(Order.is_deleted == False)  # noqa: E712
        )
    ).one()
    production, overdue, due_today, no_deadline, ready_n, started, completed, delivered = (int(c) for c in counts)

    # --- topshirishga tayyor: eng uzoq kutayotgani birinchi ---
    ready_rows = (
        await db.execute(
            select(Order, Client.full_name)
            .join(Client, Client.id == Order.client_id)
            .options(*(defer(c) for c in ORDER_FAT_COLUMNS))
            .where(Order.status == OrderStatus.COMPLETED, Order.is_deleted == False)  # noqa: E712
            .order_by(Order.completed_at.asc().nulls_last(), Order.id)
            .limit(50)
        )
    ).all()
    ready = [
        ReadyOrder(
            id=o.id,
            number=o.number,
            client_name=name,
            project_name=o.project_name,
            completed_at=o.completed_at or o.created_at,
            waiting_days=(today - (o.completed_at or o.created_at).astimezone(TASHKENT_TZ).date()).days,
        )
        for o, name in ready_rows
    ]

    # --- post yuklamasi: qolgan marshrut qadamlari (Tablo bilan bir xil hisob) ---
    posts = (
        (await db.execute(select(Post).where(Post.is_deleted == False).order_by(Post.order_index)))  # noqa: E712
        .scalars()
        .all()
    )
    routes = (
        await db.execute(
            select(
                PartRoute.post_id,
                PartRoute.order_id,
                PartRoute.part_id,
                PartRoute.total_done,
                PartRoute.total_required,
                Part.length,
                Part.width,
                Part.count.label("part_count"),
                Part.edges,
            )
            .join(Part, Part.id == PartRoute.part_id)
            .join(Order, Order.id == PartRoute.order_id)
            .where(
                in_prod,
                Order.is_deleted == False,  # noqa: E712
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
                PartRoute.total_done < PartRoute.total_required,
            )
        )
    ).all()
    queue: dict[int, dict[str, float]] = {p.id: {"scans": 0, "volume": 0.0} for p in posts}
    queue_orders: dict[int, set[int]] = {p.id: set() for p in posts}
    posts_by_id = {p.id: p for p in posts}
    # Hajm detal+post juftligi uchun BIR MARTA, QOLGAN ulushi esa o'sha juftlikning
    # hamma qatoridan yig'iladi — qoida va sababi `metrics.VolumeShare` da
    # (`tablo.py` aynan shu hisobdan yuradi, faqat u BAJARILGANini oladi).
    part_vol: dict[tuple[int, int], VolumeShare] = {}
    for r in routes:
        post = posts_by_id.get(r.post_id)
        if post is None:
            continue
        remaining = r.total_required - r.total_done
        queue[r.post_id]["scans"] += remaining
        queue_orders[r.post_id].add(r.order_id)
        share = part_vol.get((r.part_id, r.post_id))
        if share is None:
            vol = part_volume(str(post.code), length=r.length, width=r.width, count=r.part_count, edges=r.edges)
            share = VolumeShare(volume=vol)
            part_vol[(r.part_id, r.post_id)] = share
        share.scans += remaining
        share.required += r.total_required

    for (_part_id, post_id), share in part_vol.items():
        queue[post_id]["volume"] += share.share()
    today_by_post: dict[int, int] = {
        pid: int(n)
        for pid, n in (
            await db.execute(
                select(Scan.post_id, func.count(Scan.id))
                .where(Scan.created_at >= today_start, *live_scan)
                .group_by(Scan.post_id)
            )
        ).all()
    }
    down_by_post: dict[int, list[str]] = {}
    for m in (
        (
            await db.execute(
                select(Machine)
                .where(Machine.is_deleted == False, Machine.status != MachineStatus.ACTIVE)  # noqa: E712
                .order_by(Machine.name)
            )
        )
        .scalars()
        .all()
    ):
        down_by_post.setdefault(m.post_id, []).append(m.name)
    post_load = [
        PostLoad(
            post_id=p.id,
            code=str(p.code),
            name=p.name,
            unit=POST_UNIT_LABELS.get(PostUnit(p.unit), ""),
            queue_scans=int(queue[p.id]["scans"]),
            queue_volume=round(queue[p.id]["volume"], 1),
            orders=len(queue_orders[p.id]),
            today_scans=int(today_by_post.get(p.id, 0)),
            down=down_by_post.get(p.id, []),
        )
        for p in posts
    ]

    # --- qoldiq to'lovlar: faqat boshqaruvga ---
    money: DashboardMoney | None = None
    if current_user.is_superuser or current_user.role in _MANAGEMENT:
        remaining = Order.amount - func.coalesce(Order.advance_payment, 0)
        mrow = (
            await db.execute(
                select(
                    func.coalesce(func.sum(remaining), 0),
                    func.count(Order.id),
                    func.count(Order.id).filter(Order.status == OrderStatus.DELIVERED),
                ).where(
                    Order.is_deleted == False,  # noqa: E712
                    Order.status.not_in((OrderStatus.DRAFT, OrderStatus.CANCELLED)),
                    Order.amount.is_not(None),
                    remaining > 0,
                )
            )
        ).one()
        money = DashboardMoney(receivable=float(mrow[0]), orders=int(mrow[1]), delivered_unpaid=int(mrow[2]))

    return DashboardStats(
        today=DashboardToday(
            scans=trend[-1].scans,
            scans_yesterday=trend[-2].scans,
            on_shift=int(on_shift),
            started=started,
            completed=completed,
            delivered=delivered,
        ),
        orders=DashboardOrders(
            production=production, overdue=overdue, due_today=due_today, no_deadline=no_deadline, ready=ready_n
        ),
        ready=ready,
        posts=post_load,
        trend=trend,
        money=money,
    )
