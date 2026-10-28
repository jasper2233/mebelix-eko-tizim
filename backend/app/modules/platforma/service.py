"""platforma moduli ochiq interfeysi — tashqaridan faqat shu fayl import qilinadi.

Obunachini topish (keshlangan), faol obunachilar ro'yxati va modul yoqilganini tekshirish.
"""

import time
from dataclasses import dataclass

from sqlalchemy import select

from app.core.config import settings
from app.core.db import platform_session
from app.core.tenancy import DEFAULT_TENANT, is_multi, tenant

from .models import Tenant

#: Obunachi holatlari
FAOL = "faol"
TOXTATILGAN = "toxtatilgan"

#: Tarifda yoqiladigan modullar (TZ §2.4, 4-qoida)
MODULLAR = ("mes", "ombor", "kassa", "moliya", "soliq", "kroy")


@dataclass(frozen=True)
class TenantInfo:
    kod: str
    nomi: str
    faol: bool
    modules: frozenset[str]


_cache: dict[str, tuple[float, TenantInfo | None]] = {}


async def resolve(kod: str) -> TenantInfo | None:
    """Obunachi ma'lumoti; yo'q bo'lsa None. `TENANT_CACHE_SECONDS` keshlanadi (yo'qligi ham)."""
    now = time.monotonic()
    hit = _cache.get(kod)
    if hit is not None and now - hit[0] < settings.TENANT_CACHE_SECONDS:
        return hit[1]
    async with platform_session() as db:
        row = (await db.execute(select(Tenant).where(Tenant.kod == kod))).scalar_one_or_none()
    info = (
        None
        if row is None
        else TenantInfo(kod=row.kod, nomi=row.nomi, faol=row.holat == FAOL, modules=frozenset(row.modules or []))
    )
    _cache[kod] = (now, info)
    return info


def invalidate(kod: str | None = None) -> None:
    if kod is None:
        _cache.clear()
    else:
        _cache.pop(kod, None)


async def active_tenants() -> list[str]:
    """Fon vazifalari (cron) aylanib chiqadigan obunachilar. `single` — bitta, standart."""
    if not is_multi():
        return [DEFAULT_TENANT]
    async with platform_session() as db:
        rows = await db.execute(select(Tenant.kod).where(Tenant.holat == FAOL).order_by(Tenant.id))
    return list(rows.scalars())


async def tenant_exists(kod: str) -> bool:
    async with platform_session() as db:
        return (await db.execute(select(Tenant.id).where(Tenant.kod == kod))).first() is not None


async def add_tenant(kod: str, nomi: str, modules: list[str]) -> None:
    async with platform_session() as db:
        db.add(Tenant(kod=kod, nomi=nomi, holat=FAOL, modules=modules))
        await db.commit()
    invalidate(kod)


async def all_tenants() -> list[tuple[str, str, list[str], str]]:
    """(kod, holat, modullar, nomi) — hammasi, to'xtatilganlari ham."""
    async with platform_session() as db:
        rows = (await db.execute(select(Tenant).order_by(Tenant.id))).scalars()
        return [(t.kod, t.holat, list(t.modules or []), t.nomi) for t in rows]


async def set_status(kod: str, holat: str) -> bool:
    async with platform_session() as db:
        t = (await db.execute(select(Tenant).where(Tenant.kod == kod))).scalar_one_or_none()
        if t is None:
            return False
        t.holat = holat
        await db.commit()
    invalidate(kod)
    return True


async def module_enabled(name: str) -> bool:
    """Joriy obunachida `name` moduli yoqilganmi (tarif). `single` — `ENABLED_MODULES` sozlamasi."""
    kod = tenant()
    if not is_multi() or kod == DEFAULT_TENANT:
        return name in settings.ENABLED_MODULES
    info = await resolve(kod)
    return info is not None and name in info.modules
