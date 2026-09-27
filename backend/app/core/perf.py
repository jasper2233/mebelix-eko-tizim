"""«Tizim holati» o'lchovlari — ikkala gunicorn ishchisidan umumiy, Redis'da.

2026-09-26 da tsexdagi 5-10 soniyalik kutish sababi (bitta so'rov ishchining event
loop'ini ~7 s CPU bilan band qilib, o'sha ishchiga tushgan HAMMA so'rovni kuttirgan)
loglardan qo'lda, soatlab qidirildi. Bu modul o'sha savollarga doimiy javob yozib boradi:

- har so'rov davomiyligi (route shabloni va ishchi pid bilan);
- event loop bloki: loop kechikib uyg'onsa, o'sha paytda ISHLAB TURGAN (yoki shu orada
  tugagan) so'rovlar ro'yxati bilan — eng uzoq ishlayotgani ehtimoliy aybdor — va shundan
  qanchasini Python GC olgani;
- chek kechikishi: job navbatga qo'yilgandan agent qabul qilguncha.

Yozish so'rovni kuttirmaydi va yiqitmaydi: qator xotiradagi buferga qo'shiladi,
`flush_loop` soniyasiga bir marta HAMMA buferni bitta Redis paketida yozadi. Ilgari
har so'rov o'z fon vazifasi va Redis round-trip'ini ochardi. A/B o'lchov (haqiqiy
middleware, 9000 so'rov): eski usul +295 µs, bufer +3,7 µs har so'rovga. Evaziga
ishchi qulasa oxirgi ≤1 s o'lchov yo'qoladi — bu o'lchov, ma'lumot emas. Ro'yxatlar
LTRIM bilan cheklangan, bufer ham.
"""

import asyncio
import gc
import json
import logging
import os
import time
from collections import deque
from collections.abc import Callable
from typing import Any, NamedTuple

from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings

logger = logging.getLogger(__name__)

REQ_KEY = "mes:perf:req"
#: 12 soatlik smena: 2026-09-26 dagi eng band soat 6 456 so'rov — shu sur'at 12 soat davom
#: etsa 77 ming (~70 bayt/qator, ~7 MB). O'qish oyna bo'yicha bo'laklab (`read_window`), ya'ni
#: katta ro'yxat qisqa oynani sekinlatmaydi; ro'yxat oynaga yetmasa sahifa buni aytadi.
REQ_KEEP = 100_000
LAG_KEY = "mes:perf:lag"
LAG_KEEP = 2_000
PRINT_KEY = "mes:perf:print"
PRINT_KEEP = 10_000
_KEEP = {REQ_KEY: REQ_KEEP, LAG_KEY: LAG_KEEP, PRINT_KEY: PRINT_KEEP}

#: Bufer shuncha soniyada bir Redis'ga yoziladi
FLUSH_S = 1.0
#: O'qishda oyna boshidan shuncha ortiq o'qiladi — ro'yxat vaqt bo'yicha qat'iy tartibda emas
#: (`read_window`); 60 s — ishchi 1 daqiqagacha muzlasa ham yozuv tushib qolmaydi
ORDER_SLACK_S = 60

#: Loop har shuncha soniyada uyg'onib kechikishini o'lchaydi. Qadam — o'lchov xatosi:
#: blok uyqu o'rtasida boshlansa qadamgacha qismi ko'rinmaydi (0,5 s qadamda 0,6 s blok
#: 204 ms deb yozilgani sinovda ushlandi). 20 marta/s uyg'onish — bitta yadroning 0,1% i.
LAG_STEP_S = 0.05
#: Undan uzun kechikish — blok (odam sezadigan chegara; oddiy yuk bir necha ms)
LAG_ALERT_S = 0.2

#: Shu ishchida hozir ishlayotgan so'rovlar: kalit -> (nomi, boshlangan perf_counter). Nom —
#: funksiya: route shabloni (`/orders/{order_id}`) routingdan KEYIN ma'lum bo'ladi, muzlash
#: paytida esa handler allaqachon ishlayapti. Xom yo'l (`/orders/123`) jadvaldagi shablonga
#: mos kelmasdi va bitta endpoint id'lar bo'yicha bo'linib sanalardi.
inflight: dict[int, tuple[Callable[[], str], float]] = {}
#: Yaqinda TUGAGAN so'rovlar: (nomi, boshlangan, tugagan). Blok so'rovning OXIRIDA bo'lsa
#: (o'qish, keyin hisob, keyin javob) so'rov monitor uyg'onguncha tugab ulguradi — aybdor
#: shu yerdan topiladi (tekshiruvda 6 tadan 5 ta shunday blok aybdorsiz yozilgani ushlangan)
recent: deque[tuple[Callable[[], str], float, float]] = deque(maxlen=64)

