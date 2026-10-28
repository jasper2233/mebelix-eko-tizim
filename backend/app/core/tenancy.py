"""Joriy obunachi (ijarachi) konteksti — EKO TIZIM TZ §2.4.

Har so'rov, WS ulanish va arq vazifasi bitta obunachi nomidan bajariladi. Kim ekanini
`current_tenant` (ContextVar) saqlaydi; baza sessiyasi (`core/db.py: local_session`),
Redis kalitlari (`tkey`), WS hodisalari, JWT va yuklangan fayllar shundan o'qiydi.

`single` rejimda kontekst doim `DEFAULT_TENANT` va hamma narsa avvalgidek: bitta baza,
prefikssiz Redis kalitlari, eski fayl yo'llari. Shu sabab mavjud MES o'rnatmasi
hech qanday ko'chirishsiz shu kod bilan ishlaydi.
"""

import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from app.core.config import TenancyMode, settings

#: `single` rejimdagi yagona obunachi va `multi` da obunachisiz so'rovlar (health) konteksti
DEFAULT_TENANT = "default"

#: Obunachi kodi = subdomen: kichik lotin harf, raqam, chiziqcha; 2–31 belgi
TENANT_KOD_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}$")

current_tenant: ContextVar[str] = ContextVar("current_tenant", default=DEFAULT_TENANT)


def tenant() -> str:
    return current_tenant.get()


def is_multi() -> bool:
    return settings.TENANCY_MODE == TenancyMode.MULTI


@contextmanager
def use_tenant(kod: str) -> Iterator[None]:
    """Blok ichida `kod` obunachi nomidan ishlash (worker, buyruqlar)."""
    token = current_tenant.set(kod)
    try:
        yield
    finally:
        current_tenant.reset(token)


def tenant_db_name(kod: str) -> str:
    return "t_" + kod.replace("-", "_")


def tkey(key: str) -> str:
    """Redis kalitini obunachiga ajratadi. `single` da kalit o'zgarmaydi (prod Redis holati saqlanadi)."""
    kod = tenant()
    return key if kod == DEFAULT_TENANT else f"t:{kod}:{key}"


def tenant_upload_subdir() -> str | None:
    kod = tenant()
    return None if kod == DEFAULT_TENANT else f"t/{kod}"


def tenant_from_host(host: str) -> str | None:
    """`kod.BASE_DOMAIN[:port]` → `kod`. Asosiy domen, begona domen yoki noto'g'ri kod → None."""
    name = host.split(":", 1)[0].strip().lower().rstrip(".")
    suffix = "." + settings.BASE_DOMAIN.lower()
    if not name.endswith(suffix):
        return None
    kod = name[: -len(suffix)]
    return kod if TENANT_KOD_RE.fullmatch(kod) else None
