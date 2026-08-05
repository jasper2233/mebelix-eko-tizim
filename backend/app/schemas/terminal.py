from datetime import date, datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OrderPriority, PostCode, SessionStatus


class BadgeStart(BaseModel):
    badge_id: Annotated[str, Field(min_length=8, max_length=36)]


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    employee_name: str = ""
    machine_id: int | None
    post_id: int
    status: SessionStatus
    created_at: datetime
    ended_at: datetime | None


class TerminalContext(BaseModel):
    machine_id: int
    machine_name: str
    post_id: int
    post_code: PostCode
    post_name: str
    session: SessionRead | None = None


class TaskRow(BaseModel):
    """One aggregated row in NAVBATDAGI VAZIFALAR (TZ 8.3.2)."""

    part_id: int
    order_id: int
    order_number: str
    deadline: date | None
    code: str  # productCode_partCode
    name: str
    length: float | None
    width: float | None
    thickness: float | None
    qoldiq: int  # remaining scans at this post
    total: int
    edges: dict[str, Any] = {}


class TerminalOrderCard(BaseModel):
    """Terminal proyekt tanlagichi kartasi (/terminal/orders): done/total post turiga moslangan."""

    id: int
    number: str
    project_name: str | None
    deadline: date | None
    priority: OrderPriority
    done: int
    total: int
    materials: list[str] = []  # karta uchun: arrachi plita bo'yicha partiyalab kesadi
    sheets_total: int
    has_cutmap: bool


class QrOrderRef(BaseModel):
    """QR qaysi aktiv buyurtmaga tegishli (/terminal/qr/{qr}/order) — terminal o'sha sahifani ochadi."""

    order_id: int
    order_number: str


class KromkaInstance(BaseModel):
    """Bitta fizik nusxa KROMKA nazarida: nechta tomoni yopishtirilgan, arradan o'tganmi."""

    instance_id: int
    instance_no: int
    qr_text: str
    done: int  # shu nusxada bajarilgan kromka skanlari (tomonlar)
    arra_passed: bool  # chek chiqarilgan yoki ARRA skan bor — kesilgan hisoblanadi


class KromkaPartRow(BaseModel):
    part_id: int
    code: str  # productCode_partCode
    name: str
    length: float | None
    width: float | None
    thickness: float | None
    sides: int  # har nusxa uchun kerakli skanlar = kromkalanadigan tomonlar
    edges: dict[str, Any] = {}
    total_done: int
    total_required: int
    instances: list[KromkaInstance] = []


class KromkaOrderState(BaseModel):
    """KROMKA post sahifasi (proyekt ochilganda): faqat kromkali detallar."""

    order_id: int
    order_number: str
    parts: list[KromkaPartRow]


class PrisadkaFile(BaseModel):
    """Detalning SCX fayli — stanok kompyuteriga yuklab olish uchun (TZ 12.5)."""

    id: int
    filename: str


class PrisadkaInstance(BaseModel):
    """Nusxa darajasi: QR chiqarish tugmasi va holat uchun."""

    instance_id: int
    qr_text: str
    label_printed: bool
    done: bool


class PrisadkaPartRow(BaseModel):
    part_id: int
    code: str  # productCode_partCode
    name: str
    length: float | None
    width: float | None
    thickness: float | None
    done: int
    total: int
    files: list[PrisadkaFile] = []
    arra_route: bool  # marshrutida ARRA bormi — bo'lmasa QR chek shu sahifadan chiqadi (ROVER)
    done_qrs: list[str] = []  # skan tugagan nusxalar QR'lari (fayl nomi bilan mos) — UI rang beradi
    instances: list[PrisadkaInstance] = []


class PrisadkaOrderState(BaseModel):
    """CNC post sahifasi (PRISADKA/ROVER): shu postga tegishli detallar + SCX fayllari."""

    order_id: int
    order_number: str
    project_name: str | None
    parts: list[PrisadkaPartRow]


class ScanRequest(BaseModel):
    qr_text: Annotated[str, Field(min_length=3, max_length=120)]
    client_event_id: Annotated[str, Field(min_length=8, max_length=64)]  # client UUID (TZ 8.4.4)


class ScanResult(BaseModel):
    scan_id: int
    duplicate: bool = False  # idempotent replay — already counted, not an error
    qr_text: str
    part_code: str
    part_name: str
    instance_no: int
    qoldiq: int  # remaining for this part at this post after the scan
    scx_file_ids: list[int] = []  # served on EVERY scan for CNC posts (TZ 12.5)
    # Avto-SCX proyekt nomli papkaga tushishi uchun (downloadScx subpapka nomi)
    project_name: str | None = None
    order_stage_completed: bool = False
    order_completed: bool = False


class ScanHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    qr_text: str = ""
    part_code: str = ""
    is_cancelled: bool
    created_at: datetime


class CutmapInstanceState(BaseModel):
    instance_id: int
    instance_no: int
    qr_text: str
    pattern_no: int | None
    cell_index: int | None
    done: bool
    label_printed_at: datetime | None


class CutmapState(BaseModel):
    """ARRA cut-map screen payload (TZ 7.1.7): the visual model + live per-cell state."""

    order_id: int
    order_number: str
    model: dict[str, Any] | None
    instances: list[CutmapInstanceState]
