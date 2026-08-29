import logging
from datetime import UTC, datetime

from fastapi import Request
from redis.asyncio import Redis

from app.core.exceptions import RateLimitException

logger = logging.getLogger(__name__)


class RateLimiter:
    """Ilovaning umumiy Redis mijozini ushlab turadi: `RateLimit` va `login.py` dagi
    refresh-token `jti` qabrtoshlari. Modul darajasidagi `rate_limiter` nusxasidan foydalaning."""

    client: Redis | None = None

    def initialize(self, redis_url: str) -> None:
        if self.client is None:
            self.client = Redis.from_url(redis_url)

    async def over_limit(self, key: str, limit: int) -> bool:
        """Chegaradan oshganmi — HISOBLAMASDAN, faqat o'qiydi."""
        if self.client is None:
            return True  # lifespan doim initialize() qiladi; bu yerga tushsak — fail-closed
        try:
            raw = await self.client.get(key)
            return raw is not None and int(raw) >= limit
        except Exception:
            logger.exception("Rate limit o'qishda xato (%s)", key)
            # Fail closed: a Redis outage must not silently switch off brute-force protection.
            return True

    async def bump(self, key: str, period: int) -> None:
        """Bitta MUVAFFAQIYATSIZ urinishni hisobga oladi."""
        if self.client is None:
            return
        try:
            if await self.client.incr(key) == 1:
                await self.client.expire(key, period)
        except Exception:
            logger.exception("Rate limit yozishda xato (%s)", key)


rate_limiter = RateLimiter()


class RateLimit:
    """Brute-force himoyasi: FAQAT muvaffaqiyatsiz urinishlar hisoblanadi.

    Ilgari har so'rov hisoblanardi — kirish MUVAFFAQIYATLI bo'lsa ham. Tsex esa
    bitta tashqi IP orqali chiqadi (NAT): monobloklar, admin va menejer bir xil
    manzildan ko'rinadi, ya'ni 5 urinish / 5 daqiqa chegarasi butun zavodga
    umumiy edi. Smena boshida operatorlar navbatma-navbat kirsa byudjet tugar
    va keyingi odam — odatda admin — "So'rovlar chegarasidan oshib ketdi"
    xatosiga uchrardi, hech kim parolni xato termagan bo'lsa ham. Prodda
    o'lchangan: 30 daqiqada 9 ta muvaffaqiyatli kirish va 8 ta 429.

    Endi qoida asl ma'nosida ishlaydi: bog'liqlik faqat TEKSHIRADI, chaqiruvchi
    esa parol/beyjik noto'g'ri bo'lgan yo'lda `hit()` chaqiradi.
    """

    def __init__(self, limit: int, period: int):
        self.limit = limit
        self.period = period

    def _key(self, request: Request) -> str:
        ip = request.client.host if request.client else "unknown"
        now = int(datetime.now(UTC).timestamp())
        window_start = now - (now % self.period)
        return f"ratelimit:{ip}:{request.url.path}:{window_start}"

    async def __call__(self, request: Request) -> None:
        """Route bog'liqligi: faqat tekshiradi, hisobni oshirmaydi."""
        if await rate_limiter.over_limit(self._key(request), self.limit):
            raise RateLimitException("So'rovlar chegarasidan oshib ketdi.")

    async def hit(self, request: Request) -> None:
        """Muvaffaqiyatsiz urinish — chaqiruvchi xato yo'lida chaqiradi."""
        await rate_limiter.bump(self._key(request), self.period)
