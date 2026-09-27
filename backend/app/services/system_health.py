"""«Tizim holati» tahlili — `core/perf.py` yozuvlaridan oyna statistikasi va topilmalar.

Topilma (nima yomon) FAQAT shu yerda hisoblanadi: sahifa ham, yon menyudagi belgi ham
bitta manbadan o'qiydi, chegaralar ham bitta. Har jumla o'lchangan dalilga tayanadi —
sabab taxmin qilinmaydi. "Bu so'rov nega sekin" savoliga javob pid va vaqt bo'yicha
solishtirishdan chiqadi: sekin so'rov davomida O'SHA ishchi jarayonning event loop'i
muzlaganmi va muzlash so'rov vaqtining qancha qismini egallagan.
"""

import asyncio
import json
import math
import time
from bisect import bisect_right
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, NamedTuple

from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import perf
from app.core.config import TASHKENT_TZ
from app.models import BridgeAgent, Machine
from app.schemas.system import Finding, QueueStat, Thresholds
from app.tasks import print_queue_key

Level = Literal["ok", "warn", "bad", "nodata"]

#: Chegaralar tinch holatda sahifa ham tinch turishi uchun tanlangan: tuzatishdan keyingi
#: normal soatda (p95 ≤ 0,9 s) hech narsa bo'yalmaydi, 2026-09-26 dagi muammo qizil chiqadi.
LIMITS = Thresholds(
    p95_warn_ms=1000,  # eng sekin 5% shundan oshsa operator kutishni sezadi
    p95_bad_ms=3000,  # ...shundan oshsa ishi to'xtaydi
    p50_warn_ms=500,  # odatiy so'rov shundan sekin — endpoint O'ZI og'ir
    p50_bad_ms=1000,
    lag_bad_ms=1000,  # server muzlashi shundan uzun — jiddiy
    lag_warn_count=5,  # oynada shuncha qisqa (0,2-1 s) muzlash — e'tibor
    label_warn_s=2,  # chek navbatdan agentgacha, p95 (normalda ~0,3 s)
    label_bad_s=5,
    min_count=5,  # kam chaqirilgan endpointning p95 i tasodif — xulosaga kirmaydi
    queue_stuck_s=5,  # ulangan agent chekni millisekundlarda oladi
)
#: Yon menyudagi belgi shu oraliqqa qaraydi — «hozir» degani
STATUS_MINUTES = 15


def pct(sorted_xs: list[float], q: float) -> float:
    """Eng yaqin rang bo'yicha persentil: ceil(q*n)-chi element (ro'yxat saralangan, bo'sh emas)."""
    return sorted_xs[max(0, math.ceil(q * len(sorted_xs)) - 1)]


def dur(ms: float) -> str:
    """702 -> "702 ms", 16535 -> "16.5 s" — frontenddagi `dur` bilan bir xil."""
    if ms < 1000:
        return f"{round(ms)} ms"
    return f"{ms / 1000:.{2 if ms < 10_000 else 1}f} s"


def short(route: str) -> str:
    """Hamma yo'l `/api/v1` bilan boshlanadi — jumlada takrorlash shovqin. Muzlash yozuvidagi
    nom metod bilan keladi (`GET /api/v1/...`), shuning uchun boshidan emas, birinchi uchragan joydan."""
    return route.replace("/api/v1", "", 1)


def when(ts: datetime) -> str:
    """Bugun bo'lsa soat, aks holda sana bilan: 3 kun oldingi aloqa «17:35» deb bugungidek o'qilmasin."""
    local = ts.astimezone(TASHKENT_TZ)
    return f"{local:%H:%M}" if local.date() == datetime.now(TASHKENT_TZ).date() else f"{local:%d.%m %H:%M}"


def to_dt(ts: float) -> datetime:
    return datetime.fromtimestamp(ts, UTC)


class Req(NamedTuple):
    """Bitta so'rov. NamedTuple — 12 soatlik oynada 60 ming qator: frozen dataclass bilan
    tahlil 114 ms edi (o'zi muzlash chegarasiga yaqin)."""

    ts: float  # tugagan payt
    method: str
    route: str
    ms: float
    status: int
    pid: int | None  # pid qo'shilgan deploydan oldin yozilgan qatorlarda yo'q

    @property
    def start(self) -> float:
        return self.ts - self.ms / 1000


