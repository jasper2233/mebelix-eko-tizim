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


class MachineOverview(BaseModel):
    """Ish markazlari sahifasi uchun jonli holat — ro'yxat (`MachineRead`) o'zgarmaydi,
    u har select'da ishlatiladi; bu faqat sahifada, 60s poll bilan."""

    machine_id: int
    accounts: list[str]  # `user.machine_id` bilan biriktirilgan qurilma hisoblari
    agents: list[str]  # faol MES agentlari (skan-forvard / chek)
    agent_online: bool  # kamida bittasi 6 daqiqa ichida ko'ringan
    on_shift: int  # bugun ochilgan, hali yopilmagan smenalar (hodim soni)
    today_scans: int
    last_scan_at: datetime | None
    unfinished_routes: int  # shu markazga biriktirilgan, tugallanmagan qadamlar (faol buyurtmalar)


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
