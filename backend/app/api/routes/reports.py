"""Reports (TZ 11): productivity, order status, material consumption + Excel export.

Every endpoint returns JSON by default; `?format=xlsx` streams an Excel file (TZ 11.4).
Access: manager/director/admin (TZ 3.7).
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import defer

from app.api.deps import SessionDep, require_roles
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
)
from app.models.enums import OrderStatus, UserRole
from app.models.user import User
from app.services.excel import xlsx_response
from app.services.metrics import part_volume

router = APIRouter(prefix="/reports", tags=["reports"])

ReportsUser = Annotated[User, Depends(require_roles(UserRole.MANAGER, UserRole.DIRECTOR))]

_TASHKENT = ZoneInfo("Asia/Tashkent")


def _range(date_from: date | None, date_to: date | None) -> tuple[datetime, datetime]:
    """Default: last 30 days. Bounds are inclusive local (Asia/Tashkent) days."""
    end_day = date_to or datetime.now(_TASHKENT).date()
    start_day = date_from or (end_day - timedelta(days=30))
    start = datetime.combine(start_day, time.min, tzinfo=_TASHKENT)
    end = datetime.combine(end_day, time.max, tzinfo=_TASHKENT)
    return start, end


# ---------- 11.1.1 Hodim mahsuldorligi ----------


class EmployeeProductivity(BaseModel):
    employee_id: int
    full_name: str
    position: str | None
    total_scans: int
    active_days: int
    per_day: float
    per_hour: float  # scans / distinct active hours — crude but honest


class ProductivityReport(BaseModel):
    date_from: date
    date_to: date
    employees: list[EmployeeProductivity]


@router.get("/productivity", operation_id="report_productivity", response_model=ProductivityReport)
async def report_productivity(
    db: SessionDep,
    _: ReportsUser,
    date_from: date | None = None,
    date_to: date | None = None,
    format: Annotated[Literal["json", "xlsx"], Query()] = "json",
) -> ProductivityReport | StreamingResponse:
    start, end = _range(date_from, date_to)
    day = func.date_trunc("day", func.timezone(_TASHKENT.key, Scan.created_at))
    hour = func.date_trunc("hour", func.timezone(_TASHKENT.key, Scan.created_at))
    rows = (
        await db.execute(
            select(
                Employee.id,
                Employee.full_name,
                Employee.position,
                func.count(Scan.id),
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
            .order_by(func.count(Scan.id).desc())
        )
    ).all()

    employees = [
        EmployeeProductivity(
            employee_id=eid,
            full_name=name,
            position=position,
            total_scans=total,
            active_days=days,
            per_day=round(total / days, 1) if days else 0.0,
            per_hour=round(total / hours, 1) if hours else 0.0,
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


class OrderReportRow(BaseModel):
    number: str
    client_name: str
    status: str
    created_at: datetime
    deadline: date | None
    production_started_at: datetime | None
    completed_at: datetime | None
    delivered_at: datetime | None
    overdue: bool
    cancel_reason: str | None


class OrdersReport(BaseModel):
    date_from: date
    date_to: date
    rows: list[OrderReportRow]


@router.get("/orders", operation_id="report_orders", response_model=OrdersReport)
async def report_orders(
    db: SessionDep,
    _: ReportsUser,
    date_from: date | None = None,
    date_to: date | None = None,
    format: Annotated[Literal["json", "xlsx"], Query()] = "json",
) -> OrdersReport | StreamingResponse:
    start, end = _range(date_from, date_to)
    today = datetime.now(_TASHKENT).date()
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


class MaterialUsageRow(BaseModel):
    name: str
    kind: str
    unit: str
    total: float
    orders: int


class MaterialsReport(BaseModel):
    date_from: date
    date_to: date
    rows: list[MaterialUsageRow]


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


# ---------- 10.2.1 Dashboard: stanok yuklamasi + prognoz ----------


class MachineStat(BaseModel):
    machine_id: int
    name: str
    post_code: str
    status: str
    queue_scans: int  # remaining scans routed to this machine
    queue_volume: float  # in the post's unit
    unit: str
    capacity: float | None
    forecast_hours: float | None  # TZ 4.3: navbatdagi_yuk / capacity
    today_scans: int


class DashboardStats(BaseModel):
    machines: list[MachineStat]


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

    today_start = datetime.combine(datetime.now(_TASHKENT).date(), time.min, tzinfo=_TASHKENT).astimezone(UTC)
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
