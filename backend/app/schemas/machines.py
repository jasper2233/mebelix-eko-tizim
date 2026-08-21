from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MachineStatus


class MachineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    name: str
    status: MachineStatus
    created_at: datetime


class MachineCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    post_id: int
    name: Annotated[str, Field(min_length=2, max_length=100, examples=["01 ARRA"])]
    status: MachineStatus = MachineStatus.ACTIVE


class MachineUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    post_id: int | None = None
    name: Annotated[str | None, Field(min_length=2, max_length=100, default=None)]
    status: MachineStatus | None = None