class Lag(NamedTuple):
    ts: float  # monitor uyg'ongan payt = loop kechikishi tugagan payt (±`perf.LAG_STEP_S`)
    lag_ms: int
    pid: int
    #: "METOD /shablon" (eskisi — faqat yo'l), eng uzoq ishlayotgani birinchi, ko'pi bilan 8 ta
    inflight: list[tuple[str, int]]
    #: Shundan Python GC yig'imlari; `None` — yozuv bu o'lchov qo'shilishidan (2026-09-27) oldingi
    gc_ms: int | None = None

    @property
    def start(self) -> float:
        return self.ts - self.lag_ms / 1000


def req_ts(line: str) -> float:
    return float(line.split("|", 1)[0])


def parse_req(line: str) -> Req:
    p = line.split("|")
    return Req(float(p[0]), p[1], p[2], float(p[3]), int(p[4]), int(p[5]) if len(p) > 5 else None)


def lag_ts(line: str) -> float:
    return float(json.loads(line)["ts"])


def parse_lag(line: str) -> Lag:
    rec = json.loads(line)
    return Lag(
        ts=rec["ts"],
        lag_ms=rec["lag_ms"],
        pid=rec["pid"],
        inflight=[(p, ms) for p, ms in rec["inflight"]],
        gc_ms=rec.get("gc_ms"),
    )


@dataclass(slots=True)
class Window:
    """Oyna ichidagi o'lchovlar (yangisi birinchi). `covered_from` — ma'lumot aslida qaysi
    paytdan bor: yangi o'rnatishda yoki ro'yxat LTRIM bilan kesilganda tanlangan oraliqdan
    qisqa bo'ladi va sahifa buni aytadi. `None` — umuman yozuv yo'q."""

    minutes: int
    now: float
    covered_from: float | None
    reqs: list[Req]
    lags: list[Lag]
    prints: list[float]  # soniya
    #: Ustma-ustlikni hisoblash uchun: oyna boshidan `perf.ORDER_SLACK_S` oldingi muzlashlar ham —
    #: oyna chegarasini kesib o'tgan sekin so'rov undan oldingi muzlashni «ko'rmay» qolmasin
    lag_ctx: list[Lag] = field(default_factory=list)

    @property
    def covered_minutes(self) -> float:
        return 0.0 if self.covered_from is None else max((self.now - self.covered_from) / 60, 1 / 60)


async def _parse_reqs(lines: list[str], chunk: int = 5_000) -> list[Req]:
    """Bo'laklab, orasida loop'ga navbat berib: 12 soatlik oyna (60 ming qator) bir yo'la
    ~50 ms CPU — shu vaqt ishchidagi boshqa so'rovlar kutardi. Bo'lak ~4 ms."""
    out: list[Req] = []
    for i in range(0, len(lines), chunk):
        out += map(parse_req, lines[i : i + chunk])
        await asyncio.sleep(0)
    return out


async def read_window(minutes: int) -> Window:
    now = time.time()
    since = now - minutes * 60
    req = await perf.read_window(perf.REQ_KEY, since, req_ts)
    lag = await perf.read_window(perf.LAG_KEY, since, lag_ts)
    prn = await perf.read_window(perf.PRINT_KEY, since, req_ts)
    # So'rovlar ro'yxati eng zich — qamrov undan: u oyna boshiga yetmay tugasa, eng eski
    # yozuvdan oldin ma'lumot yo'q. Muzlash va chek ro'yxatining qisqaligi esa "hodisa
    # bo'lmagan" degani; ular faqat LTRIM kesgan bo'lsa qamrovni qisqartiradi.
    start = since
    if req.exhausted and req.items:
        start = max(start, req_ts(req.items[-1]))
    if lag.trimmed and lag.items:
        start = max(start, lag_ts(lag.items[-1]))
    if prn.trimmed and prn.items:
        start = max(start, req_ts(prn.items[-1]))
    lag_all = [parse_lag(x) for x in lag.items]
    return Window(
        minutes=minutes,
        now=now,
        covered_from=start if req.items else None,
        reqs=[r for r in await _parse_reqs(req.items) if r.ts >= start],
        lags=[g for g in lag_all if g.ts >= start],
        prints=[float(sec) for ts, _agent, sec in (x.split("|") for x in prn.items) if float(ts) >= start],
        lag_ctx=lag_all,
    )


