"""Reports: productivity, order status, material consumption + Excel export.

Every endpoint returns JSON by default; `?format=xlsx` streams an Excel file.
Access: manager/director/admin.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import defer

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
    PartRoute,
    Post,
    Scan,
    WorkSession,
)
from app.models.enums import (
    POST_UNIT_LABELS,
    DowntimeKind,
    MachineStatus,
    OrderStatus,
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
    MachineTimeStop,
    MaterialsReport,
    MaterialUsageRow,
    OrderReportRow,
    OrdersReport,
    PostLoad,
    ProductivityReport,
    ReadyOrder,
    TrendDay,
)
from app.services.andon import ANDON_STATES, andon_spans, machine_time, read_live
from app.services.availability import DayTotals, StopRun, availability, plan_windows
from app.services.excel import xlsx_response
from app.services.metrics import VolumeShare, part_volume
from app.services.settings_service import STOP_PROMPT_IDLE_MINUTES, get_setting, get_work_schedule

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

#: Excel sarlavhalari va ustun tartibi — `ANDON_STATES` bilan bir xil tartib
_ANDON_LABELS = {
    "PROCESSING": "Ishlov",
    "AWAIT_PART": "Detal kutish",
    "IDLE": "Kutish",
    "STOPPED": "Uzoq kutish",
    "FAULT": "Avariya",
    "OFF": "O'chiq",
}
#: Oraliq tugagandan keyin kelgan hodisa ham oraliq ichidagi holatni yopgan bo'lishi
#: mumkin (masalan tungi OFF ertalab tugaydi) — shuncha kun keyingacha hodisa olinadi.
_ANDON_TAIL = timedelta(days=3)
_ANDON_STOPS_LIMIT = 200


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
    start, end = _range(date_from, date_to)
    now = datetime.now(UTC)
    events = (
        (
            await db.execute(
                select(AndonEvent.machine_id, AndonEvent.prev_state, AndonEvent.prev_duration_s, AndonEvent.happened_at)
                .where(
                    AndonEvent.kind == "state",
                    AndonEvent.is_deleted == False,  # noqa: E712
                    AndonEvent.happened_at >= start,
                    AndonEvent.happened_at <= end + _ANDON_TAIL,
                )
                .order_by(AndonEvent.machine_id, AndonEvent.happened_at, AndonEvent.id)
            )
        )
        .tuples()
        .all()
    )

    # Tugamagan oxirgi holat: faqat oraliq hozirni o'z ichiga olsa va agent hali tirik bo'lsa
    ongoing: dict[int, tuple[str, datetime]] = {}
    if end >= now:
        last_states = (
            await db.execute(
                select(AndonEvent.machine_id, AndonEvent.state, AndonEvent.happened_at)
                .where(
                    AndonEvent.kind == "state",
                    AndonEvent.is_deleted == False,  # noqa: E712
                    AndonEvent.state.is_not(None),
                )
                .distinct(AndonEvent.machine_id)
                .order_by(AndonEvent.machine_id, AndonEvent.happened_at.desc(), AndonEvent.id.desc())
            )
        ).all()
        live = await read_live(mid for mid, _state, _at in last_states)
        ongoing = {
            mid: (state, at)
            for mid, state, at in last_states
            if state is not None and live.get(mid, {}).get("state") == state
        }

    spans = andon_spans(events, ongoing)
    result = machine_time(spans, start, end, now)

    # OEE Availability: ish jadvali + to'xtashlar. Signal ustuni ulangan HAR ish markazi kiradi —
    # butun davr o'chiq turgan stanok hisobotdan tushib qolmay, 0% bo'lib ko'rinsin.
    andon_ids = (
        (
            await db.execute(
                select(Machine.id).where(
                    Machine.is_deleted == False,  # noqa: E712
                    select(AndonEvent.id).where(AndonEvent.machine_id == Machine.id).exists(),
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

    rows = []
    for mid in sorted(ids, key=lambda m: names.get(m, "")):
        secs = result.seconds.get(mid) or dict.fromkeys(ANDON_STATES, 0)
        total = sum(secs.values())
        a = avail[mid].total
        rows.append(
            MachineTimeRow(
                machine_id=mid,
                machine_name=names.get(mid, f"#{mid}"),
                seconds=secs,
                total_s=total,
                busy_pct=round(secs["PROCESSING"] * 100 / total, 1) if total else None,
                faults=result.faults.get(mid, 0),
                shift_s=a.shift_s,
                planned_stop_s=a.planned_stop_s,
                planned_s=a.planned_s,
                unplanned_stop_s=a.unplanned_stop_s,
                no_data_s=a.no_data_s,
                run_s=a.run_s,
                availability_pct=a.availability_pct,
                coverage_pct=a.coverage_pct,
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
            )
        )
    empty_day = DayTotals()
    day_keys = set(result.days) | {(mid, day) for mid, a_m in avail.items() for day in a_m.days}
    days = []
    for mid, day in sorted(day_keys):
        d = avail[mid].days.get(day, empty_day)
        days.append(
            MachineTimeDay(
                machine_id=mid,
                day=day,
                seconds=result.days.get((mid, day)) or dict.fromkeys(ANDON_STATES, 0),
                shift_s=d.shift_s,
                planned_stop_s=d.planned_stop_s,
                planned_s=d.planned_s,
                unplanned_stop_s=d.unplanned_stop_s,
                no_data_s=d.no_data_s,
                run_s=d.run_s,
                availability_pct=d.availability_pct,
            )
        )
    stops = [
        MachineTimeStop(
            machine_id=s.machine_id,
            machine_name=names.get(s.machine_id, f"#{s.machine_id}"),
            state=s.state,
            started_at=s.began,
            ended_at=s.ended,
            duration_s=int(((s.ended or now) - s.began).total_seconds()),
        )
        for s in result.stops[:_ANDON_STOPS_LIMIT]
    ]
    report = MachineTimeReport(
        date_from=start.date(),
        date_to=end.date(),
        rows=rows,
        days=days,
        stops=stops,
        schedule_set=bool(schedule.shifts),
        idle_threshold_min=idle_minutes,
    )
    if format == "xlsx":
        return xlsx_response(
            "Stanok vaqti",
            [
                "Stanok",
                "Reja vaqti (soat)",
                "Ishladi (soat)",
                "Rejasiz to'xtash (soat)",
                "Ma'lumot yo'q (soat)",
                "Rejali to'xtash (soat)",
                "Availability, %",
                "Qamrov, %",
                *(f"{_ANDON_LABELS[s]} (soat)" for s in ANDON_STATES),
                "Jami qayd (soat)",
                "Ishlov ulushi, %",
                "Avariyalar",
            ],
            [
                [
                    r.machine_name,
                    round(r.planned_s / 3600, 2),
                    round(r.run_s / 3600, 2),
                    round(r.unplanned_stop_s / 3600, 2),
                    round(r.no_data_s / 3600, 2),
                    round(r.planned_stop_s / 3600, 2),
                    r.availability_pct if r.availability_pct is not None else "",
                    r.coverage_pct if r.coverage_pct is not None else "",
                    *(round(r.seconds[s] / 3600, 2) for s in ANDON_STATES),
                    round(r.total_s / 3600, 2),
                    r.busy_pct if r.busy_pct is not None else "",
                    r.faults,
                ]
                for r in rows
            ],
            f"stanok_vaqti_{report.date_from}_{report.date_to}.xlsx",
        )
    return report


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
