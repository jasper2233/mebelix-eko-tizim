"""«Tizim holati» — `GET /system/*` javoblari (`core/perf.py` o'lchovlari, tahlil `services/system_health.py`)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Level = Literal["ok", "warn", "bad", "nodata"]


class Thresholds(BaseModel):
    """Rang chegaralari — backend topilmalari ham, sahifa jadvalini bo'yash ham shulardan."""

    p95_warn_ms: float
    p95_bad_ms: float
    p50_warn_ms: float
    p50_bad_ms: float
    lag_bad_ms: int
    lag_warn_count: int
    label_warn_s: float
    label_bad_s: float
    min_count: int
    #: Navbatdagi eng eski chek shuncha soniya tursa — agent olmayapti
    queue_stuck_s: float


class Finding(BaseModel):
    """Bitta topilma — tayyor jumla. `route` berilsa sahifa uni endpoint tafsilotiga bog'laydi."""

    level: Literal["warn", "bad"]
    text: str
    method: str | None = None
    route: str | None = None


class EndpointStat(BaseModel):
    method: str
    route: str
    count: int
    p50_ms: float
    p95_ms: float
    max_ms: float
    #: So'rovlar davomiyligi yig'indisi — qaysi endpointda eng ko'p kutilganini aytadi.
    #: CPU vaqti EMAS: bazani kutish va boshqa so'rov muzlatgan payt ham shunga kiradi.
    total_s: float
    #: 5xx javoblar soni
    errors: int


class InflightRequest(BaseModel):
    path: str
    elapsed_ms: int


class LagIncident(BaseModel):
    """Ishchining event loop'i kech uyg'ongan payt (bitta uzun ish yoki ketma-ket qisqa ishlar): shu vaqt
    ichida o'sha ishchidagi so'rovlar navbatda turgan."""

    at: datetime
    lag_ms: int
    pid: int
    #: O'sha paytda ishlab turgan (yoki shu orada tugagan) so'rovlar — "METOD /shablon", eng uzoq
    #: ishlayotgani birinchi, ko'pi bilan 8 ta (`perf.lag_monitor`)
    inflight: list[InflightRequest]
    #: Shundan Python GC yig'imlari (±50 ms); `None` — yozuv bu o'lchovdan oldingi
    gc_ms: int | None = None


class PrintStat(BaseModel):
    """Chek: POST uni arq navbatiga qo'ygandan agent qabul qilguncha — worker chizishi va agent
    navbati kiradi, qog'ozga chiqishi kirmaydi."""

    count: int
    p50_s: float | None
    p95_s: float | None
    max_s: float | None


class QueueStat(BaseModel):
    """Agentning chek navbati hozir: nechta kutyapti, eng eskisi necha soniyadan beri."""

    agent_id: int
    name: str
    machine_name: str | None
    last_seen_at: datetime | None
    pending: int
    #: Eng eski job'ning yoshi; `queued_at` siz eski job bo'lsa noma'lum
    oldest_s: float | None


class DbStatement(BaseModel):
    calls: int
    total_ms: float
    mean_ms: float
    rows: int
    query: str


class SystemStatus(BaseModel):
    """Yon menyudagi belgi: oxirgi `minutes` daqiqa holati."""

    minutes: int
    level: Level
    findings: list[Finding]


class SystemPerf(BaseModel):
    minutes: int
    level: Level
    findings: list[Finding]
    thresholds: Thresholds
    #: Ma'lumot aslida qaysi paytdan bor — tanlangan oraliqdan kech bo'lsa sahifa aytadi; None = yozuv yo'q
    covered_from: datetime | None
    covered_minutes: float
    requests: int
    #: Oynada ko'ringan ishchi jarayonlar (pid) — restartdan keyin eskisi ham sanaladi
    pids: list[int]
    endpoints: list[EndpointStat]
    lag_count: int
    #: Shundan `thresholds.lag_bad_ms` dan uzunlari — xulosadagi son bilan bir xil
    lag_long_count: int
    lag_longest_ms: int
    lag_total_ms: int
    #: Oxirgi 50 tasi (`routes/system._LAG_SHOW`, yangisi birinchi); hammasi `lag_count` da
    lag_incidents: list[LagIncident]
    labels: PrintStat
    queues: list[QueueStat]
    #: `pg_stat_statements` yuklanmagan bo'lsa False (lokal Postgres sozlanmagan bo'lishi mumkin)
    db_available: bool
    #: Statistika qachondan beri yig'ilyapti — oxirgi nollash (qo'lda yoki baza yangidan yaratilganda)
    db_since: datetime | None
    db_top: list[DbStatement]


class EndpointBucket(BaseModel):
    at: datetime
    count: int
    p50_ms: float | None
    max_ms: float | None
    #: 1 s dan sekin so'rovlar
    slow: int
    errors: int


class FreezeMatch(BaseModel):
    """Sekin so'rov davomida o'sha ishchida bo'lgan eng uzun muzlash."""

    at: datetime
    lag_ms: int
    inflight: list[InflightRequest]
    gc_ms: int | None = None  # `LagIncident.gc_ms` kabi


class SlowRequest(BaseModel):
    at: datetime  # tugagan payt
    ms: float
    status: int
    pid: int | None
    #: Shu so'rov vaqtining muzlashga to'g'ri kelgan qismi; pid'siz eski yozuvda None
    frozen_ms: float | None
    freeze: FreezeMatch | None


class EndpointDetail(BaseModel):
    method: str
    route: str
    minutes: int
    covered_from: datetime | None
    count: int
    p50_ms: float | None
    p95_ms: float | None
    max_ms: float | None
    errors: int
    bucket_minutes: int
    buckets: list[EndpointBucket]
    #: 1 s dan sekin so'rovlar va ularning qancha qismi muzlashga to'g'ri kelgani
    slow_count: int
    slow_frozen_share: float | None
    #: Dalilga tayangan sabab jumlasi (sekin so'rov bo'lmasa bo'sh)
    cause: str
    slowest: list[SlowRequest]
    #: Oxirgi 5xx lar (yangisi birinchi, ko'pi bilan 20)
    error_times: list[datetime]