#: pid -> (tugash vaqtlari, muzlashlar) — vaqt bo'yicha saralangan. Bitta ishchining muzlashlari
#: ustma-ust tushmaydi (keyingisi oldingisi tugagach boshlanadi), ya'ni tugash bo'yicha saralash
#: boshlanish bo'yicha ham saralash — `bisect` bilan so'rov oralig'iga tushganlarini topish mumkin.
LagIndex = dict[int, tuple[list[float], list[Lag]]]


def by_pid(lags: Iterable[Lag]) -> LagIndex:
    groups: dict[int, list[Lag]] = defaultdict(list)
    for lag in lags:
        groups[lag.pid].append(lag)
    out: LagIndex = {}
    for pid, lst in groups.items():
        lst.sort(key=lambda g: g.ts)
        out[pid] = ([g.ts for g in lst], lst)
    return out


def frozen_ms(req: Req, index: LagIndex) -> tuple[float, Lag | None]:
    """So'rov davomida O'SHA ishchida loop kechikkan (muzlagan) vaqt (ms) va eng uzun ustma-ust
    muzlash. pid'siz (eski) qator solishtirilmaydi — chaqiruvchi uni alohida sanaydi. Ilgari har
    so'rov har muzlash bilan solishtirilardi: 4 000 sekin so'rov va 500 muzlashda 0,3 s bloklardi."""
    if req.pid is None or req.pid not in index:
        return 0.0, None
    ends, lst = index[req.pid]
    total, longest = 0.0, None
    i = bisect_right(ends, req.start)  # so'rov boshlangandan keyin tugagan birinchi muzlash
    while i < len(lst) and lst[i].start < req.ts:
        lag = lst[i]
        total += (min(req.ts, lag.ts) - max(req.start, lag.start)) * 1000
        if longest is None or lag.lag_ms > longest.lag_ms:
            longest = lag
        i += 1
    return min(total, req.ms), longest


@dataclass(slots=True)
class SlowSplit:
    """So'rovlar (odatda 1 s dan sekinlari): vaqtining qancha qismi o'sha ishchi muzlagan paytga to'g'ri keladi."""

    count: int = 0  # jami so'rov
    unknown: int = 0  # pid'siz — solishtirib bo'lmaydi
    ms: float = 0.0  # solishtirilganlarning jami vaqti
    frozen: float = 0.0  # shundan muzlash ustiga tushgani
    #: Muzlashga to'g'ri kelgan so'rov -> o'sha muzlashda eng uzoq ishlayotgan so'rov (har so'rovga bitta)
    culprits: Counter[str] = field(default_factory=Counter)

    @property
    def share(self) -> float | None:
        return self.frozen / self.ms if self.ms else None


def split_slow(reqs: Iterable[Req], index: LagIndex, min_ms: float = LIMITS.p95_warn_ms) -> SlowSplit:
    out = SlowSplit()
    for r in reqs:
        if r.ms < min_ms:
            continue
        out.count += 1
        if r.pid is None:
            out.unknown += 1
            continue
        fz, lag = frozen_ms(r, index)
        out.ms += r.ms
        out.frozen += fz
        if lag is not None and lag.inflight:
            out.culprits[lag.inflight[0][0]] += 1
    return out


def same_endpoint(name: str, method: str, route: str) -> bool:
    """Muzlash yozuvidagi nom shu endpointmi. Yangi yozuv "METOD /yo'l"; eskisida metod yo'q — bir
    yo'ldagi GET va PATCH ni ajratib bo'lmaydi, shuning uchun eski yozuv mos deb hisoblanmaydi."""
    return name == f"{method} {route}"


def cause_sentence(method: str, route: str, s: SlowSplit) -> str:
    """Sekin so'rovlar sababi — faqat o'lchangan ulush va sanoqdan. 1 s dan sekin so'rov yo'q bo'lsa bo'sh."""
    if not s.count:
        return ""
    known = s.count - s.unknown
    parts = []
    share = s.share
    if share is not None:
        parts.append(
            f"1 s dan sekin {known} ta so'rov vaqtining {round(share * 100)}% i o'sha ishchi muzlagan "
            "(event loop kechikkan) paytga to'g'ri keladi."
        )
        matched = sum(s.culprits.values())
        if matched:
            top, k = s.culprits.most_common(1)[0]
            who = "shu endpointning o'zi" if same_endpoint(top, method, route) else short(top)
            parts.append(
                f"Muzlashga to'g'ri kelgan {matched} tadan {k} tasida o'sha paytda eng uzoq ishlayotgan so'rov — "
                f"{who} (ehtimoliy sabab)."
            )
        if share < 0.5:
            parts.append(
                "Qolgan vaqtda 0.2 s dan uzun loop kechikishi bo'lmagan: vaqt bazani yoki Redisni kutishga, "
                "yoki qisqaroq kechikishlarga ketgan."
            )
    if s.unknown:
        parts.append(
            f"{'Yana ' if known else ''}{s.unknown} tasini solishtirib bo'lmadi — ular pid qo'shilishidan oldin "
            "yozilgan (ishchi raqami yo'q)."
        )
    return " ".join(parts)


