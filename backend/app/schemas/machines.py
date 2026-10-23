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


class KromkaKalRow(BaseModel):
    """KROMKA stansiyasi Pico'sidagi JORIY kalibrlash (`main.py: KAL`) — agent `HOLAT` javobidan
    o'zgarganda yuboradi (agent 1.11.0+). Qo'llash — `/kromka-kalib/{id}/apply` (docs/12 §4.20).
    Agent hali yubormagan stanokda `at` va `values` bo'sh."""

    machine_id: int
    machine_name: str
    #: Pico qiymatlarni qachon aytgan (oxirgi o'zgarish yoki yangi ulanish)
    at: datetime | None
    #: D, V10, V18, K1, K2, B1, B2, C, TD, AO, HQ, HA, AV — Pico'dagi aynan qiymatlar
    values: dict[str, float]
    #: proshivka versiyasi (`HOLAT.ver`)
    ver: str | None
    #: avariya lampasi hozir miltillayaptimi (`HOLAT.alarm`)
    alarm: int | None
    #: `holat` — davriy so'rovdan, `set` — `SET` javobidan
    manba: str | None


class KromkaMeasurementRow(BaseModel):
    """Kromka stansiyasi o'lchagan bitta detal — admin panelidagi JONLI oqim uchun.

    Terminaldagi `KromkaMeasurement` bilan bir xil maydonlar, ustiga ish markazi:
    admin bir nechta stanokni bitta ro'yxatda ko'radi."""

    machine_id: int
    machine_name: str
    at: datetime
    length_mm: float | None
    #: OK — ikkala datchik mos; FARQ — chegaradan oshdi; FAQAT1/FAQAT2 — bitta datchik ko'rmagan
    code: str
    #: mos · ortiqcha · nomos · shubhali · skanersiz (`models/enums.py: KromkaVerdict`)
    verdict: str
    expected_mm: float | None
    delta_mm: float | None
    part_name: str | None
    qr_text: str | None
    scan_id: int | None
    #: Paket bo'lsa — unda nechta bo'lak o'tgani (kichik detallar birga tiqiladi, docs/12
    #: §4.26). Bo'sh bo'lmasa `length_mm` PAKETNING uzunligi, bu detalning emas.
    pack_n: int | None = None


class MachineActivityRow(BaseModel):
    """Ish markazida bo'lgan bitta amal — JONLI oqim uchun bitta qator.

    Hozircha faqat skan: «nima o'tdi va qaysi buyurtmadan». KROMKA'da ustiga o'lchov
    oqimi ham turadi (`KromkaMeasurementRow`) — u detalning mos/nomosligini aytadi,
    bu esa har postda bir xil: detal shu markazdan O'TDI."""

    scan_id: int
    at: datetime
    qr_text: str
    #: Nusxa raqamisiz detal kodi (`services/scanning.py: qr_part_code`)
    part_code: str
    part_name: str | None
    order_id: int
    order_number: str
    #: Skanni kim qildi (beyjik egasi); ARRA'da chek chiqarish skanida ham shu
    employee: str | None
    #: Bekor qilingan skan ro'yxatdan chiqmaydi — nima bo'lgani ko'rinib tursin
    cancelled: bool = False


class MachineActivity(BaseModel):
    """«Hozir nima qilyapti» — ish markazining o'z sahifasi uchun.

    Joriy ish OXIRGI SKANdan olinadi: tsexda odam detalni skanerlagan zahoti ish
    boshlanadi, alohida «ishni boshlash» tugmasi yo'q (docs/08). Smenada turganlar
    esa ochiq `work_session` dan."""

    #: Hozir smenada turgan hodimlar (ochiq smena)
    employees: list[str]
    #: Oxirgi skanning buyurtmasi — shu markaz hozir shu buyurtma ustida
    order_id: int | None = None
    order_number: str | None = None
    #: Shu buyurtmaning SHU POSTdagi qolgan skani (butun buyurtma bo'yicha)
    order_remaining: int | None = None
    #: Oxirgi amallar, yangisi birinchi
    rows: list[MachineActivityRow]
