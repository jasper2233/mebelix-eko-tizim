from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import MachineStatus
from app.schemas.users import validate_password_strength


class MachineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    name: str
    status: MachineStatus
    created_at: datetime
    #: Shu ish markazining MONOBLOK hisobi (rol `terminal`) logini — yo'q bo'lsa
    #: None. Terminal ekrani qaysi mashinani ochishini AYNAN shu hisob hal
    #: qiladi; usiz post o'zining eng kichik id'li mashinasiga qulflanadi.
    terminal_username: str | None = None


class TerminalAccountUpsert(BaseModel):
    """Ish markazining monoblok hisobi: yaratish yoki parolni yangilash."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    username: Annotated[str, Field(min_length=3, max_length=50, examples=["arra-1"])]
    password: str

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return validate_password_strength(v)


class MachineCreate(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    post_id: int
    name: Annotated[str, Field(min_length=2, max_length=100, examples=["01 ARRA"])]
    status: MachineStatus = MachineStatus.ACTIVE


class MachineUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    post_id: int | None = None
    name: Annotated[str | None, Field(min_length=2, max_length=100, default=None)]
    status: MachineStatus | None = None
