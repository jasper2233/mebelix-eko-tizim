"""«Tizim holati» sahifasi — `GET /system/perf` javobi (`core/perf.py` o'lchovlaridan)."""

from datetime import datetime

from pydantic import BaseModel


class EndpointStat(BaseModel):
    method: str
    route: str
    count: int
    p50_ms: float
    p95_ms: float
    max_ms: float
    #: Oynadagi jami server vaqti — qaysi endpoint resursni ko'proq yeyishini shu aytadi
    total_s: float
    #: 5xx javoblar soni
    errors: int


class InflightRequest(BaseModel):
    path: str
    elapsed_ms: int


class LagIncident(BaseModel):
    """Ishchining event loop'i bloklangan payt: shu vaqt ichida o'sha ishchidagi HAMMA so'rov kutgan."""

    at: datetime
    lag_ms: int
    pid: int
    #: O'sha paytda ishlab turgan so'rovlar, eng uzoq davom etayotgani birinchi — aybdor odatda shu
    inflight: list[InflightRequest]


class PrintStat(BaseModel):
    """Chek job'i navbatga qo'yilgandan agent qabul qilguncha (tugma bosilishidan ~40 ms keyin boshlanadi)."""

    count: int
    p50_s: float | None
    p95_s: float | None
    max_s: float | None


class DbStatement(BaseModel):
    calls: int
    total_ms: float
    mean_ms: float
    rows: int
    query: str


class SystemPerf(BaseModel):
    minutes: int
    requests: int
    endpoints: list[EndpointStat]
    lag_incidents: list[LagIncident]
    labels: PrintStat
    #: `pg_stat_statements` yuklanmagan bo'lsa False (lokal Postgres sozlanmagan bo'lishi mumkin)
    db_available: bool
    #: Statistika qachondan beri yig'ilyapti (baza qayta ishga tushganda nollanadi)
    db_since: datetime | None
    db_top: list[DbStatement]
