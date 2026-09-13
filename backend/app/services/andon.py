"""Andon (stanok signal ustuni) — jonli holat Redis'da.

Jonli holat jadvalda EMAS: u har necha soniyada yangilanadi va faqat oxirgisi
kerak. Kalit TTL bilan yoziladi: agent xabar bermay qo'ysa holat o'zi yo'qoladi va
sahifa "aloqa yo'q" ko'rsatadi — eskirgan "Ishlov" yolg'on ko'rinib turmaydi.
Xom hodisalar esa `andon_event` jadvalida (tarix, keyingi bosqichdagi OEE uchun).
"""

import json
import logging
from collections.abc import Iterable
from typing import Any

from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError

from app.core.config import settings

logger = logging.getLogger(__name__)

ANDON_LIVE_KEY = "mes:andon:live:{}"
#: Agent har bir necha soniyada, bo'sh turganda ham har 30 soniyada yuboradi —
#: 90 soniya ichida kelmasa agent, kompyuter yoki Pico bilan aloqa yo'q.
ANDON_LIVE_TTL = 90


async def save_live(machine_id: int, live: dict[str, Any]) -> bool:
    """Jonli holatni yozadi. Holat yoki uning boshlangan vaqti O'ZGARGAN bo'lsa True.

    Qaytgan qiymat WS xabari uchun: agent har 30 soniyada bir xil holatni qayta
    yuboradi (TTL yangilansin), har safar ekranlarga xabar tarqatish shovqin bo'lardi.

    Redis ishlamasa False: xom hodisalar jadvalga allaqachon yozilgan, jonli holat
    esa yordamchi — uning xatosi agentga 500 qaytarib, navbatni qayta yubortirmasin."""
    try:
        async with AsyncRedis.from_url(settings.REDIS_URL) as redis:
            old_raw = await redis.set(ANDON_LIVE_KEY.format(machine_id), json.dumps(live), ex=ANDON_LIVE_TTL, get=True)
    except (RedisError, OSError) as exc:
        logger.warning("andon jonli holati yozilmadi (machine %s): %r", machine_id, exc)
        return False
    if old_raw is None:
        return True
    try:
        old = json.loads(old_raw)
    except ValueError:
        return True
    return bool(old.get("state") != live.get("state") or old.get("since") != live.get("since"))


async def read_live(machine_ids: Iterable[int]) -> dict[int, dict[str, Any]]:
    """Bir nechta ish markazining jonli holati (andon ulanmagan yoki aloqa yo'q — kalit yo'q).

    Redis ishlamasa bo'sh lug'at: ish markazlari sahifasi andon holatisiz ochilaversin."""
    ids = list(machine_ids)
    if not ids:
        return {}
    try:
        async with AsyncRedis.from_url(settings.REDIS_URL) as redis:
            rows = await redis.mget([ANDON_LIVE_KEY.format(mid) for mid in ids])
    except (RedisError, OSError) as exc:
        logger.warning("andon jonli holati o'qilmadi: %r", exc)
        return {}
    out: dict[int, dict[str, Any]] = {}
    for mid, raw in zip(ids, rows, strict=True):
        if raw is None:
            continue
        try:
            out[mid] = json.loads(raw)
        except ValueError:
            continue
    return out
