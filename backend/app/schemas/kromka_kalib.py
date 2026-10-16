from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class KalibStart(BaseModel):
    machine_id: int
    #: Birinchi etalon uzunligi, mm (shtangensirkul bilan o'lchangan)
    L_ref: float = Field(gt=0, le=6000)


class KalibEtalon(BaseModel):
    L_ref: float = Field(gt=0, le=6000)


class KalibExclude(BaseModel):
    excluded: bool


class KalibSessionRow(BaseModel):
    id: int
    machine_id: int
    machine_name: str
    started_at: datetime
    ended_at: datetime | None
    #: `[{"L_ref": mm, "dan": iso}]`
    segments: list[dict[str, Any]]


class KalibPoint(BaseModel):
    event_id: int
    at: datetime
    L_ref: float
    S: int
    #: Pico'ning o'zi o'lchagan uzunlik va kodi — joriy kalibrlash bilan
    L_pico: float | None
    kod: str | None
    t1: float
    t2: float
    dtm: float
    #: Yangi (hisoblangan) kalibrlash bilan
    Lfit: float | None
    err: float | None
    #: 3σ dan chetda — hisob o'zi tashladi
    chet: bool
    #: admin qo'lda chetlatgan — hisobga umuman kirmaydi
    excluded: bool


class KalApplyRow(BaseModel):
    id: int
    session_id: int | None
    rollback_of_id: int | None
    values: dict[str, float]
    previous: dict[str, float]
    created_at: datetime
    sent_at: datetime | None
    confirmed_at: datetime | None
    #: `kutilmoqda` · `tasdiqlandi` · `javobsiz` (10 daqiqada Pico javob bermadi)
    status: str
    #: Agentga beriladigan aynan qator
    line: str


class KalibDetail(KalibSessionRow):
    points: list[KalibPoint]
    #: `services/kromka_kalib.hisobla` natijasi; nuqta bo'lmasa None
    result: dict[str, Any] | None
    #: Pico'dagi joriy KAL (oxirgi `kal` hodisasi) — solishtirish uchun
    current: dict[str, float]
    #: Shu stanokning oxirgi 10 qo'llashi (yangisi birinchi)
    applies: list[KalApplyRow]
