from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EmployeeStatus

from .users import PHONE_PATTERN

_PHONE = Field(pattern=PHONE_PATTERN, examples=["+998901234567"], default=None)


class EmployeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    badge_id: str
    phone: str | None
    position: str | None
    status: EmployeeStatus
    assigned_post_ids: list[int]
    #: PIN o'rnatilganmi. Hash HECH QACHON chiqmaydi.
    has_pin: bool
    created_at: datetime


class EmployeeCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: Annotated[str, Field(min_length=2, max_length=100)]
    phone: Annotated[str | None, _PHONE]
    position: str | None = Field(default=None, max_length=50)
    status: EmployeeStatus = EmployeeStatus.ACTIVE
    assigned_post_ids: list[int] = []
    # badge_id is server-generated (UUID) — never client-supplied


class EmployeeUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: Annotated[str | None, Field(min_length=2, max_length=100, default=None)]
    phone: Annotated[str | None, _PHONE]
    position: str | None = Field(default=None, max_length=50)
    status: EmployeeStatus | None = None
    assigned_post_ids: list[int] | None = None


class EmployeePinUpdate(BaseModel):
    """PIN o'rnatish yoki o'chirish (`null` — o'chiradi).

    QAT'IY 4 raqam: monoblokda oxirgi raqam terilishi bilan kirish boshlanadi,
    ya'ni "tasdiqlash" tugmasi kerak emas — uzunlik o'zgaruvchan bo'lsa qachon
    tugaganini bilib bo'lmasdi. Kuchni uzunlik emas, urinishlar chegarasi beradi
    (5 xato — 5 daqiqa blok, `login.py`).
    """

    pin: Annotated[str | None, Field(default=None, min_length=4, max_length=4, pattern=r"^\d{4}$")]
