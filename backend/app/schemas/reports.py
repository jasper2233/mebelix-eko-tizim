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


# ---------- 10.2.1 Dashboard: ish markazi yuklamasi + prognoz ----------


class MachineStat(BaseModel):
    machine_id: int
    name: str
    post_code: str
    status: str
    queue_scans: int  # remaining scans routed to this machine
    queue_volume: float  # in the post's unit
    unit: str
    today_scans: int


class DashboardStats(BaseModel):
    machines: list[MachineStat]
