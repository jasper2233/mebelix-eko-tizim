"""«Tizim holati» (admin): qaysi endpoint qancha vaqt oladi, event loop qachon va kim tufayli
bloklangan, chek agentga qancha vaqtda yetadi, bazada qaysi so'rov og'ir. Manba — `core/perf.py`
(Redis, ikkala gunicorn ishchisidan umumiy) va `pg_stat_statements`."""

import json
import time
from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.api.deps import AdminUser, SessionDep
from app.core import perf
from app.schemas.system import (
    DbStatement,
    EndpointStat,
    InflightRequest,
    LagIncident,
    PrintStat,
    SystemPerf,
)

router = APIRouter(prefix="/system", tags=["system"])

#: Sahifada ko'rsatiladigan eng og'ir DB so'rovlari soni
_DB_TOP = 15
#: Sahifadagi blok hodisalari soni (yangisi birinchi)
_LAG_SHOW = 50


def _pct(sorted_xs: list[float], q: float) -> float:
    """Eng yaqin rang bo'yicha persentil (ro'yxat saralangan, bo'sh emas)."""
    return sorted_xs[min(len(sorted_xs) - 1, int(q * len(sorted_xs)))]


@router.get("/perf", response_model=SystemPerf, operation_id="read_system_perf")
async def read_system_perf(
    db: SessionDep, _: AdminUser, minutes: Annotated[int, Query(ge=5, le=360)] = 60
) -> SystemPerf:
    since = time.time() - minutes * 60
    req_lines, lag_lines, print_lines = await perf.read_lists()

    by_route: dict[tuple[str, str], list[float]] = defaultdict(list)
    errors: dict[tuple[str, str], int] = defaultdict(int)
    requests = 0
    for line in req_lines:
        ts, method, route, ms, status = line.split("|")
        if float(ts) < since:
            break  # ro'yxat yangisidan eskisiga — qolgani oynadan tashqarida
        requests += 1
        by_route[(method, route)].append(float(ms))
        if int(status) >= 500:
            errors[(method, route)] += 1
    endpoints = []
    for (method, route), xs in by_route.items():
        xs.sort()
        endpoints.append(
            EndpointStat(
                method=method,
                route=route,
                count=len(xs),
                p50_ms=_pct(xs, 0.5),
                p95_ms=_pct(xs, 0.95),
                max_ms=xs[-1],
                total_s=round(sum(xs) / 1000, 1),
                errors=errors[(method, route)],
            )
        )
    endpoints.sort(key=lambda e: -e.total_s)

    incidents = []
    for line in lag_lines:
        rec = json.loads(line)
        if rec["ts"] < since:
            break
        incidents.append(
            LagIncident(
                at=datetime.fromtimestamp(rec["ts"], UTC),
                lag_ms=rec["lag_ms"],
                pid=rec["pid"],
                inflight=[InflightRequest(path=p, elapsed_ms=ms) for p, ms in rec["inflight"]],
            )
        )
        if len(incidents) >= _LAG_SHOW:
            break

    delays = sorted(float(s) for ts, _agent, s in (x.split("|") for x in print_lines) if float(ts) >= since)
    print_stat = PrintStat(
        count=len(delays),
        p50_s=_pct(delays, 0.5) if delays else None,
        p95_s=_pct(delays, 0.95) if delays else None,
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
        requests=requests,
        endpoints=endpoints,
        lag_incidents=incidents,
        labels=print_stat,
        db_available=db_available,
        db_since=db_since,
        db_top=db_top,
    )
