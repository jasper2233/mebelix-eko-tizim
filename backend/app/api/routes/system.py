"""«Tizim holati» (admin): qaysi endpoint qancha vaqt oladi, event loop qachon va nima ishlayotganda
bloklangan, chek agentga qancha vaqtda yetadi va navbatda nechta turibdi, bazada qaysi so'rov og'ir.
Manba — `core/perf.py` (Redis, ikkala gunicorn ishchisidan umumiy) va `pg_stat_statements`;
tahlil va topilmalar — `services/system_health.py`."""

import math
from collections import defaultdict
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.api.deps import AdminUser, SessionDep, client_ip
from app.core import perf
from app.crud import log_action
from app.schemas.system import (
    DbStatement,
    EndpointBucket,
    EndpointDetail,
    EndpointStat,
    FreezeMatch,
    InflightRequest,
    LagIncident,
    PrintStat,
    SlowRequest,
    SystemPerf,
    SystemStatus,
)
from app.services import system_health as sh

router = APIRouter(prefix="/system", tags=["system"])

#: Sahifada ko'rsatiladigan eng og'ir DB so'rovlari soni
_DB_TOP = 15
#: Sahifadagi muzlash qatorlari (yangisi birinchi); soni esa hammasidan
_LAG_SHOW = 50
#: Oraliq: 12 soat — bitta smena; `perf.REQ_KEEP` shunga yetadigan qilib tanlangan
Minutes = Annotated[int, Query(ge=5, le=720)]


def _incident(g: sh.Lag) -> LagIncident:
    return LagIncident(
        at=sh.to_dt(g.ts),
        lag_ms=g.lag_ms,
        pid=g.pid,
        inflight=[InflightRequest(path=p, elapsed_ms=ms) for p, ms in g.inflight],
        gc_ms=g.gc_ms,
    )


@router.get("/status", response_model=SystemStatus, operation_id="read_system_status")
async def read_system_status(db: SessionDep, _: AdminUser) -> SystemStatus:
    """Yon menyudagi belgi uchun: oxirgi 15 daqiqa topilmalari (bazasiz statistika — arzon)."""
    w = await sh.read_window(sh.STATUS_MINUTES)
    fs = sh.findings(w, await sh.queue_stats(db, perf.client()))
    return SystemStatus(minutes=sh.STATUS_MINUTES, level=sh.overall(w, fs), findings=fs)


@router.get("/perf", response_model=SystemPerf, operation_id="read_system_perf")
async def read_system_perf(db: SessionDep, _: AdminUser, minutes: Minutes = 60) -> SystemPerf:
    w = await sh.read_window(minutes)
    queues = await sh.queue_stats(db, perf.client())
    groups = sh.endpoint_groups(w.reqs)
    fs = sh.findings(w, queues, groups)

    errors: dict[tuple[str, str], int] = defaultdict(int)
    for r in w.reqs:
        if r.status >= 500:
            errors[(r.method, r.route)] += 1
    endpoints = [
        EndpointStat(
            method=method,
            route=route,
            count=len(xs),
            p50_ms=sh.pct(xs, 0.5),
            p95_ms=sh.pct(xs, 0.95),
            max_ms=xs[-1],
            total_s=round(sum(xs) / 1000, 1),
            errors=errors[(method, route)],
        )
        for (method, route), xs in groups.items()
    ]
    endpoints.sort(key=lambda e: -e.total_s)

    delays = sorted(w.prints)
    print_stat = PrintStat(
        count=len(delays),
        p50_s=sh.pct(delays, 0.5) if delays else None,
        p95_s=sh.pct(delays, 0.95) if delays else None,
        max_s=delays[-1] if delays else None,
    )

    db_available, db_since, db_top = True, None, []
    try:
        db_since = (await db.execute(text("SELECT stats_reset FROM pg_stat_statements_info"))).scalar()
        db_top = [
            DbStatement(calls=calls, total_ms=round(total, 1), mean_ms=round(mean, 2), rows=rows, query=q)
            for calls, total, mean, rows, q in (
                await db.execute(
                    text(
                        "SELECT calls, total_exec_time, mean_exec_time, rows, query FROM pg_stat_statements "
                        "WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database()) "
                        "ORDER BY total_exec_time DESC LIMIT :n"
                    ),
                    {"n": _DB_TOP},
                )
            ).all()
        ]
    except DBAPIError:
        # Kengaytma yaratilmagan yoki `shared_preload_libraries` da yo'q — sahifaning qolgani ishlasin
        await db.rollback()
        db_available = False

    return SystemPerf(
        minutes=minutes,
        level=sh.overall(w, fs),
        findings=fs,
        thresholds=sh.LIMITS,
        covered_from=sh.to_dt(w.covered_from) if w.covered_from is not None else None,
        covered_minutes=round(w.covered_minutes, 1),
        requests=len(w.reqs),
        pids=sorted({r.pid for r in w.reqs if r.pid is not None}),
        endpoints=endpoints,
        lag_count=len(w.lags),
        lag_long_count=sum(1 for g in w.lags if g.lag_ms >= sh.LIMITS.lag_bad_ms),
        lag_longest_ms=max((g.lag_ms for g in w.lags), default=0),
        lag_total_ms=sum(g.lag_ms for g in w.lags),
        lag_incidents=[_incident(g) for g in w.lags[:_LAG_SHOW]],
        labels=print_stat,
        queues=queues,
        db_available=db_available,
        db_since=db_since,
        db_top=db_top,
    )


