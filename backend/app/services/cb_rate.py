"""Markaziy bank dollar kursi — Boshqaruv panelida sexdagi kurs YONIDA ko'rsatish uchun.

Bu kurs hisob-kitobga TUSHMAYDI. Narx sexdagi kurs (`warehouse_pricing.usd_rate`) bilan
hisoblanadi, chunki kurs o'zgarishi butun katalogning xaridi va furnitura sotuvini qayta
hisoblaydi — bunday o'zgarishni odam ko'rib tasdiqlashi kerak. Markaziy bank raqami faqat
SOLISHTIRISH uchun: «sizdagi 11 900, bankda 12 055.90» deb turadi va omborchi xohlasa bir
bosishda qo'llaydi.

Manba — `cbu.uz` ning ochiq JSON'i (egasining tanlovi, 2026-10-17). Yangi bog'liqlik qo'shilmadi:
bitta GET uchun `urllib` yetadi.
"""

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)

CB_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/USD/"
#: So'rov chegarasi — panel shu tufayli kutib qolmasin
CB_TIMEOUT_S = 5
#: Markaziy bank kursni kuniga bir marta e'lon qiladi, ya'ni soatiga bir tortish yetarli
CACHE_KEY = "mes:cb:usd"
CACHE_TTL = 3600
#: Bank javob bermasa ham qayta-qayta urinmaslik uchun — qisqa muddatli «yo'q» belgisi
FAIL_KEY = "mes:cb:usd:fail"
FAIL_TTL = 300


@dataclass(frozen=True, slots=True)
class CbRate:
    rate: Decimal
    #: Bank bergan sana, `17.10.2026` ko'rinishida (xom holida — ekranda shunday ko'rsatiladi)
    date: str
    #: Oldingi kundan farq (bank o'zi hisoblaydi)
    diff: Decimal | None


def _parse(raw: Any) -> CbRate | None:
    """Bank javobidan USD qatorini oladi. Shakl kutilganidan boshqa bo'lsa — `None`."""
    row = raw[0] if isinstance(raw, list) and raw else raw
    if not isinstance(row, dict) or row.get("Ccy") != "USD":
        return None
    try:
        rate = Decimal(str(row["Rate"]))
        diff = Decimal(str(row["Diff"])) if row.get("Diff") not in (None, "") else None
    except (KeyError, InvalidOperation):
        return None
    # Nominal 1 dan boshqa bo'lsa kurs bitta dollarga tegishli emas — ishlatmaymiz
    if rate <= 0 or str(row.get("Nominal", "1")).strip() not in ("1", "1.0"):
        return None
    return CbRate(rate=rate, date=str(row.get("Date") or ""), diff=diff)


def _fetch() -> CbRate | None:
    with urllib.request.urlopen(CB_URL, timeout=CB_TIMEOUT_S) as r:  # noqa: S310 — manzil qat'iy
        return _parse(json.loads(r.read().decode("utf-8")))


async def cb_usd() -> CbRate | None:
    """Markaziy bank dollar kursi (keshdan yoki bankdan). Olinmasa `None` — panel kursni
    solishtirmasdan, lekin to'liq ishlab turadi: bu ma'lumot yordamchi, majburiy emas."""
    import asyncio

    redis: AsyncRedis | None = None
    try:
        redis = AsyncRedis.from_url(settings.REDIS_URL)
        if await redis.get(FAIL_KEY):
            return None
        keshdan = await redis.get(CACHE_KEY)
        if keshdan:
            saqlangan = json.loads(keshdan)
            return CbRate(
                rate=Decimal(saqlangan["rate"]),
                date=saqlangan["date"],
                diff=Decimal(saqlangan["diff"]) if saqlangan.get("diff") is not None else None,
            )
    except (RedisError, OSError, ValueError, KeyError) as exc:
        logger.warning("Markaziy bank kursi keshdan o'qilmadi: %r", exc)
        redis = None

    try:
        kurs = await asyncio.to_thread(_fetch)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        logger.warning("Markaziy bank kursi olinmadi: %r", exc)
        kurs = None

    if redis is not None:
        try:
            if kurs is None:
                await redis.set(FAIL_KEY, "1", ex=FAIL_TTL)
            else:
                await redis.set(
                    CACHE_KEY,
                    json.dumps(
                        {
                            "rate": str(kurs.rate),
                            "date": kurs.date,
                            "diff": str(kurs.diff) if kurs.diff is not None else None,
                        }
                    ),
                    ex=CACHE_TTL,
                )
        except (RedisError, OSError) as exc:
            logger.warning("Markaziy bank kursi keshga yozilmadi: %r", exc)
        finally:
            await redis.aclose()
    return kurs
