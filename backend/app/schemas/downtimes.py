from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DowntimeKind

ReasonName = Annotated[str, Field(min_length=1, max_length=60)]


class DowntimeReasonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_planned: bool
    needs_note: bool
    order_index: int
    is_active: bool


class DowntimeReasonCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: ReasonName
    is_planned: bool = False
    needs_note: bool = False


class DowntimeReasonUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: ReasonName | None = None
    is_planned: bool | None = None
    needs_note: bool | None = None
    order_index: int | None = None
    #: O'chirish yo'q — eski to'xtashlar sababini yo'qotmasin; nofaol sabab terminalda chiqmaydi
    is_active: bool | None = None


class DowntimeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: DowntimeKind
    started_at: datetime
    #: `None` — to'xtash davom etmoqda
    ended_at: datetime | None
    reason_id: int | None


class DowntimeReasonInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reason_id: int
    note: str = Field(default="", max_length=500)
