from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
    created_at: datetime
