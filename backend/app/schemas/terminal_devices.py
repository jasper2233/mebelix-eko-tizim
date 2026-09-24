from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field


class TerminalDeviceRead(BaseModel):
    """Admin ro'yxati. pair_code faqat hali ulanmagan qurilmada — ro'yxat admin-only."""

    id: int
    name: str
    machine_id: int
    machine_name: str | None = None
    paired: bool
    pair_code: str | None
    pair_expires_at: datetime | None
    last_seen_at: datetime | None
    #: Kod kiritilgan payt va brauzer (User-Agent) — admin qurilma turini ko'radi
    paired_at: datetime | None = None
    paired_user_agent: str | None = None
    created_at: datetime


class TerminalDeviceCreate(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=100, examples=["Arra monobloki"])]
    #: MAJBURIY: qurilma aynan shu ish markazining chekini chiqaradi
    machine_id: int


class TerminalDevicePairRequest(BaseModel):
    code: Annotated[str, Field(min_length=4, max_length=16)]


class TerminalDevicePairResponse(BaseModel):
    """Token javobda YO'Q — u faqat httpOnly cookie'da, sahifa skripti uni ko'rmaydi."""

    name: str
    machine_name: str
