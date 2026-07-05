import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import queue
from app.core.utils.rate_limit import rate_limiter

LOGGER = logging.getLogger(__name__)


async def check_database_health(db: AsyncSession) -> bool:
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception as e:
        LOGGER.exception("Database health check failed: %s", e)
        return False


async def check_redis_health() -> bool:
    """Ping every Redis client this app uses. If no Redis features are enabled, the check passes vacuously."""
    clients = [c for c in (queue.pool, rate_limiter.client) if c is not None]
    if not clients:
        return True
    try:
        for client in clients:
            await client.ping()
        return True
    except Exception as e:
        LOGGER.exception("Redis health check failed: %s", e)
        return False
