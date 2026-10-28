"""Obunachilarni boshqarish (`multi` rejim, EKO TIZIM TZ §2.4).

    python -m app.commands.platforma init                       # platforma bazasi migratsiyasi
    python -m app.commands.platforma create <kod> "<nomi>" --admin-phone +998... --admin-password ...
    python -m app.commands.platforma migrate-all                # har obunachi bazasini head'ga
    python -m app.commands.platforma list
    python -m app.commands.platforma status <kod> faol|toxtatilgan

Obunachi yaratish tartibi: baza → migratsiya → admin va standart postlar → platforma qatori.
Qator ENG OXIRIDA yoziladi: yarim tayyor obunachi subdomendan ochilib qolmasin. Biror qadam
yiqilsa yaratilgan baza o'chiriladi.
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

from app.commands.create_first_superuser import create_first_user
from app.commands.seed_defaults import seed_defaults
from app.core.db import (
    async_engine,
    dispose_tenant_engine,
    dispose_tenant_engines,
    local_session,
)
from app.core.tenancy import TENANT_KOD_RE, tenant_db_name, use_tenant
from app.modules.platforma import service as platforma
from app.modules.platforma.service import FAOL, MODULLAR, TOXTATILGAN

BACKEND = Path(__file__).resolve().parents[2]


def _alembic(*args: str) -> int:
    """Alembic alohida jarayonda: uning env.py o'zi `asyncio.run` qiladi (ichma-ich loop bo'lmaydi)."""
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND).returncode


def cmd_init() -> int:
    return _alembic("-c", "alembic_platforma.ini", "upgrade", "head")


async def _database_sql(sql: str) -> None:
    # CREATE/DROP DATABASE tranzaksiya ichida ishlamaydi
    async with async_engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text(sql))


async def cmd_create(args: argparse.Namespace) -> int:
    kod: str = args.kod
    if not TENANT_KOD_RE.fullmatch(kod):
        print(f"Kod noto'g'ri: {kod!r} — kichik lotin harf bilan boshlansin, 2–31 belgi (a-z, 0-9, -)")
        return 2
    modules = [m.strip() for m in args.modules.split(",") if m.strip()]
    if unknown := set(modules) - set(MODULLAR):
        print(f"Noma'lum modul: {', '.join(sorted(unknown))}. Mavjud: {', '.join(MODULLAR)}")
        return 2
    if await platforma.tenant_exists(kod):
        print(f"{kod} allaqachon bor")
        return 1

    db_name = tenant_db_name(kod)
    await _database_sql(f'CREATE DATABASE "{db_name}"')
    try:
        if _alembic("-x", f"tenant={kod}", "upgrade", "head") != 0:
            raise RuntimeError("migratsiya yiqildi")
        with use_tenant(kod):
            async with local_session() as session:
                await create_first_user(
                    session,
                    name=args.admin_name,
                    phone=args.admin_phone,
                    username=args.admin_username,
                    password=args.admin_password,
                )
            await seed_defaults()
        await platforma.add_tenant(kod, args.nomi, modules)
    except BaseException:
        # Ochiq ulanish qolsa DROP DATABASE rad etiladi
        await dispose_tenant_engine(kod)
        await _database_sql(f'DROP DATABASE IF EXISTS "{db_name}"')
        print(f"{kod} yaratilmadi — {db_name} bazasi o'chirildi")
        raise
    print(f"{kod} yaratildi: baza {db_name}, modullar {', '.join(modules) or '—'}")
    return 0


async def cmd_migrate_all() -> int:
    kods = [kod for kod, *_ in await platforma.all_tenants()]
    failed = [kod for kod in kods if _alembic("-x", f"tenant={kod}", "upgrade", "head") != 0]
    print(f"Migratsiya: {len(kods) - len(failed)}/{len(kods)} obunachi tayyor")
    if failed:
        print("Yiqilganlar:", ", ".join(failed))
    return 1 if failed else 0


async def cmd_list() -> int:
    for kod, holat, modules, nomi in await platforma.all_tenants():
        print(f"{kod:<20} {holat:<12} {','.join(modules):<40} {nomi}")
    return 0


async def cmd_status(kod: str, holat: str) -> int:
    if not await platforma.set_status(kod, holat):
        print(f"{kod} topilmadi")
        return 1
    print(f"{kod}: {holat} (API jarayonlari keshi {kod} uchun TENANT_CACHE_SECONDS ichida yangilanadi)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="platforma")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    c = sub.add_parser("create")
    c.add_argument("kod")
    c.add_argument("nomi")
    c.add_argument("--modules", default=",".join(MODULLAR))
    c.add_argument("--admin-name", default="Administrator")
    c.add_argument("--admin-username", default="admin")
    c.add_argument("--admin-phone", required=True)
    c.add_argument("--admin-password", required=True)
    sub.add_parser("migrate-all")
    sub.add_parser("list")
    s = sub.add_parser("status")
    s.add_argument("kod")
    s.add_argument("holat", choices=[FAOL, TOXTATILGAN])
    args = parser.parse_args()

    if args.cmd == "init":
        return cmd_init()

    async def run() -> int:
        try:
            if args.cmd == "create":
                return await cmd_create(args)
            if args.cmd == "migrate-all":
                return await cmd_migrate_all()
            if args.cmd == "list":
                return await cmd_list()
            return await cmd_status(args.kod, args.holat)
        finally:
            await dispose_tenant_engines()
            await async_engine.dispose()

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
