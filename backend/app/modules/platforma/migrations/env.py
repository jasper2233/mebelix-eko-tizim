"""Platforma bazasi migratsiyalari — `POSTGRES_DB` (`multi` rejimda platforma bazasi).

Jadval nomi `alembic_version_platforma`: platforma bazasida ish migratsiyalari yo'q, lekin
`single` dan `multi` ga o'tilganda ikkalasi bitta bazada uchrashib qolsa ham aralashmasin.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.db import DATABASE_URL
from app.modules.platforma.models import PlatformBase

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = PlatformBase.metadata
VERSION_TABLE = "alembic_version_platforma"


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, version_table=VERSION_TABLE)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


asyncio.run(run_async_migrations())
