"""Harakatsizlik chegarasi: odam qachon oxirgi marta ish qilgani va qancha kutiladi.

Muammo (2026-09-17): kirish kechgacha ishlab, ertasiga ham saqlanib qolardi —
odam qayta kirmasdan ishini davom ettirardi, smena esa tun bo'yi ochiq turardi.
Qoida — faqat HARAKATSIZLIK: ish jadvali tugashi bilan kesilmaydi, smena kechroq
tugashi mumkin (odam omili).

Faollik manbalari:
- brauzerdagi haqiqiy kiritish (bosish, klaviatura, skaner) — frontend
  `POST /users/me/activity` bilan xabar beradi (daqiqasiga ko'pi bilan bir marta);
- shu ish markazidagi skan — terminal WS `scan.recorded` ni ham faollik deb hisoblaydi,
  brauzer yopiq bo'lsa esa worker skanlarni bazadan o'qiydi (`tasks.close_idle_sessions`).

Chegara oshsa: brauzer login sahifasiga qaytaradi (`useIdleLogout`), server
refresh'ni rad etadi (`login.refresh_access_token`), worker ochiq smenalarni yopadi.
"""

from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenancy import tkey
from app.models.enums import POST_ROLES, UserRole
from app.models.user import User
from app.services.settings_service import IDLE_OPERATOR_MINUTES, IDLE_STAFF_MINUTES, get_setting


def _key(user_id: int) -> str:
    # ponytail: TTL yo'q — kalit hisobga bittadan, bir necha o'nta. TTL qo'yilsa
    # dam olish kunlaridan keyin kalit yo'qolib «faollik noma'lum = ruxsat» bo'lardi.
    return tkey(f"mes:activity:user:{user_id}")


async def touch_activity(redis: Redis | None, user_id: int) -> None:
    if redis is None:  # lifespan'siz (skriptlar) — ilovada Redis doim bor
        return
    await redis.set(_key(user_id), datetime.now(UTC).timestamp())


async def last_activity(redis: Redis | None, user_id: int) -> datetime | None:
    """Oxirgi faollik. `None` — noma'lum (deploy'dan oldingi kirish, Redis tozalangan)."""
    if redis is None:
        return None
    raw = await redis.get(_key(user_id))
    return datetime.fromtimestamp(float(raw), UTC) if raw is not None else None


async def idle_minutes(db: AsyncSession, user: User) -> int | None:
    """Shu hisob necha daqiqa harakatsizlikdan keyin chiqariladi. `None` — chiqarilmaydi.

    TABLO — devordagi ekran, unga hech kim tegmaydi. Tsex (TERMINAL va post rollari)
    qisqa chegara oladi, ofis (admin, direktor, menejer, texnolog) — uzunroq."""
    role = UserRole(user.role)
    if role == UserRole.TABLO:
        return None
    operator = role == UserRole.TERMINAL or role in POST_ROLES
    return int(await get_setting(db, IDLE_OPERATOR_MINUTES if operator else IDLE_STAFF_MINUTES))
