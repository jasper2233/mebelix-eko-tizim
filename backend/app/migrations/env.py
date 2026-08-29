import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.db import DATABASE_URL, Base

config = context.config

# URL alembic.ini da yo'q (parol repoga tushmasin) — ilova ishlatadigan aynan shu
# satrni olamiz, ya'ni driver/escaping tuzatishi migratsiyaga ham o'z-o'zidan tegadi.
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# app/models/__init__.py barcha jadval modullarini statik import qiladi — metadata shu bilan to'ladi.
import app.models  # noqa: F401, E402

target_metadata = Base.metadata

#: Migratsiyasi prodga QO'LLANGAN, lekin modeli olib tashlangan obyektlar — OEE va
#: materiallar ombori modullari (`docs/04-backend-data.md` §4.4). Bazada bo'sh turadi
#: va ATAYLAB drop qilinmaydi: prodda qo'llangan migratsiyani orqaga qaytarish
#: deployni yiqitardi. Autogenerate/`alembic check` ularni har safar "drift" deb
#: ko'rsatmasin — aks holda haqiqiy drift shovqin ichida ko'rinmay qoladi.
#: Modul qaytarilsa yoki jadval haqiqatan drop qilinsa — shu ro'yxatdan olib tashlanadi.
LEGACY_TABLES = frozenset({"machine_stop", "payment", "sale", "stock_item", "stock_move", "stop_reason"})
LEGACY_COLUMNS = frozenset(
    {
        ("machine", "capacity"),
        ("machine", "capacity_unit"),
        ("machine", "ideal_rate"),
        ("machine", "planned_minutes_per_day"),
        ("part_instance", "cut_meters"),
        ("post", "color"),
        ("post", "icon"),
    }
)


def include_object(obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any) -> bool:
    """Yuqoridagi yetim obyektlarni autogenerate solishtiruvidan chiqaradi."""
    if type_ == "table":
        return name not in LEGACY_TABLES
    if type_ == "column" and reflected and compare_to is None:
        return (obj.table.name, name) not in LEGACY_COLUMNS
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
