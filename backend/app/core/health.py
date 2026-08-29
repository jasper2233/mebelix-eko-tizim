"""DB va Redis tirikligi: lifespan/worker startup probe'lari ham, `/health` va `/ready` ham shu yerdan.

Probe'lar ilgari `core/setup.py` da edi — arq worker bitta `SELECT 1` uchun butun FastAPI
ilova-fabrikasini (prometheus, uvicorn middleware, `app.api.deps`) import qilishga majbur bo'lardi.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

import anyio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import async_engine
from app.core.utils import queue
from app.core.utils.rate_limit import rate_limiter

LOGGER = logging.getLogger(__name__)


def redis_clients() -> list[tuple[str, Redis]]:
    """Lifespan egalik qiladigan Redis mijozlari — startup probe'i ham, `/ready` ham shundan o'qiydi.

    WS pub/sub mijozi va `/ws/bridge` dagi har-ulanish mijozi bu ro'yxatda YO'Q.
    """
    named: tuple[tuple[str, Redis | None], ...] = (("Queue", queue.pool), ("RateLimit", rate_limiter.client))
    return [(name, client) for name, client in named if client is not None]


async def check_database_health(db: AsyncSession) -> bool:
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception:
        LOGGER.exception("Database health check failed")
        return False


async def check_redis_health() -> bool:
    try:
        for _, client in redis_clients():
            await client.ping()
        return True
    except Exception:
        LOGGER.exception("Redis health check failed")
        return False


# -------------- startup probes --------------
async def _retry_async(label: str, fn: Callable[[], Any]) -> None:
    """Run `fn` up to STARTUP_RETRY_MAX_ATTEMPTS times, sleeping STARTUP_RETRY_DELAY_SECONDS between tries.

    Cancellation (`KeyboardInterrupt`, `asyncio.CancelledError`) propagates immediately.
    """
    max_attempts = settings.STARTUP_RETRY_MAX_ATTEMPTS
    delay = settings.STARTUP_RETRY_DELAY_SECONDS
    for attempt in range(1, max_attempts + 1):
        try:
            await fn()
            return
        except (asyncio.CancelledError, KeyboardInterrupt):
            LOGGER.info("%s check cancelled by user.", label)
            raise
        except Exception as e:
            if attempt == max_attempts:
                LOGGER.error("%s failed after %s attempts: %s", label, max_attempts, e)
                raise
            LOGGER.warning("%s attempt %s failed: %s. Retrying in %ss...", label, attempt, e, delay)
            await anyio.sleep(delay)


async def check_database_connection() -> None:
    async def _probe() -> None:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        LOGGER.info(
            "Database connection successful to %s:%s/%s",
            settings.POSTGRES_SERVER,
            settings.POSTGRES_PORT,
            settings.POSTGRES_DB,
        )

    await _retry_async("Database connection", _probe)


async def check_redis_connection() -> None:
    clients = redis_clients()

    async def _probe() -> None:
        for _, client in clients:
            await client.ping()
        LOGGER.info(
            "Redis connection successful to %s:%s (verified: %s)",
            settings.REDIS_HOST,
            settings.REDIS_PORT,
            ", ".join(name for name, _ in clients),
        )

    await _retry_async("Redis connection", _probe)