@router.get("/perf/endpoint", response_model=EndpointDetail, operation_id="read_system_perf_endpoint")
async def read_system_perf_endpoint(_: AdminUser, method: str, route: str, minutes: Minutes = 60) -> EndpointDetail:
    """Bitta endpoint: vaqt bo'yicha qachon sekinlashgan, eng sekin so'rovlari va ularning har biri
    davomida o'sha ishchi muzlaganmi — "o'zi og'irmi yoki boshqasini kutganmi" savoliga dalil."""
    w = await sh.read_window(minutes)
    reqs = [r for r in w.reqs if r.method == method and r.route == route]
    lags = sh.by_pid(w.lag_ctx)
    xs = sorted(r.ms for r in reqs)

    # Ustunlar soni ~30: 15 daq -> 1 daq, 1 soat -> 2 daq, 12 soat -> 24 daq. Ma'lumot BOR vaqtga
    # qarab: 1 soatlik oynada 4 daqiqa yozuv bo'lsa 2 daqiqalik 2 ta ustun hech narsa ko'rsatmasdi
    step = max(1, math.ceil(min(minutes, w.covered_minutes or minutes) / 30))
    start = w.covered_from if w.covered_from is not None else w.now - minutes * 60
    first = math.floor(start / (step * 60)) * step * 60
    groups: dict[float, list[sh.Req]] = {
        first + i * step * 60: [] for i in range(math.ceil((w.now - first) / (step * 60)))
    }
    for r in reqs:
        groups.setdefault(first + math.floor((r.ts - first) / (step * 60)) * step * 60, []).append(r)
    buckets = []
    for at, rs in sorted(groups.items()):
        ms = sorted(r.ms for r in rs)
        buckets.append(
            EndpointBucket(
                at=sh.to_dt(at),
                count=len(ms),
                p50_ms=sh.pct(ms, 0.5) if ms else None,
                max_ms=ms[-1] if ms else None,
                slow=sum(1 for x in ms if x >= sh.LIMITS.p95_warn_ms),
                errors=sum(1 for r in rs if r.status >= 500),
            )
        )

    slowest = []
    for r in sorted(reqs, key=lambda r: -r.ms)[:10]:
        fz, lag = sh.frozen_ms(r, lags) if r.pid is not None else (None, None)
        slowest.append(
            SlowRequest(
                at=sh.to_dt(r.ts),
                ms=r.ms,
                status=r.status,
                pid=r.pid,
                frozen_ms=round(fz) if fz is not None else None,
                freeze=FreezeMatch(
                    at=sh.to_dt(lag.ts),
                    lag_ms=lag.lag_ms,
                    inflight=[InflightRequest(path=p, elapsed_ms=e) for p, e in lag.inflight],
                    gc_ms=lag.gc_ms,
                )
                if lag is not None
                else None,
            )
        )
    split = sh.split_slow(reqs, lags)
    return EndpointDetail(
        method=method,
        route=route,
        minutes=minutes,
        covered_from=sh.to_dt(w.covered_from) if w.covered_from is not None else None,
        count=len(xs),
        p50_ms=sh.pct(xs, 0.5) if xs else None,
        p95_ms=sh.pct(xs, 0.95) if xs else None,
        max_ms=xs[-1] if xs else None,
        errors=sum(1 for r in reqs if r.status >= 500),
        bucket_minutes=step,
        buckets=buckets,
        slow_count=split.count,
        slow_frozen_share=split.share,
        cause=sh.cause_sentence(method, route, split),
        slowest=slowest,
        error_times=[sh.to_dt(r.ts) for r in reqs if r.status >= 500][:20],
    )


@router.post("/db-stats/reset", status_code=204, operation_id="reset_system_db_stats")
async def reset_system_db_stats(db: SessionDep, current_user: AdminUser, request: Request) -> None:
    """`pg_stat_statements` ni nollaydi — o'zgarishdan (deploy, indeks) keyin og'ir so'rovlarni
    toza boshdan o'lchash uchun. Statistika jami, oynaga bo'linmaydi: nollamasdan eski yuk aralashadi."""
    try:
        await db.execute(text("SELECT pg_stat_statements_reset()"))
    except DBAPIError as e:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Baza statistikasini nollab bo'lmadi: kengaytma yoqilmagan yoki huquq yo'q."
        ) from e
    log_action(
        db,
        module="system",
        action="db_stats_reset",
        user_id=current_user.id,
        message="Baza so'rovlari statistikasi nollandi",
        ip=client_ip(request),
    )
    await db.commit()
