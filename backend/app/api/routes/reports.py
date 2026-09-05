"""Reports: productivity, order status, material consumption + Excel export.

Every endpoint returns JSON by default; `?format=xlsx` streams an Excel file.
Access: manager/director/admin.
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import defer

from app.api.deps import SessionDep, require_roles
from app.core.config import TASHKENT_TZ
from app.models import (
    ORDER_FAT_COLUMNS,
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
from app.models.enums import POST_UNIT_LABELS, MachineStatus, OrderStatus, PostUnit, SessionStatus, UserRole
from app.models.user import User
from app.schemas.reports import (
    DashboardMoney,
    DashboardOrders,
    DashboardStats,
    DashboardToday,
    EmployeeProductivity,
    MaterialsReport,
    MaterialUsageRow,
    OrderReportRow,
    OrdersReport,
    PostLoad,
    ProductivityReport,
    ReadyOrder,
    TrendDay,
)
from app.services.excel import xlsx_response
from app.services.metrics import part_volume

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
    # Hajm detal+post juftligi uchun BIR MARTA — sabab `tablo.py` dagi bilan bir xil.
    seen_volume: set[tuple[int, int]] = set()
    for r in routes:
        post = posts_by_id.get(r.post_id)
        if post is None:
            continue
        remaining = r.total_required - r.total_done
        queue[r.post_id]["scans"] += remaining
        queue_orders[r.post_id].add(r.order_id)
        if (r.part_id, r.post_id) in seen_volume:
            continue
        seen_volume.add((r.part_id, r.post_id))
        vol = part_volume(str(post.code), length=r.length, width=r.width, count=r.part_count, edges=r.edges)
        queue[r.post_id]["volume"] += vol * (remaining / r.total_required if r.total_required else 0)
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
