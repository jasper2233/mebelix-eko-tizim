"""Hisobotlar va dashboard javob sxemalari."""

from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.settings import IdealCycle, IdealCycleKromka

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


class AvailabilityReason(BaseModel):
    reason_id: int | None  # None — sabab kiritilmagan
    name: str
    is_planned: bool
    seconds: int  # to'xtashning ISH VAQTI ichidagi qismi
    count: int


class MachineTimeRow(BaseModel):
    """Bitta stanokning davr bo'yicha yakuni. Sahifada arifmetika KO'RINIB tursin:
    `reja vaqti − to'xtash = ishladi`, keyin uchala foiz va ularning ko'paytmasi."""

    machine_id: int
    machine_name: str
    # --- OEE Availability (`services/availability.py`). Ish jadvali kiritilmagan bo'lsa hammasi 0 / None.
    shift_s: int  # jadval bo'yicha ish vaqti: smenalar minus tanaffuslar, hozirgacha
    planned_s: int  # reja vaqti = ish vaqti − REJALI sababli to'xtashlar
    unplanned_stop_s: int  # rejasiz yoki sababi kiritilmagan to'xtashlar
    no_data_s: int  # ish vaqtida Pico'dan qayd yo'q — stanok O'CHIQ deb sanaladi (2026-09-17 qarori)
    run_s: int  # ishlagan = planned_s - unplanned_stop_s - no_data_s
    availability_pct: float | None  # run_s / planned_s; reja vaqti 0 bo'lsa None
    reasons: list[AvailabilityReason]  # ko'p vaqt olgani birinchi
    # --- OEE Performance (`services/performance.py`) — Prisadka (xnc formulasi) va Kromka (stansiya
    # o'lchovi, L / v + oraliq) ish markazlarida, qolganida 0 / None
    parts: int  # Prisadka: kuzatilgan ish vaqtida skanerlangan detallar; Kromka: o'lchangan o'tishlar
    ideal_s: int  # o'sha detallarning ideal sikl vaqti yig'indisi
    performance_pct: float | None  # ideal_s / run_s; 100 dan oshsa KESILMAYDI — koeffitsiyent yumshoqligi belgisi
    cycles: int  # Pico o'lchagan tugallangan sikllar (kalibrlash uchun)
    measured_cycle_s: int  # ularning wait_s + process_s yig'indisi — ideal_s bilan solishtiriladi
    # --- OEE Quality (`part_defect` — terminaldagi BRAK tugmasi). Brak kiritilmagan bo'lsa 100%
    defects: int  # kuzatilgan ish vaqtida brak deb belgilangan nusxalar
    quality_pct: float | None  # (detallar − brak) ÷ detallar; detal sanalmagan bo'lsa None
    oee_pct: float | None  # Availability × Performance × Quality; uchtasidan biri yo'q bo'lsa None


class MachineTimeDay(BaseModel):
    """Kunlik trek uchun: rangli chiziq (`seconds`) va o'sha kunning yakuni."""

    machine_id: int
    day: date  # Toshkent kuni
    # holat -> soniya: PROCESSING, AWAIT_PART, IDLE, STOPPED, FAULT, OFF — trek shundan chiziladi
    seconds: dict[str, int]
    planned_s: int
    run_s: int
    availability_pct: float | None
    parts: int
    defects: int
    quality_pct: float | None
    oee_pct: float | None


class MachineTimeReport(BaseModel):
    date_from: date
    date_to: date
    rows: list[MachineTimeRow]
    days: list[MachineTimeDay]
    schedule_set: bool  # ish jadvalida smena bormi — yo'q bo'lsa Availability hisoblanmaydi
    idle_threshold_min: int  # sariq chiroq shundan uzoq yonsa to'xtash (`stop_prompt_idle_minutes`)
    ideal_cycle: IdealCycle  # Prisadka Performance'i shu koeffitsiyentlar bilan hisoblangan
    ideal_cycle_kromka: IdealCycleKromka  # Kromkada sozlanadigani — detallar oralig'i
    #: OEE shu kundan hisoblanadi; undan oldingi kunlar hisobotdan tushirilgan (None — cheklov yo'q)
    oee_start: date | None


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
