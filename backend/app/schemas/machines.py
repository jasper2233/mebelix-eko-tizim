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
    unfinished_routes: int  # shu markazga BIRIKTIRILGAN, tugallanmagan qadamlar — o'chirish to'sig'i (`_blockers`)
    # Terminal navbati bilan bir xil qoida: biriktirilgan + postning biriktirilmagan
    # ishi, QOLGAN SKAN bilan (boshqaruv paneli «navbatda» bilan bir birlik).
    # ponytail: bir postda 2+ faol markaz bo'lsa biriktirilmagan ish ikkalasida ko'rinadi —
    # terminalda ham shunday, kim oldin skan qilsa o'shaniki.
    queue_scans: int
    # Stanok signal ustuni (andon: Pico + MES agent) — jonli holat: PROCESSING, AWAIT_PART,
    # IDLE, STOPPED, FAULT, OFF. None — andon ulanmagan yoki 90 soniyadan beri xabar yo'q.
    andon_state: str | None = None
    andon_since: datetime | None = None  # joriy holat qachondan beri


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
