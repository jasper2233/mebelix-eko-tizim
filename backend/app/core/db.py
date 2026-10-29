from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass

from .config import settings
from .tenancy import DEFAULT_TENANT, tenant, tenant_db_name


class Base(DeclarativeBase, MappedAsDataclass):
    pass


DATABASE_URL = f"{settings.POSTGRES_ASYNC_PREFIX}{settings.POSTGRES_URI}"

# `statement_timeout` ulanish ochilganda o'rnatiladi (asyncpg `server_settings`): sex jarayonida
# qotib qolgan so'rov 3 s da uziladi va pulni band qilib turmaydi. Alembic o'z engine'ini
# quradi (`migrations/env.py`) — migratsiyalarga bu cheklov tegmaydi.
# `lock_timeout` va `idle_in_transaction_session_timeout` (EKO 2.4, prototip qoidasi): qulf kutish
# cheklangan — navbat qotib qolmaydi; osilib qolgan tranzaksiya qulflarni abadiy ushlab turmaydi.
_server_settings: dict[str, str] = {}
if settings.STATEMENT_TIMEOUT_MS > 0:
    _server_settings["statement_timeout"] = str(settings.STATEMENT_TIMEOUT_MS)
if settings.DB_LOCK_TIMEOUT_MS > 0:
    _server_settings["lock_timeout"] = str(settings.DB_LOCK_TIMEOUT_MS)
if settings.DB_IDLE_TX_TIMEOUT_MS > 0:
    _server_settings["idle_in_transaction_session_timeout"] = str(settings.DB_IDLE_TX_TIMEOUT_MS)
_connect_args: dict[str, dict[str, str]] = {"server_settings": _server_settings} if _server_settings else {}


def _engine(url: str, pool_size: int, max_overflow: int) -> AsyncEngine:
    return create_async_engine(
        url,
        echo=False,
        future=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,
        connect_args=_connect_args,
    )


#: `single` — ish bazasi; `multi` — platforma bazasi (obunachilar ro'yxati, health)
async_engine = _engine(DATABASE_URL, settings.DB_POOL_SIZE, settings.DB_MAX_OVERFLOW)

#: Obunachi engine'lari — birinchi so'rovda yaratiladi va jarayon umri davomida turadi.
#: Har biri kichik pul (`TENANT_DB_POOL_SIZE`), ulanishlar soni PgBouncer'da cheklanadi.
_tenant_engines: dict[str, AsyncEngine] = {}


def engine_for(kod: str) -> AsyncEngine:
    if kod == DEFAULT_TENANT:
        return async_engine
    engine = _tenant_engines.get(kod)
    if engine is None:
        url = f"{settings.POSTGRES_ASYNC_PREFIX}{settings.postgres_uri_for(tenant_db_name(kod))}"
        engine = _engine(url, settings.TENANT_DB_POOL_SIZE, settings.TENANT_DB_MAX_OVERFLOW)
        _tenant_engines[kod] = engine
    return engine


def platform_session() -> AsyncSession:
    """Platforma bazasi (`multi`) — obunachidan qat'i nazar."""
    return AsyncSession(bind=async_engine, expire_on_commit=False)


class _TenantSessionFactory:
    """`async_sessionmaker` o'rnida: `local_session()` JORIY obunachi bazasiga sessiya beradi.

    Chaqiruvlar (`async with local_session() as db`) o'zgarmadi — obunachi ContextVar'dan olinadi.
    """

    def __call__(self) -> AsyncSession:
        return AsyncSession(bind=engine_for(tenant()), expire_on_commit=False)


local_session = _TenantSessionFactory()


async def async_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with local_session() as db:
        yield db


async def dispose_tenant_engine(kod: str) -> None:
    if (engine := _tenant_engines.pop(kod, None)) is not None:
        await engine.dispose()


async def dispose_tenant_engines() -> None:
    for engine in list(_tenant_engines.values()):
        await engine.dispose()
    _tenant_engines.clear()
