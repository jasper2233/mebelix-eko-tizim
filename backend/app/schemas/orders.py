from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import FileKind, OrderPriority, OrderStatus, PostCode, RouteSource


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
    created_at: datetime
    updated_at: datetime | None
    production_started_at: datetime | None
    completed_at: datetime | None
    delivered_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None


class MaterialUsageItem(BaseModel):
    """ingest.py material_usage yozuvi: GibLab fayldan avtomatik registr."""

    name: str
    code: str | None = None
    kind: str  # "sheet" | "band" | "hardware"
    count: float | None = None
    unit: str


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
    # GibLab fayldan avtomatik material registri: sheet (list), band (kromka, metr),
    # hardware (furnitura, dona). Furnituralar tabida ko'rsatiladi.
    material_usage: list[MaterialUsageItem] = []
    files: list[OrderFileRead] = []
    parts_count: int = 0
    instances_count: int = 0
    #: Buyurtmani hali tahrirlash mumkinmi (fayl qayta yuklash, matritsa, ish
    #: markazi). Ishlab chiqarishdagi buyurtma ham tahrirlanadi — TO birinchi
    #: skan qilinmaguncha. Frontend tugmalarni shunga qarab yoqadi.
    can_edit: bool = False
    #: Tahrirlab bo'lmasa — SABABI: "ARRA postida 12 ta skan (26-08 10:15)".
    #: Tugmani jimgina o'chirib qo'yish texnologni sababsiz qoldirardi.
    edit_blocked_reason: str | None = None
    #: Kim bekor qilgan — ISM, id emas: kartochkada "Bekor sababi" yonida turadi.
    #: Ilgari `cancelled_by_id` yozilardi-yu, hech qayerda o'qilmasdi: foydalanuvchi
    #: sababni ko'rar, kimligini esa faqat audit logdan qidirishga to'g'ri kelardi.
    cancelled_by_name: str | None = None


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


# --- Mijoz anketasi (menejer to'ldiradigan qog'oz forma o'rniga) ---
# Variantlar kodlari (ldsp, mdf, akril...) frontend/src/lib/anketa.ts da matnga aylantiriladi —
# bu yerda ro'yxat qat'iy emas: yangi variant qo'shilganda migratsiya kerak bo'lmasin.
# Mijoz ma'lumotlari Client'da, narx/avans/muddat Order'da — anketada takrorlanmaydi.


# Anketa tashqi kirish — chegaralar shu yerda, aks holda bitta so'rov bazani to'ldirib yuboradi
_Mm = Annotated[float | None, Field(ge=0, le=50_000)]


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
    count: Annotated[int | None, Field(ge=1, le=999)] = None
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
    shape: Annotated[str | None, Field(max_length=20)] = None
    room_length: _Mm = None
    room_width: _Mm = None
    room_height: _Mm = None
    furniture_wall_length: _Mm = None

    # 4. Korpus
    corpus_materials: Annotated[list[str], Field(max_length=10)] = []
    corpus_color: Annotated[str, Field(max_length=120)] = ""
    corpus_thickness: Annotated[str | None, Field(max_length=20)] = None
    corpus_note: Annotated[str, Field(max_length=300)] = ""

    # 5. Fasad
    facade_materials: Annotated[list[str], Field(max_length=10)] = []
    facade_color: Annotated[str, Field(max_length=120)] = ""
    countertop: Annotated[str | None, Field(max_length=20)] = None
    facade_note: Annotated[str, Field(max_length=300)] = ""

    # 6. Furnitura va qo'shimcha xizmatlar
    hardware_level: Annotated[str | None, Field(max_length=20)] = None
    extra_services: Annotated[list[str], Field(max_length=10)] = []

    # 7. Izoh
    note: Annotated[str, Field(max_length=1000)] = ""

    # O'lchov varag'i (zamerdan keyin to'ldiriladi)
    walls: Annotated[list[SurveyWall], Field(max_length=8)] = []
    modules: Annotated[list[SurveyModule], Field(max_length=40)] = []
    total_running_meters: Annotated[float | None, Field(ge=0, le=1000)] = None  # pm
    total_height: _Mm = None


class OrderSurvey(BaseModel):
    """Buyurtma anketasi: bitta yoki bir nechta xona."""

    model_config = ConfigDict(extra="ignore")

    version: int = 1
    measured_at: date | None = None  # o'lchov sanasi
    measured_by: Annotated[str, Field(max_length=120)] = ""  # o'lchagan usta
    # Tsex va logistika BUYURTMA ustida ishlaydi — xona degan tushuncha ularga
    # yetib bormaydi (bitta .project fayl butun buyurtmaga yuklanadi). Shuning
    # uchun quyidagilar room ichida emas, shu yerda. Migratsiya kerak emas:
    # survey — JSONB. Diqqat: default False FAQAT yozishda (bu sxema orqali
    # validatsiyada) qo'llanadi — o'qishda `OrderDetail.survey` xom dict qaytadi,
    # ya'ni eski yozuvda bu kalitlar javobda umuman bo'lmaydi.
    packaging: bool = False  # tayyor mahsulot yetkazishdan oldin qadoqlanadimi
    delivery: bool = False  # bitta mashina, bitta manzil — xonaga bo'linmaydi
    installation: bool = False  # bitta brigada, bitta tashrif
    rooms: Annotated[list[SurveyRoom], Field(max_length=10)] = []


class MachineAssignments(BaseModel):
    """Manager's machine choice per post before production start (TZ 6.4)."""

    assignments: dict[PostCode, int]


class RouteCell(BaseModel):
    """One matrix cell: part × post (TZ 6.3.3)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    seq: int  # marshrutdagi o'rni, 1 dan
    process_code: int  # 1..16 (15/16 — marshrut dumi, TAIL_CODES); STOLYARKA da 6 xil bor
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
    edges: dict[str, Any]
    note: str | None
    is_custom: bool
    #: Bu detal biriktirilgan ASOSIY detal (stolyarkada yaxlit buyumga aylanadi).
    assembly_parent_id: int | None = None
    #: Bunga biriktirilgan mayda detallar: [{"part_id", "code", "count"}] — UI ro'yxati.
    assembly_children: list[dict[str, Any]] = []
    routes: list[RouteCell]


class OrderMatrix(BaseModel):
    order_id: int
    parts: list[MatrixPart]


class MatrixPartEdit(BaseModel):
    """Texnolog edits one part's row (TZ 6.3.3): stages, note, count, custom route, assembly link."""

    part_id: int
    note: str | None = None
    count: int | None = Field(default=None, ge=1, le=1000)
    # post_id -> enabled; STOLYARKA toggling and disabling auto-detected stages
    stages: dict[int, bool] = {}
    #: Nostandart bayrog'i. `True` qilinsa fayldan kelgan avtomatik marshrut o'chadi va
    #: texnolog `route_codes` bilan o'zi chizadi; `False` qilinsa qo'lda chizilgani o'chib,
    #: fayl bo'yicha standart marshrut tiklanadi.
    is_custom: bool | None = None
    #: Nostandart detal marshruti — jarayon kodlari TARTIB bilan (masalan [7, 11, 8]).
    #: Kod takrorlanishi mumkin ([3, 6, 3]). Bo'sh ro'yxat marshrutni tozalaydi.
    route_codes: list[int] | None = None
    #: Yig'ma buyum: bu detal qaysi ASOSIY detalga biriktiriladi. `None` yuborilsa
    #: bog'lam uziladi. Maydon umuman yuborilmasa tegilmaydi (`model_fields_set`).
    assembly_parent_id: int | None = None


class MatrixEdit(BaseModel):
    edits: list[MatrixPartEdit]
