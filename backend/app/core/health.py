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
    """Ping the two lifespan-owned Redis clients (queue + rate limit).

    The WS pub/sub client and the per-connection client in /ws/bridge are not covered.
    """
    clients = [c for c in (queue.pool, rate_limiter.client) if c is not None]
    try:
        for client in clients:
            await client.ping()
        return True
    except Exception as e:
        LOGGER.exception("Redis health check failed: %s", e)
        return False
