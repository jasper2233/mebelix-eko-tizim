from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CapacityUnit, MachineStatus


class MachineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    name: str
    ip_address: str | None
    capacity: float | None
    capacity_unit: CapacityUnit | None
    status: MachineStatus
    created_at: datetime


class MachineCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    post_id: int
    name: Annotated[str, Field(min_length=2, max_length=100, examples=["01 ARRA STANOGI"])]
    ip_address: str | None = Field(default=None, max_length=45)
    capacity: float | None = Field(default=None, gt=0)
    capacity_unit: CapacityUnit | None = None
    status: MachineStatus = MachineStatus.ACTIVE


class MachineUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    post_id: int | None = None
    name: Annotated[str | None, Field(min_length=2, max_length=100, default=None)]
    ip_address: str | None = Field(default=None, max_length=45)
    capacity: float | None = Field(default=None, gt=0)
    capacity_unit: CapacityUnit | None = None
    status: MachineStatus | None = None
