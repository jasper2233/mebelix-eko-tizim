from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import EmployeeStatus
from app.schemas.users import validate_phone

_PHONE = Field(examples=["+998901234567"], default=None)


class EmployeeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    #: Beyjik RAQAMI ataylab BERILMAYDI: u tsexdagi yagona kirish kaliti (login.py
    #: `/login/badge`). Ilgari ro'yxat javobida ochiq matnda ketardi va ekrandagi QR
    #: ni suratga olgan odam boshqa hodim nomidan smena ocha olardi. Chop etish
    #: serverda (`POST /{id}/print`), yorliqni bevosita printer oladi.
    user_id: int | None
    phone: str | None
    position: str | None
    status: EmployeeStatus
    assigned_post_ids: list[int]
    created_at: datetime


class EmployeeCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: Annotated[str, Field(min_length=2, max_length=100)]
    phone: Annotated[str | None, _PHONE]
    position: str | None = Field(default=None, max_length=50)
    status: EmployeeStatus = EmployeeStatus.ACTIVE
    assigned_post_ids: list[int] = []
    #: Kirish hisobi (ofis xodimida parol bilan kirish). Bo'sh — tsexda faqat beyjik
    user_id: int | None = None
    # badge_id is server-generated (UUID) — never client-supplied

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str | None) -> str | None:
        return validate_phone(v)


class EmployeeUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: Annotated[str | None, Field(min_length=2, max_length=100, default=None)]
    phone: Annotated[str | None, _PHONE]
    position: str | None = Field(default=None, max_length=50)
    status: EmployeeStatus | None = None
    user_id: int | None = None
    assigned_post_ids: list[int] | None = None

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str | None) -> str | None:
        return validate_phone(v)