#: Shu ishchida Python GC yig'imlariga ketgan jami vaqt (s). Muzlash yozuvi o'z oynasidagi farqni
#: oladi — «shundan GC»: 2026-09-27 prodda to'liq yig'im ~120 ms edi va qisqa muzlashlarning bir
#: qismi aynan shu bo'lgani probe'da ko'rindi; jonli ishchida esa ko'rinmasdi. GC GIL ostida
#: ishlaydi, ya'ni qaysi oqimda bo'lmasin loop'ni to'xtatadi — hammasi sanaladi.
_gc_spent = 0.0
_gc_t0 = 0.0

_buf: dict[str, list[str]] = {REQ_KEY: [], LAG_KEY: [], PRINT_KEY: []}
_client: AsyncRedis | None = None


def client() -> AsyncRedis:
    """Lazy klient — o'lchov yozuvi va «Tizim holati» o'qishi uchun, ishchi hayoti davomida bitta."""
    global _client
    if _client is None:
        # Timeout: Redis javob bermasa flush osilib qolmasin (bufer baribir cheklangan)
        _client = AsyncRedis.from_url(settings.REDIS_URL, socket_timeout=2, socket_connect_timeout=2)
    return _client


def _add(key: str, value: str) -> None:
    buf = _buf[key]
    buf.append(value)
    if len(buf) > _KEEP[key]:  # Redis uzoq javob bermasa bufer cheksiz o'smasin
        del buf[: len(buf) - _KEEP[key]]


async def flush() -> None:
    """Buferdagi hamma yozuvni bitta paketda: LPUSH eskisidan yangisiga — ro'yxat boshida eng yangisi."""
    batch = {key: vals for key, vals in _buf.items() if vals}
    if not batch:
        return
    for key in batch:
        _buf[key] = []
    try:
        async with client().pipeline(transaction=False) as pipe:
            for key, vals in batch.items():
                pipe.lpush(key, *vals)
                pipe.ltrim(key, 0, _KEEP[key] - 1)
            await pipe.execute()
    except Exception:  # noqa: BLE001 — o'lchov ishni yiqitmasin; paket tashlanadi (qayta urinish tartibni buzardi)
        logger.debug("perf paketi Redis'ga tushmadi", exc_info=True)


async def flush_loop() -> None:
    while True:
        await asyncio.sleep(FLUSH_S)
        await flush()


def finish(key: int) -> None:
    """So'rov tugadi: ishlayotganlardan olib, «yaqinda tugaganlar» ga qo'yadi."""
    item = inflight.pop(key, None)
    if item is not None:
        recent.append((item[0], item[1], time.perf_counter()))


def record_request(method: str, route: str, ms: float, status: int) -> None:
    """Bitta so'rov: `vaqt|METHOD|/route/{param}|ms|status|pid`."""
    _add(REQ_KEY, f"{time.time():.3f}|{method}|{route}|{ms:.1f}|{status}|{os.getpid()}")


def record_delivered(agent_id: int | None, job: dict[str, Any]) -> None:
    """Agent chekni qabul qildi: job navbatga qo'yilgandan (`queued_at`, `tasks._print_job`)
    shu paytgacha — `vaqt|agent|soniya`. `queued_at` siz eski job o'lchanmaydi."""
    queued_at = job.get("queued_at")
    if agent_id is None or not isinstance(queued_at, int | float):
        return
    _add(PRINT_KEY, f"{time.time():.3f}|{agent_id}|{time.time() - queued_at:.3f}")


def _gc_watch(phase: str, info: dict[str, int]) -> None:
    global _gc_spent, _gc_t0
    if phase == "start":
        _gc_t0 = time.perf_counter()
    else:
        _gc_spent += time.perf_counter() - _gc_t0


async def lag_monitor() -> None:
    """Ishchi hayoti davomida: loop kechikib uyg'onsa — blok, o'sha paytdagi so'rovlar bilan yoziladi."""
    gc.callbacks.append(_gc_watch)
    try:
        await _watch_loop()
    finally:
        gc.callbacks.remove(_gc_watch)


