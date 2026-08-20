from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CapacityUnit, MachineStatus


class MachineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    name: str
    capacity: float | None
    capacity_unit: CapacityUnit | None
    status: MachineStatus
    #: OEE — kunlik reja (daqiqa) va ideal tezlik. `ideal_rate` birligi POSTDAN
    #: keladi: ARRA sek/metr, KROMKA metr/daqiqa, PRISADKA sek/teshik.
    planned_minutes_per_day: int
    ideal_rate: float | None
    created_at: datetime


class MachineCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    post_id: int
    name: Annotated[str, Field(min_length=2, max_length=100, examples=["01 ARRA"])]
    capacity: float | None = Field(default=None, gt=0)
    capacity_unit: CapacityUnit | None = None
    status: MachineStatus = MachineStatus.ACTIVE
    planned_minutes_per_day: int = Field(default=480, ge=1, le=1440)
    ideal_rate: float | None = Field(default=None, gt=0)


class MachineUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    post_id: int | None = None
    name: Annotated[str | None, Field(min_length=2, max_length=100, default=None)]
    capacity: float | None = Field(default=None, gt=0)
    capacity_unit: CapacityUnit | None = None
    status: MachineStatus | None = None
    planned_minutes_per_day: int | None = Field(default=None, ge=1, le=1440)
    ideal_rate: float | None = Field(default=None, gt=0)
