from datetime import UTC, datetime

from fastapi import Request
from redis.asyncio import ConnectionPool, Redis

from app.core.exceptions import RateLimitException
from app.core.logger import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Holds the shared Redis client used by `RateLimit`. Use the module-level `rate_limiter` instance."""

    pool: ConnectionPool | None = None
    client: Redis | None = None

    def initialize(self, redis_url: str) -> None:
        if self.pool is None:
            self.pool = ConnectionPool.from_url(redis_url)
            self.client = Redis(connection_pool=self.pool)

    async def is_rate_limited(self, key: str, limit: int, period: int) -> bool:
        if self.client is None:
            # Rate limiting disabled by config (ENABLE_REDIS_RATE_LIMIT) — deliberate, so allow.
            return False
        try:
            current_count = await self.client.incr(key)
            if current_count == 1:
                await self.client.expire(key, period)
            return current_count > limit
        except Exception as e:
            logger.exception("Error checking rate limit for key %s: %s", key, e)
            # Fail closed: a Redis outage must not silently switch off brute-force protection.
            return True


rate_limiter = RateLimiter()


class RateLimit:
    def __init__(self, limit: int, period: int):
        self.limit = limit
        self.period = period

    async def __call__(self, request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        path = request.url.path
        current_timestamp = int(datetime.now(UTC).timestamp())
        window_start = current_timestamp - (current_timestamp % self.period)
        key = f"ratelimit:{ip}:{path}:{window_start}"

        if await rate_limiter.is_rate_limited(key, self.limit, self.period):
            raise RateLimitException("So'rovlar chegarasidan oshib ketdi.")
