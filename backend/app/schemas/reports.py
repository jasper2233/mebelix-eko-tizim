"""Hisobotlar (TZ 11) va dashboard (TZ 10.2.1) javob sxemalari."""

from datetime import date, datetime

from pydantic import BaseModel

# ---------- 11.1.1 Hodim mahsuldorligi ----------


class EmployeeProductivity(BaseModel):
    employee_id: int
    full_name: str
    position: str | None
    #: Brigadada bo'lingan skan soni — KASR bo'lishi mumkin: ikki kishi birga
    #: ishlagan skan har biriga 0.5 yoziladi (zavod bir ishga bir marta to'laydi).
    total_scans: float
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
    capacity: float | None
    forecast_hours: float | None  # TZ 4.3: navbatdagi_yuk / capacity
    today_scans: int


class DashboardStats(BaseModel):
    machines: list[MachineStat]


class OeeStopRow(BaseModel):
    """Bitta sabab bo'yicha yig'ma to'xtash — eng katta yo'qotish tepada turadi."""

    reason: str
    minutes: float
    count: int
    #: True — PLANNED dan ayrilgan (tushlik, tanaffus), ya'ni YO'QOTISH EMAS
    excludes_planned: bool


class OeeMachineRow(BaseModel):
    machine_id: int
    machine_name: str
    post_code: str
    post_name: str
    active_days: int
    planned_minutes: float
    run_minutes: float
    planned_off_minutes: float
    loss_minutes: float
    #: 0..1. None — o'sha davrda reja umuman bo'lmagan (ish markazi ishlamagan):
    #: "0%" ko'rsatish yolg'on bo'lardi
    availability: float | None
    stops: list[OeeStopRow] = []


class OeeReport(BaseModel):
    date_from: date
    date_to: date
    machines: list[OeeMachineRow] = []
