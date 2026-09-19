from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DefectStatus


class DefectCreate(BaseModel):
    """Brak: operator skanerlagan nusxani BRAK deb belgilaydi (terminal skan tasmasi).

    Nusxa emas, SKAN beriladi: tasmada aynan shu skan turibdi va uning ish markazi,
    posti hamda nusxasi allaqachon ma'lum — terminal QR ni qayta yubormaydi."""

    model_config = ConfigDict(str_strip_whitespace=True)

    scan_id: int
    #: Sabab Tizim sozlamalaridagi ro'yxatdan (`system_setting.defect_reasons`); matn
    #: bo'lib ko'chiriladi, ya'ni ro'yxat keyin o'zgarsa ham yozuv o'qiladi
    reason: str = Field(min_length=1, max_length=60)
    note: str = Field(default="", max_length=500)


class DefectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    instance_id: int
    reason: str
    note: str | None
    status: DefectStatus
    created_at: datetime


class DefectStep(BaseModel):
    """Detal marshrutining bitta qadami — menejer aybdorni va qayta boshlash nuqtasini
    SHU ro'yxatdan tanlaydi. Post emas, QADAM: bitta post marshrutda ikki marta uchrashi
    mumkin (Kromka → Prisadka → Kromka)."""

    route_id: int
    seq: int
    post_code: str
    post_name: str
    process_code: int
    #: Shu qadamda skanerlagan hodim (oxirgi bekor qilinmagan skan) — aybdor odatda shu
    employee_id: int | None
    employee_name: str | None


class DefectRow(BaseModel):
    """Brak sahifasining bitta qatori — menejer qaror qabul qilishi uchun yetarli kontekst."""

    id: int
    created_at: datetime
    status: DefectStatus
    reason: str
    note: str | None
    #: Detal ID (chek, QR va SCX bilan bitta satr)
    qr_text: str
    order_id: int
    order_number: str
    part_code: str
    part_name: str
    #: Brakni KIM va QAYERDA belgilagan
    post_name: str
    machine_name: str | None
    employee_name: str | None
    #: Marshrut qadamlari (tartib bilan) — tanlov ro'yxati
    steps: list[DefectStep]
    blame_route_id: int | None
    blame_employee_name: str | None
    restart_route_id: int | None
    reviewed_at: datetime | None
    reviewed_by: str | None


class DefectReview(BaseModel):
    """Menejer qarori. `rejected` — «brak emas»: Quality'ga kirmaydi.

    Tasdiqlashda `restart_route_id` MAJBURIY — «qayerdan qayta boshlanadi» degan savol
    qarorning o'zi; `blame_route_id` esa ixtiyoriy: material nuqsonida ayb hech kimda emas."""

    status: DefectStatus
    blame_route_id: int | None = None
    restart_route_id: int | None = None


class DefectPending(BaseModel):
    #: Sidebar belgisi uchun: menejer ko'rmagan braklar soni
    count: int