async def _watch_loop() -> None:
    while True:
        t0 = time.perf_counter()
        gc0 = _gc_spent
        await asyncio.sleep(LAG_STEP_S)
        now = time.perf_counter()
        lag = now - t0 - LAG_STEP_S
        if lag < LAG_ALERT_S:
            continue
        # Oyna [t0, now] uyquni ham o'z ichiga oladi: uyqu paytida boshlangan GC'ning kechikishdan oldingi
        # qismi ham sanaladi — shuning uchun kechikishdan oshmaydi; xatosi kechikishning o'zi kabi ±qadam
        gc_s = min(_gc_spent - gc0, lag)
        # Kechikish [t0, now] ichida: hali ishlayotganlar + shu oraliqda tugaganlar — shu oraliqda kamida bir
        # qadam (50 ms) ishlaganlari. Kechikish bitta blok emas, ketma-ket callback'lar ham bo'lishi mumkin,
        # ya'ni so'rov uning ICHIDA boshlanib CPU yegan bo'lishi mumkin (boshlanish bo'yicha kesish uni
        # yo'qotardi — sinovda ushlandi). Monitor uyg'onishidan bir zum oldin kelgan «0 ms» so'rov esa
        # kechikishni kutmagan va unga hissa qo'shmagan — ro'yxatga kirmaydi
        busy = sorted(
            [(name(), round((now - st) * 1000)) for name, st in inflight.values() if now - max(st, t0) >= LAG_STEP_S]
            + [(name(), round((end - st) * 1000)) for name, st, end in recent if end - max(st, t0) >= LAG_STEP_S],
            key=lambda x: -x[1],
        )
        logger.warning(
            "Event loop %d ms bloklandi (shundan GC %d ms); ishlab turgan so'rovlar: %s",
            lag * 1000,
            gc_s * 1000,
            busy[:5],
        )
        record = {
            "ts": time.time(),
            "lag_ms": round(lag * 1000),
            "pid": os.getpid(),
            "inflight": busy[:8],
            "gc_ms": round(gc_s * 1000),
        }
        _add(LAG_KEY, json.dumps(record))


class Slice(NamedTuple):
    items: list[str]  # yangisi birinchi; oyna boshidan `ORDER_SLACK_S` gacha eskisi ham bor
    exhausted: bool  # ro'yxat oyna boshiga yetmay tugadi
    trimmed: bool  # ...va u LTRIM kesgani uchun (to'la) — undan eskisi o'chirilgan


async def read_window(key: str, since: float, ts_of: Callable[[str], float], chunk: int = 2_000) -> Slice:
    """`since` dan yangi yozuvlar — ro'yxat bo'laklab o'qiladi va oyna boshidan eski yozuvga
    yetganda to'xtaydi: narxi oynaga bog'liq, ro'yxat hajmiga emas (60 ming yozuvni butunlay
    o'qish 35 ms edi).

    Ikki ishchi paketlarini alohida yozadi, ya'ni ro'yxat vaqt bo'yicha ≤`FLUSH_S` (ishchi
    muzlasa ko'proq) aralash bo'lishi mumkin — shuning uchun `ORDER_SLACK_S` ortig'i bilan
    o'qiladi, aniq kesishni chaqiruvchi qiladi. Ro'yxat oyna boshidan OLDIN tugasa sahifa
    buni aytishi shart: aks holda «oxirgi 12 soatda» deb kamroq vaqtni ko'rsatardi."""
    out: list[str] = []
    start = 0
    stop = since - ORDER_SLACK_S
    while True:
        async with client().pipeline(transaction=False) as pipe:  # execute() tiplangan; lrange() ikki xil
            pipe.lrange(key, start, start + chunk - 1)
            (part,) = await pipe.execute()
        items = [x.decode() if isinstance(x, bytes) else x for x in part]
        # Bo'lakning oxirgisi ham oynada bo'lsa — hammasi oynada (har qatorni tekshirish 60 ming
        # yozuvda 30 ms edi). Aks holda chegara shu bo'lak ichida: eski yozuvgacha olinadi.
        if items and ts_of(items[-1]) >= stop:
            out += items
        else:
            for item in items:
                if ts_of(item) < stop:
                    return Slice(out, exhausted=False, trimmed=False)
                out.append(item)
        if len(part) < chunk:
            return Slice(out, exhausted=True, trimmed=start + len(part) >= _KEEP[key])
        start += chunk
