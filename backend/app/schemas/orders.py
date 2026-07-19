from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FileKind, OrderPriority, OrderStatus, PostCode, ProjectGeneration, RouteSource


class OrderRead(BaseModel):
    """Registry row (TZ 10.3.1)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    status: OrderStatus
    priority: OrderPriority
    client_id: int
    client_name: str = ""  # joined in the route
    deadline: date | None
    amount: Decimal | None
    advance_payment: Decimal | None
    notes: str | None
    project_name: str | None
    project_generation: ProjectGeneration | None
    created_at: datetime
    updated_at: datetime | None
    production_started_at: datetime | None
    completed_at: datetime | None
    delivered_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None


class OrderFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: FileKind
    filename: str
    size: int | None
    part_id: int | None
    meta: dict[str, Any] = {}  # anketa rasmi uchun {"room_id": ..., "content_type": ...}
    created_at: datetime


class OrderDetail(OrderRead):
    """Order card (TZ 10.3.3): metadata + files; the parts matrix comes from /matrix."""

    machine_assignments: dict[str, int]
    project_uuid: str | None
    project_loaded_at: datetime | None
    survey: dict[str, Any] | None = None  # mijoz anketasi (OrderSurvey), texnolog o'qiydi
    files: list[OrderFileRead] = []
    parts_count: int = 0
    instances_count: int = 0


class OrderCreate(BaseModel):
    """Manager creates a DRAFT order (TZ 6.2). The number is auto-generated (B-2026-001)."""

    model_config = ConfigDict(extra="ignore")

    client_id: int
    deadline: date | None = None
    priority: OrderPriority = OrderPriority.MEDIUM
    amount: Decimal | None = Field(default=None, ge=0)
    advance_payment: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class OrderUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    client_id: int | None = None
    deadline: date | None = None
    priority: OrderPriority | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    advance_payment: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class OrderCancel(BaseModel):
    reason: Annotated[str, Field(min_length=3, max_length=500)]


# --- Mijoz anketasi (qog'oz forma o'rniga, uploads/forma/mebel_buyurtma_anketa.html) ---
# Variantlar kodlari (ldsp, mdf, akril...) frontend/src/lib/anketa.ts da matnga aylantiriladi —
# bu yerda ro'yxat qat'iy emas: yangi variant qo'shilganda migratsiya kerak bo'lmasin.
# Mijoz ma'lumotlari Client'da, narx/avans/muddat Order'da — anketada takrorlanmaydi.


# Anketa tashqi kirish — chegaralar shu yerda, aks holda bitta so'rov bazani to'ldirib yuboradi
_Mm = Annotated[float | None, Field(default=None, ge=0, le=50_000)]


class SurveyWall(BaseModel):
    """O'lchov varag'i A bo'limi: bitta devor (A..E)."""

    letter: Annotated[str, Field(max_length=2)] = ""
    length: _Mm = None
    height: _Mm = None


class SurveyModule(BaseModel):
    """O'lchov varag'i B bo'limi: yasaladigan moduldan bitta qator."""

    name: Annotated[str, Field(max_length=120)] = ""
    wall: Annotated[str, Field(max_length=2)] = ""
    width: _Mm = None  # eni
    depth: _Mm = None  # chuqurlik
    height: _Mm = None  # balandlik
    count: Annotated[int | None, Field(default=None, ge=1, le=999)] = None
    note: Annotated[str, Field(max_length=200)] = ""


class SurveyRoom(BaseModel):
    """Bitta xona uchun anketa — menejer har xonaga alohida to'ldiradi."""

    model_config = ConfigDict(extra="ignore")

    id: Annotated[str, Field(max_length=40)]  # frontend beradigan barqaror kalit
    name: Annotated[str, Field(max_length=60)] = ""  # "Oshxona", "Yotoqxona 1"

    # 2. Qanday mebel kerak
    furniture_types: Annotated[list[str], Field(max_length=20)] = []
    furniture_other: Annotated[str, Field(max_length=120)] = ""

    # 3. Shakl va xona o'lchamlari (mm)
    shape: Annotated[str | None, Field(default=None, max_length=20)] = None
    room_length: _Mm = None
    room_width: _Mm = None
    room_height: _Mm = None
    furniture_wall_length: _Mm = None

    # 4. Korpus
    corpus_materials: Annotated[list[str], Field(max_length=10)] = []
    corpus_color: Annotated[str, Field(max_length=120)] = ""
    corpus_thickness: Annotated[str | None, Field(default=None, max_length=20)] = None
    corpus_note: Annotated[str, Field(max_length=300)] = ""

    # 5. Fasad
    facade_materials: Annotated[list[str], Field(max_length=10)] = []
    facade_color: Annotated[str, Field(max_length=120)] = ""
    countertop: Annotated[str | None, Field(default=None, max_length=20)] = None
    facade_note: Annotated[str, Field(max_length=300)] = ""

    # 6-7. Furnitura va qo'shimcha xizmatlar
    hardware_level: Annotated[str | None, Field(default=None, max_length=20)] = None
    extra_services: Annotated[list[str], Field(max_length=10)] = []

    # 8. Izoh
    note: Annotated[str, Field(max_length=1000)] = ""

    # O'lchov varag'i (zamerdan keyin to'ldiriladi)
    walls: Annotated[list[SurveyWall], Field(max_length=8)] = []
    modules: Annotated[list[SurveyModule], Field(max_length=40)] = []
    total_running_meters: Annotated[float | None, Field(default=None, ge=0, le=1000)] = None  # pm
    total_height: _Mm = None


class OrderSurvey(BaseModel):
    """Buyurtma anketasi: bitta yoki bir nechta xona."""

    model_config = ConfigDict(extra="ignore")

    version: int = 1
    measured_at: date | None = None  # o'lchov sanasi
    measured_by: Annotated[str, Field(max_length=120)] = ""  # o'lchagan usta
    rooms: Annotated[list[SurveyRoom], Field(max_length=10)] = []


class MachineAssignments(BaseModel):
    """Manager's machine choice per post before production start (TZ 6.4)."""

    assignments: dict[PostCode, int]


class RouteCell(BaseModel):
    """One matrix cell: part × post (TZ 6.3.3)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    source: RouteSource
    is_enabled: bool
    per_instance: int
    total_required: int
    total_done: int
    machine_id: int | None


class MatrixPart(BaseModel):
    """One matrix row: part with its route cells."""

    id: int
    product_code: str
    code: str
    name: str
    count: int
    length: float | None
    width: float | None
    thickness: float | None
    label_num: int | None
    edges: dict[str, Any]
    xnc_summary: dict[str, Any]
    note: str | None
    routes: list[RouteCell]


class OrderMatrix(BaseModel):
    order_id: int
    parts: list[MatrixPart]


class MatrixPartEdit(BaseModel):
    """Texnolog edits one part's row (TZ 6.3.3): toggle stages, note, rare count fix."""

    part_id: int
    note: str | None = None
    count: int | None = Field(default=None, ge=1, le=1000)
    # post_id -> enabled; STOLYARKA toggling and disabling auto-detected stages
    stages: dict[int, bool] = {}


class MatrixEdit(BaseModel):
    edits: list[MatrixPartEdit]
