"""«Tizim holati» o'lchovlari — ikkala gunicorn ishchisidan umumiy, Redis'da.

2026-09-26 da tsexdagi 5-10 soniyalik kutish sababi (bitta so'rov ishchining event
loop'ini ~7 s CPU bilan band qilib, o'sha ishchidagi HAMMA so'rovni — boshqa
postlarning chek va skanini ham — kuttirgan) loglardan qo'lda, soatlab qidirildi.
Bu modul o'sha savollarga doimiy javob yozib boradi:

- har so'rov davomiyligi (route shabloni bilan) — qaysi endpoint qancha vaqt oladi;
- event loop bloki: loop kechikib uyg'onsa, o'sha paytda ISHLAB TURGAN so'rovlar
  ro'yxati bilan — aynan qaysi so'rov kimni kuttirganini ko'rsatadi;
- chek kechikishi: job navbatga qo'yilgandan agent qabul qilguncha.

Yozish so'rovni hech qachon kuttirmaydi va yiqitmaydi: Redis'ga fon vazifasi
bilan yoziladi, xato faqat debug logga tushadi. Ro'yxatlar LTRIM bilan cheklangan.
"""

import asyncio
import json
import logging
import os
import time
from collections.abc import Coroutine
from typing import Any

from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings

logger = logging.getLogger(__name__)

REQ_KEY = "mes:perf:req"
REQ_KEEP = 20_000  # prodda ~0,25 so'rov/s — bir necha soatlik tarix
LAG_KEY = "mes:perf:lag"
LAG_KEEP = 500
PRINT_KEY = "mes:perf:print"
PRINT_KEEP = 5_000

#: Loop har shuncha soniyada uyg'onib kechikishini o'lchaydi. Qadam — o'lchov xatosi:
#: blok uyqu o'rtasida boshlansa qadamgacha qismi ko'rinmaydi (0,5 s qadamda 0,6 s blok
#: 204 ms deb yozilgani sinovda ushlandi). 20 marta/s uyg'onish CPU uchun arzimas.
LAG_STEP_S = 0.05
#: Undan uzun kechikish — blok (odam sezadigan chegara; oddiy yuk bir necha ms)
LAG_ALERT_S = 0.2

#: Shu ishchida hozir ishlayotgan so'rovlar: kalit -> (yo'l, boshlangan perf_counter)
inflight: dict[int, tuple[str, float]] = {}

_client: AsyncRedis | None = None
_tasks: set[asyncio.Task[None]] = set()


def _redis() -> AsyncRedis:
    global _client
    if _client is None:
        _client = AsyncRedis.from_url(settings.REDIS_URL)
    return _client


async def _push(key: str, value: str, keep: int) -> None:
    try:
        async with _redis().pipeline(transaction=False) as pipe:
            pipe.lpush(key, value)
            pipe.ltrim(key, 0, keep - 1)
            await pipe.execute()
    except Exception:  # noqa: BLE001 — o'lchov ishni yiqitmasin
        logger.debug("perf yozuvi Redis'ga tushmadi: %s", key, exc_info=True)


def _fire(coro: Coroutine[Any, Any, None]) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)  # kuchli havola: aks holda GC vazifani tugamasdan yig'ishtirishi mumkin
    task.add_done_callback(_tasks.discard)


def record_request(method: str, route: str, ms: float, status: int) -> None:
    """Bitta so'rov: `vaqt|METHOD|/route/{param}|ms|status`."""
    _fire(_push(REQ_KEY, f"{time.time():.3f}|{method}|{route}|{ms:.1f}|{status}", REQ_KEEP))


def record_delivered(agent_id: int | None, job: dict[str, Any]) -> None:
    """Agent chekni qabul qildi: job navbatga qo'yilgandan (`queued_at`, `tasks._print_job`)
    shu paytgacha — `vaqt|agent|soniya`. `queued_at` siz eski job o'lchanmaydi."""
    queued_at = job.get("queued_at")
    if agent_id is None or not isinstance(queued_at, int | float):
        return
    _fire(_push(PRINT_KEY, f"{time.time():.3f}|{agent_id}|{time.time() - queued_at:.3f}", PRINT_KEEP))


async def lag_monitor() -> None:
    """Ishchi hayoti davomida: loop kechikib uyg'onsa — blok, o'sha paytdagi so'rovlar bilan yoziladi."""
    loop = asyncio.get_running_loop()
    while True:
        t0 = loop.time()
        await asyncio.sleep(LAG_STEP_S)
        lag = loop.time() - t0 - LAG_STEP_S
        if lag < LAG_ALERT_S:
            continue
        now = time.perf_counter()
        busy = sorted(((path, round((now - st) * 1000)) for path, st in inflight.values()), key=lambda x: -x[1])
        logger.warning("Event loop %d ms bloklandi; ishlab turgan so'rovlar: %s", lag * 1000, busy[:5])
        record = {"ts": time.time(), "lag_ms": round(lag * 1000), "pid": os.getpid(), "inflight": busy[:8]}
        await _push(LAG_KEY, json.dumps(record), LAG_KEEP)


async def read_lists() -> tuple[list[str], list[str], list[str]]:
    """Sahifa uchun uchala ro'yxat (yangisi birinchi)."""
    async with _redis().pipeline(transaction=False) as pipe:
        pipe.lrange(REQ_KEY, 0, -1)
        pipe.lrange(LAG_KEY, 0, -1)
        pipe.lrange(PRINT_KEY, 0, -1)
        req, lag, prn = await pipe.execute()

    def dec(xs: list[bytes | str]) -> list[str]:
        return [x.decode() if isinstance(x, bytes) else x for x in xs]

    return dec(req), dec(lag), dec(prn)
