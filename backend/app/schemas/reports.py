"""Hisobotlar va dashboard javob sxemalari."""

from datetime import date, datetime

from pydantic import BaseModel

# ---------- 11.1.1 Hodim mahsuldorligi ----------


class EmployeeProductivity(BaseModel):
    employee_id: int
    full_name: str
    position: str | None
    total_scans: int  # skan uni urgan hodimga to'liq (brigada bo'linishi yo'q)
    active_days: int
    per_day: float
    per_hour: float  # scans / distinct active hours — crude but honest


class ProductivityReport(BaseModel):
    date_from: date
    date_to: date
    employees: list[EmployeeProductivity]


# ---------- Stanok vaqti (andon — signal ustuni) ----------


class MachineTimeRow(BaseModel):
    machine_id: int
    machine_name: str
    # holat -> soniya: PROCESSING, AWAIT_PART, IDLE, STOPPED, FAULT, OFF
    seconds: dict[str, int]
    total_s: int  # jami qayd etilgan vaqt — agent/Pico bilan aloqa yo'q paytlar kirmaydi
    busy_pct: float | None  # ishlov / jami qayd — OEE Availability EMAS (reja vaqti yo'q)
    faults: int  # oraliqqa tushgan avariyalar soni


class MachineTimeDay(BaseModel):
    machine_id: int
    day: date  # Toshkent kuni
    seconds: dict[str, int]


class MachineTimeStop(BaseModel):
    machine_id: int
    machine_name: str
    state: str  # FAULT | STOPPED
    started_at: datetime
    ended_at: datetime | None  # None — hali davom etmoqda
    duration_s: int


class MachineTimeReport(BaseModel):
    date_from: date
    date_to: date
    rows: list[MachineTimeRow]
    days: list[MachineTimeDay]
    stops: list[MachineTimeStop]  # eng yangisi birinchi, ko'pi bilan 200 ta


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


# ---------- 11.3 Material sarfi ----------


class MaterialUsageRow(BaseModel):
    name: str
    # Katalog kodi (SKU) — bir nomli ikki material qatorini ajratadi; eski eksportlarda yo'q
    code: str | None = None
    kind: str
    unit: str
    total: float
    orders: int


class MaterialsReport(BaseModel):
    date_from: date
    date_to: date
    rows: list[MaterialUsageRow]


# ---------- Dashboard ----------


class DashboardToday(BaseModel):
    scans: int
    scans_yesterday: int
    on_shift: int  # bugun beyjik bilan ochilgan va hali yopilmagan smenalar (hodim soni)
    started: int  # bugun ishlab chiqarishga uzatilgan buyurtmalar
    completed: int
    delivered: int


class DashboardOrders(BaseModel):
    production: int
    overdue: int  # jarayonda, muddati o'tgan
    due_today: int
    no_deadline: int  # jarayonda, muddati kiritilmagan
    ready: int  # tayyor (COMPLETED), hali topshirilmagan


class ReadyOrder(BaseModel):
    id: int
    number: str
    client_name: str
    project_name: str | None
    completed_at: datetime
    waiting_days: int


class PostLoad(BaseModel):
    post_id: int
    code: str
    name: str
    unit: str
    queue_scans: int  # shu postda qolgan skanlar (barcha jarayondagi buyurtmalar)
    queue_volume: float  # post birligida (m² / m / dona)
    orders: int  # shu postda ishi qolgan buyurtmalar soni
    today_scans: int
    down: list[str]  # ishlamayotgan (ta'mir/o'chirilgan) ish markazlari nomlari


class TrendDay(BaseModel):
    day: date
    scans: int


class DashboardMoney(BaseModel):
    receivable: float  # narx − boshlang'ich to'lov, qoldig'i musbat buyurtmalar bo'yicha
    orders: int
    delivered_unpaid: int  # topshirilgan, lekin qoldiq bor


class DashboardStats(BaseModel):
    today: DashboardToday
    orders: DashboardOrders
    ready: list[ReadyOrder]
    posts: list[PostLoad]
    trend: list[TrendDay]  # oxirgi 14 kun, bo'sh kunlar 0 bilan
    money: DashboardMoney | None  # faqat boshqaruv (manager/direktor/admin) uchun