def endpoint_groups(reqs: Iterable[Req]) -> dict[tuple[str, str], list[float]]:
    """(method, route) -> saralangan davomiyliklar (ms)."""
    out: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in reqs:
        out[(r.method, r.route)].append(r.ms)
    for xs in out.values():
        xs.sort()
    return out


async def queue_stats(db: AsyncSession, redis: AsyncRedis) -> list[QueueStat]:
    """Chop etadigan har agentning navbati: nechta chek kutyapti va eng eskisi qachondan."""
    agents = (
        await db.execute(
            select(BridgeAgent.id, BridgeAgent.name, BridgeAgent.last_seen_at, Machine.name)
            .outerjoin(Machine, Machine.id == BridgeAgent.machine_id)
            .where(
                BridgeAgent.is_deleted == False,  # noqa: E712
                BridgeAgent.token_hash.is_not(None),
                BridgeAgent.can_print,
            )
            .order_by(BridgeAgent.name)
        )
    ).all()
    if not agents:
        return []
    async with redis.pipeline(transaction=False) as pipe:
        for agent_id, *_ in agents:
            pipe.llen(print_queue_key(agent_id))
            pipe.lindex(print_queue_key(agent_id), -1)  # BRPOP o'ng tomondan oladi — eng eskisi shu
        res = await pipe.execute()
    now = time.time()
    out = []
    for i, (agent_id, name, last_seen, machine) in enumerate(agents):
        pending, oldest = int(res[2 * i]), res[2 * i + 1]
        age = None
        if oldest is not None:
            try:
                queued_at = json.loads(oldest).get("queued_at")
            except ValueError:
                queued_at = None
            if isinstance(queued_at, int | float):
                age = round(now - queued_at, 1)
        out.append(
            QueueStat(
                agent_id=agent_id,
                name=name,
                machine_name=machine,
                last_seen_at=last_seen,
                pending=pending,
                oldest_s=age,
            )
        )
    return out


