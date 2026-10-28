from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass

from .config import settings


class Base(DeclarativeBase, MappedAsDataclass):
    pass


DATABASE_URL = f"{settings.POSTGRES_ASYNC_PREFIX}{settings.POSTGRES_URI}"

# `statement_timeout` ulanish ochilganda o'rnatiladi (asyncpg `server_settings`): sex jarayonida
# qotib qolgan so'rov 3 s da uziladi va pulni band qilib turmaydi. Alembic o'z engine'ini
# quradi (`migrations/env.py`) — migratsiyalarga bu cheklov tegmaydi.
_connect_args: dict[str, dict[str, str]] = {}
if settings.STATEMENT_TIMEOUT_MS > 0:
    _connect_args["server_settings"] = {"statement_timeout": str(settings.STATEMENT_TIMEOUT_MS)}

async_engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

local_session = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


async def async_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with local_session() as db:
        yield db
