"""Brak sxemalari — terminalda belgilash, menejerda tasdiqlash."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DefectStatus


class DefectCreate(BaseModel):
    """Terminalda belgilash. Nusxa QR bo'yicha topiladi — operator qo'lida
    aynan chek bor, ID emas."""

    qr_text: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=3, max_length=200)


class DefectScanRow(BaseModel):
    """Nusxaning skan tarixi — menejer AYBDORNI shundan aniqlaydi."""

    post_name: str
    employee_name: str | None
    machine_name: str | None
    at: datetime


class DefectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: DefectStatus
    reason: str
    created_at: datetime
    order_number: str
    part_name: str
    qr_text: str
    found_post_name: str
    found_by_name: str | None
    #: Marshrut — nostandart detalda ketma-ketlik ko'rinib tursin
    route: list[str] = []
    #: Nusxaning skan tarixi (kim, qayerda, qachon)
    history: list[DefectScanRow] = []
    #: Taklif — oxirgi skandan; menejer o'zgartirishi mumkin
    suggested_post_id: int | None = None
    suggested_employee_id: int | None = None
    blamed_post_name: str | None = None
    blamed_employee_name: str | None = None
    restart_post_name: str | None = None
    new_qr_text: str | None = None
    reviewed_at: datetime | None = None


class DefectApprove(BaseModel):
    blamed_post_id: int
    blamed_employee_id: int | None = None
    restart_post_id: int