def findings(
    w: Window, queues: list[QueueStat], stats: dict[tuple[str, str], list[float]] | None = None
) -> list[Finding]:
    """Xulosa: nima yomon va nega — raqamlarni o'qimasdan ham ko'rinsin. Jiddiysi birinchi.
    `stats` — chaqiruvchida `endpoint_groups(w.reqs)` tayyor bo'lsa (12 soatda qayta hisob ~10 ms)."""
    out: list[Finding] = []
    lags_long = [g for g in w.lags if g.lag_ms >= LIMITS.lag_bad_ms]
    if lags_long:
        culprits = Counter(g.inflight[0][0] for g in lags_long if g.inflight)
        text = (
            f"Server ishchisi {len(lags_long)} marta 1 soniyadan uzoq muzladi "
            f"(eng uzuni {dur(max(g.lag_ms for g in lags_long))})."
        )
        if culprits:
            name, n = culprits.most_common(1)[0]
            text += f" {len(lags_long)} tadan {n} tasida o'sha paytda eng uzoq ishlayotgan so'rov — {short(name)}."
        out.append(Finding(level="bad", text=text + " Muzlash paytida o'sha ishchidagi so'rovlar navbatda turadi."))
    elif len(w.lags) >= LIMITS.lag_warn_count:
        out.append(
            Finding(
                level="warn",
                text=f"Server ishchisi {len(w.lags)} marta qisqa muzladi (0.2–1 s) — «Server muzlashlari» "
                "jadvalida o'sha paytda nima ishlaganini ko'ring.",
            )
        )

    for q in queues:
        if q.pending and q.oldest_s is not None and q.oldest_s >= LIMITS.queue_stuck_s:
            seen = f"oxirgi aloqa {when(q.last_seen_at)}" if q.last_seen_at else "oxirgi aloqa noma'lum"
            out.append(
                Finding(
                    level="bad",
                    text=f"{q.name}: navbatda {q.pending} ta chek, eng eskisi {dur(q.oldest_s * 1000)} oldin "
                    f"so'ralgan — cheklar agentga yetib bormayapti ({seen}).",
                )
            )

    if stats is None:
        stats = endpoint_groups(w.reqs)
    reliable = {k: xs for k, xs in stats.items() if len(xs) >= LIMITS.min_count}
    own = sorted(
        ((k, pct(xs, 0.5), pct(xs, 0.95)) for k, xs in reliable.items() if pct(xs, 0.5) >= LIMITS.p50_warn_ms),
        key=lambda x: -x[1],
    )
    index = by_pid(w.lag_ctx)
    for (method, route), p50, p95 in own[:3]:
        text = f"{short(route)} odatda sekin: odatiy so'rovi {dur(p50)}, sekin 5% i {dur(p95)}."
        # "o'zi og'ir" deb bo'lmaydi, agar vaqti muzlash ustiga tushgan bo'lsa — o'shani aytamiz
        split = split_slow((r for r in w.reqs if r.method == method and r.route == route), index, min_ms=0)
        if split.share is not None and split.share >= 0.5:
            text += f" Lekin vaqtining {round(split.share * 100)}% i o'sha ishchi muzlagan paytga to'g'ri keladi."
        out.append(Finding(level="bad" if p50 >= LIMITS.p50_bad_ms else "warn", text=text, method=method, route=route))
    if len(own) > 3:
        out.append(
            Finding(
                level="warn",
                text=f"Yana {len(own) - 3} ta endpointning odatiy so'rovi {dur(LIMITS.p50_warn_ms)} dan sekin — "
                "jadvalda.",
            )
        )

    waited = sorted(
        (k for k, xs in reliable.items() if pct(xs, 0.5) < LIMITS.p50_warn_ms and pct(xs, 0.95) >= LIMITS.p95_warn_ms),
        key=lambda k: -pct(stats[k], 0.95),
    )
    if waited:
        names = ", ".join(short(r) for _m, r in waited[:3]) + (" va boshq." if len(waited) > 3 else "")
        text = (
            f"{len(waited)} ta endpoint odatda tez, lekin ba'zan {LIMITS.p95_warn_ms / 1000:g} s dan sekin bo'lgan: "
            f"{names}."
        )
        keys = set(waited)
        split = split_slow((r for r in w.reqs if (r.method, r.route) in keys), index)
        if split.share is not None:
            whose = (
                f"pid'i bor {split.count - split.unknown} ta sekin so'rovi"
                if split.unknown
                else f"{LIMITS.p95_warn_ms / 1000:g} s dan sekin so'rovlari"
            )
            text += (
                f" Ularning {whose} vaqtining {round(split.share * 100)}% i o'sha ishchi muzlagan paytga "
                "to'g'ri keladi."
            )
        one = waited[0] if len(waited) == 1 else None
        out.append(Finding(level="warn", text=text, method=one and one[0], route=one and one[1]))

    if w.prints:
        p95 = pct(sorted(w.prints), 0.95)
        if p95 >= LIMITS.label_warn_s:
            out.append(
                Finding(
                    level="bad" if p95 >= LIMITS.label_bad_s else "warn",
                    text=f"Chek agentga kech yetyapti: sekin 5% i {p95:.1f} s "
                    "(navbatga qo'yilgandan agent qabul qilguncha).",
                )
            )

    errors = Counter((r.method, r.route) for r in w.reqs if r.status >= 500)
    if errors:
        top3 = ", ".join(f"{short(r)} ({n})" for (_m, r), n in errors.most_common(3))
        out.append(Finding(level="warn", text=f"{sum(errors.values())} ta server xatosi (5xx): {top3}."))
    rank = {"bad": 0, "warn": 1}
    return sorted(out, key=lambda f: rank[f.level])


def overall(w: Window, fs: list[Finding]) -> Level:
    """Butun holat: yozuv bo'lmasa «ma'lumot yo'q» — hech narsa o'lchanmagan joyda «joyida» deyilmaydi."""
    if fs:
        return "bad" if any(f.level == "bad" for f in fs) else "warn"
    return "ok" if w.reqs else "nodata"
