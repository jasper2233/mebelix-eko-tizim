"""Reports (TZ 11): productivity, order status, material consumption + Excel export.

Every endpoint returns JSON by default; `?format=xlsx` streams an Excel file (TZ 11.4).
Access: manager/director/admin (TZ 3.7).
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased, defer

from app.api.deps import SessionDep, require_roles
from app.core.config import TASHKENT_TZ
from app.models import (
    ORDER_FAT_COLUMNS,
    PART_FAT_COLUMNS,
    Client,
    Employee,
    Machine,
    Order,
    Part,
    PartRoute,
    Post,
    Scan,
    WorkSession,
)
from app.models.enums import OrderStatus, UserRole
from app.models.user import User
from app.schemas.reports import (
    DashboardStats,
    EmployeeProductivity,
    MachineStat,
    MaterialsReport,
    MaterialUsageRow,
    OeeMachineRow,
    OeeReport,
    OeeStopRow,
    OrderReportRow,
    OrdersReport,
    ProductivityReport,
)
from app.services.excel import xlsx_response
from app.services.metrics import part_volume
from app.services.oee import machine_availability, machine_performance

router = APIRouter(prefix="/reports", tags=["reports"])

ReportsUser = Annotated[User, Depends(require_roles(UserRole.MANAGER, UserRole.DIRECTOR))]


def _range(date_from: date | None, date_to: date | None) -> tuple[datetime, datetime]:
    """Default: last 30 days. Bounds are inclusive local (Asia/Tashkent) days."""
    end_day = date_to or datetime.now(TASHKENT_TZ).date()
    start_day = date_from or (end_day - timedelta(days=30))
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

    # Brigada: bitta ish markazida ikki kishi ishlashi mumkin (ARRA — biri varaqni
    # beradi, ikkinchisi detalni oladi) va detalni qaysi biri olganini bilishning
    # iloji yo'q. Skan qatorida bitta `employee_id` bor — u LANGAR smena egasi,
    # ya'ni uni sanash ishni butunlay bitta odamga yozardi. Shuning uchun hisob
    # skan VAQTIDA ochiq bo'lgan smenalar bo'yicha yuritiladi va har skan ular
    # orasida TENG bo'linadi: zavod bir ishga bir marta to'laydi.
    #
    # LEFT JOIN ataylab: `scan.machine_id` NULL bo'lishi mumkin (ish markazisiz yozuv),
    # o'shanda mos smena topilmaydi va skan hisobdan tushib qolardi — bunday holda
    # `COALESCE` uni eski yo'l bilan `scan.employee_id` ga yozadi, brigada = 1.
    ws = aliased(WorkSession)
    member = (
        select(
            Scan.created_at.label("at"),
            func.coalesce(ws.employee_id, Scan.employee_id).label("employee_id"),
            func.count().over(partition_by=Scan.id).label("crew_size"),
        )
        .outerjoin(
            ws,
            and_(
                ws.machine_id == Scan.machine_id,
                ws.is_deleted == False,  # noqa: E712
                ws.created_at <= Scan.created_at,
                or_(ws.ended_at.is_(None), ws.ended_at >= Scan.created_at),
            ),
        )
        .where(
            Scan.created_at.between(start, end),
            Scan.is_cancelled == False,  # noqa: E712
            Scan.is_deleted == False,  # noqa: E712
        )
        .subquery()
    )

    day = func.date_trunc("day", func.timezone(TASHKENT_TZ.key, member.c.at))
    hour = func.date_trunc("hour", func.timezone(TASHKENT_TZ.key, member.c.at))
    credited = func.sum(1.0 / member.c.crew_size)
    rows = (
        await db.execute(
            select(
                Employee.id,
                Employee.full_name,
                Employee.position,
                credited,
                func.count(func.distinct(day)),
                func.count(func.distinct(hour)),
            )
            .join(member, member.c.employee_id == Employee.id)
            .group_by(Employee.id, Employee.full_name, Employee.position)
            .order_by(credited.desc())
        )
    ).all()

    employees = [
        EmployeeProductivity(
            employee_id=eid,
            full_name=name,
            position=position,
            total_scans=round(float(total), 1),
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
        for item in usage or []:
            key = (item["name"], item["kind"])
            row = agg.get(key)
            if row is None:
                row = MaterialUsageRow(
                    name=item["name"], kind=item["kind"], unit=item.get("unit", ""), total=0.0, orders=0
                )
                agg[key] = row
            row.total += float(item.get("count") or 0)
            row.orders += 1
    data = sorted(agg.values(), key=lambda r: (-r.total, r.name))
    report = MaterialsReport(date_from=start.date(), date_to=end.date(), rows=data)
    if format == "xlsx":
        return xlsx_response(
            "Material sarfi",
            ["Material", "Turi", "Birlik", "Jami sarf", "Buyurtmalar soni"],
            [[r.name, "List" if r.kind == "sheet" else "Kromka", r.unit, round(r.total, 2), r.orders] for r in data],
            f"materiallar_{report.date_from}_{report.date_to}.xlsx",
        )
    return report


# ---------- 10.2.1 Dashboard: ish markazi yuklamasi + prognoz ----------


@router.get("/dashboard", operation_id="report_dashboard")
async def report_dashboard(db: SessionDep, _: ReportsUser) -> DashboardStats:
    posts = {p.id: p for p in (await db.execute(select(Post))).scalars()}
    machines = (
        (
            await db.execute(
                select(Machine).where(Machine.is_deleted == False).order_by(Machine.name)  # noqa: E712
            )
        )
        .scalars()
        .all()
    )
    machines_by_post: dict[int, list[Machine]] = {}
    for m in machines:
        machines_by_post.setdefault(m.post_id, []).append(m)

    routes = (
        await db.execute(
            select(PartRoute, Part)
            .join(Part, Part.id == PartRoute.part_id)
            .join(Order, Order.id == PartRoute.order_id)
            # part_volume faqat length/width/count/edges o'qiydi — qolgan JSONB
            # ustunlar bekorga uzatilardi (navbat butun ishlab chiqarish bo'yicha)
            .options(*(defer(c) for c in PART_FAT_COLUMNS))
            .where(
                Order.status == OrderStatus.PRODUCTION,
                Order.is_deleted == False,  # noqa: E712
                PartRoute.is_enabled == True,  # noqa: E712
                PartRoute.is_deleted == False,  # noqa: E712
                PartRoute.total_done < PartRoute.total_required,
            )
        )
    ).all()

    queue: dict[int, dict[str, float]] = {m.id: {"scans": 0, "volume": 0.0} for m in machines}
    for route, part in routes:
        post = posts.get(route.post_id)
        if post is None:
            continue
        remaining = route.total_required - route.total_done
        vol = part_volume(str(post.code), length=part.length, width=part.width, count=part.count, edges=part.edges) * (
            remaining / route.total_required if route.total_required else 0
        )
        if route.machine_id is not None and route.machine_id in queue:
            targets = [route.machine_id]
        else:
            # ponytail: unassigned queue lands on the post's first machine; split when a post
            # actually runs several unassigned machines in parallel.
            post_machines = machines_by_post.get(route.post_id, [])
            targets = [post_machines[0].id] if post_machines else []
        for mid in targets:
            queue[mid]["scans"] += remaining
            queue[mid]["volume"] += vol

    today_start = datetime.combine(datetime.now(TASHKENT_TZ).date(), time.min, tzinfo=TASHKENT_TZ).astimezone(UTC)
    today_rows = (
        await db.execute(
            select(Scan.machine_id, func.count(Scan.id))
            .where(
                Scan.created_at >= today_start,
                Scan.is_cancelled == False,  # noqa: E712
                Scan.is_deleted == False,  # noqa: E712
            )
            .group_by(Scan.machine_id)
        )
    ).all()
    today_by_machine = {mid: cnt for mid, cnt in today_rows if mid is not None}

    unit_labels = {"m2": "m²", "meter": "metr", "piece": "dona"}
    stats: list[MachineStat] = []
    for m in machines:
        post = posts.get(m.post_id)
        q = queue[m.id]
        forecast: float | None = None
        if m.capacity and q["volume"]:
            forecast = round(q["volume"] / m.capacity, 1)
        stats.append(
            MachineStat(
                machine_id=m.id,
                name=m.name,
                post_code=str(post.code) if post else "",
                status=str(m.status),
                queue_scans=int(q["scans"]),
                queue_volume=round(q["volume"], 2),
                unit=unit_labels.get(str(post.unit), "") if post else "",
                capacity=m.capacity,
                forecast_hours=forecast,
                today_scans=today_by_machine.get(m.id, 0),
            )
        )
    return DashboardStats(machines=stats)


# ---------- OEE (Availability) ----------


@router.get("/oee", operation_id="report_oee", response_model=OeeReport)
async def report_oee(
    db: SessionDep,
    _: ReportsUser,
    date_from: date | None = None,
    date_to: date | None = None,
    post_id: int | None = None,
) -> OeeReport:
    """Ish markazlari bo'yicha Availability va to'xtalishlar tahlili.

    Hozircha OEE ning VAQT qismi: Performance ideal tezlik va ishlab chiqarilgan
    miqdorni, Quality esa brak hisobini talab qiladi — ular keyingi bosqichlarda.

    FAQAT STANOKLAR: `ideal_rate` to'ldirilgan ish markazlari. To'qqiz postning
    beshtasida haqiqiy stanok bor (ARRA, KROMKA, OVAL, PRISADKA, ROVER),
    qolganida esa brigada va monoblok — u yerda "uskuna samaradorligi" o'lchash
    mumkin bo'lgan uskunaning o'zi yo'q. Ro'yxat KODDA emas, sozlamada:
    admin ish markaziga ideal tezlik kiritsa, o'sha stanok kuzatuvga tushadi.

    NOAKTIV ish markazlari ham ro'yxatda: ta'mirda turgan stanok aynan eng katta
    yo'qotish manbai bo'lishi mumkin, uni yashirish ko'rsatkichni chiroylashtirardi.
    """
    end_day = date_to or datetime.now(TASHKENT_TZ).date()
    start_day = date_from or (end_day - timedelta(days=30))

    query = (
        select(Machine, Post)
        .join(Post, Post.id == Machine.post_id)
        .where(
            Machine.is_deleted == False,  # noqa: E712
            Machine.ideal_rate.is_not(None),
        )
        .order_by(Post.order_index, Machine.name)
    )
    if post_id is not None:
        query = query.where(Machine.post_id == post_id)

    out = OeeReport(date_from=start_day, date_to=end_day)
    for machine, post in (await db.execute(query)).all():
        result = await machine_availability(db, machine, start_day, end_day)
        perf = await machine_performance(db, machine, post, result.run_minutes, start_day, end_day)
        avail = result.value
        p_value = perf.value if perf else None
        out.machines.append(
            OeeMachineRow(
                machine_id=machine.id,
                machine_name=machine.name,
                post_code=post.code,
                post_name=post.name,
                active_days=result.active_days,
                planned_minutes=round(result.planned_minutes, 1),
                run_minutes=round(result.run_minutes, 1),
                planned_off_minutes=round(result.planned_off_minutes, 1),
                loss_minutes=round(result.loss_minutes, 1),
                availability=round(avail, 4) if avail is not None else None,
                quantity=round(perf.quantity, 2) if perf else 0.0,
                quantity_unit=perf.unit if perf else "",
                ideal_minutes=round(perf.ideal_minutes, 1) if perf else 0.0,
                performance=round(p_value, 4) if p_value is not None else None,
                oee_partial=(
                    round(avail * p_value, 4) if avail is not None and p_value is not None else None
                ),
                stops=[
                    OeeStopRow(
                        reason=line.reason,
                        minutes=round(line.minutes, 1),
                        count=line.count,
                        excludes_planned=line.excludes_planned,
                    )
                    for line in result.stops
                ],
            )
        )
    return out
