"""Chek chiqara oladigan qurilma — brauzer cookie'si bo'yicha tekshiruv.

Nega kerak: terminal hisobi ODAMGA bog'langan (`resolve_terminal` postni
roldan, ish markazini hisobdan oladi), ya'ni arrachi telefondan o'z hisobiga
kirsa ham chek postdagi printerdan chiqadi. 2026-09-24 da shu yo'l bilan bitta
detalning ikki bir xil cheki chiqib, ikki xil detalga yopishtirilgan.

Qoida: ish markazida kamida bitta ULANGAN (`token_hash` bor) qurilma bo'lsa,
chek faqat shu qurilmalardan birining cookie'si bor brauzerdan chiqadi.
Ulangan qurilmasi yo'q ish markazida cheklov YO'Q — joriy qilish bosqichma-
bosqich, ulanmagan post ishini to'xtatmaydi. Kod berilgan, lekin hali
kiritilmagan qurilma ham cheklov yoqmaydi: aks holda admin kodni yaratgan
lahzadan monoblokda kiritilguncha post chek chiqara olmasdi.

Faqat CHEK CHIQARISH to'siladi. Skan, xarita, smena — telefondan ham ishlayveradi.
"""

import hashlib
import hmac
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import EnvironmentOption, settings
from app.crud import log_action
from app.models import Machine, TerminalDevice, User
from app.services.scanning import ScanRejected

DEVICE_COOKIE = "terminal_device"
# Chrome cookie muddatini 400 kun bilan cheklaydi. `/terminal/context` har
# ochilishda cookie'ni yangilaydi, ya'ni ishlab turgan monoblokda u tugamaydi.
DEVICE_COOKIE_MAX_AGE = 400 * 24 * 3600
# `last_seen_at` har chek/kontekst so'rovida yozilmasin — panelga daqiqa aniqligi yetadi
_SEEN_EVERY = timedelta(minutes=1)


def device_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def set_device_cookie(response: Response, token: str) -> None:
    """httpOnly: sahifadagi skript tokenni o'qiy olmaydi. `path` — butun sayt:
    API `/api/v1/...` da, lekin cookie nomi auth cookie'lari bilan to'qnashmaydi."""
    response.set_cookie(
        key=DEVICE_COOKIE,
        value=token,
        httponly=True,
        secure=settings.ENVIRONMENT != EnvironmentOption.LOCAL,
        samesite="strict",
        max_age=DEVICE_COOKIE_MAX_AGE,
    )


async def _paired_devices(db: AsyncSession, machine: Machine) -> Sequence[TerminalDevice]:
    return (
        (
            await db.execute(
                select(TerminalDevice).where(
                    TerminalDevice.machine_id == machine.id,
                    TerminalDevice.token_hash.is_not(None),
                    TerminalDevice.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )


async def machine_locked(db: AsyncSession, machine: Machine) -> bool:
    """Cheklov yoqilganmi — ish markazida kamida bitta ULANGAN qurilma bormi."""
    return bool(await _paired_devices(db, machine))


async def print_device(db: AsyncSession, request: Request, machine: Machine) -> tuple[bool, TerminalDevice | None]:
    """(cheklov yoqilganmi, shu brauzerning qurilmasi).

    Cheklov = ish markazida kamida bitta ulangan qurilma. Qurilma = cookie
    tokeni shu ish markazining ulangan qurilmalaridan biriga mos kelsa.
    """
    devices = await _paired_devices(db, machine)
    if not devices:
        return False, None
    raw = request.cookies.get(DEVICE_COOKIE)
    if not raw:
        return True, None
    h = device_token_hash(raw)
    return True, next((d for d in devices if d.token_hash and hmac.compare_digest(d.token_hash, h)), None)


async def pairing_open(db: AsyncSession, machine: Machine) -> bool:
    """Ish markazida kodi hali amal qilayotgan (kiritilmagan) qurilma bormi."""
    return (
        await db.execute(
            select(TerminalDevice.id)
            .where(
                TerminalDevice.machine_id == machine.id,
                TerminalDevice.pair_code.is_not(None),
                TerminalDevice.pair_expires_at > datetime.now(UTC),
                TerminalDevice.is_deleted == False,  # noqa: E712
            )
            .limit(1)
        )
    ).first() is not None


async def touch_device(db: AsyncSession, device: TerminalDevice) -> None:
    """`last_seen_at` — panel "oxirgi marta" ustuni uchun; daqiqasiga bir martadan ko'p yozilmaydi."""
    now = datetime.now(UTC)
    if device.last_seen_at is None or now - device.last_seen_at > _SEEN_EVERY:
        await db.execute(update(TerminalDevice).where(TerminalDevice.id == device.id).values(last_seen_at=now))


async def require_print_device(db: AsyncSession, request: Request, user: User, machine: Machine | None) -> None:
    """Chek chiqarishdan OLDIN — hech narsa yozilmasdan va navbatga qo'yilmasdan.

    Rad etilsa (E011) urinish audit-logga yoziladi va commit qilinadi — admin
    Loglar sahifasida kim qaysi qurilmadan chek chiqarmoqchi bo'lganini ko'radi.
    `log_rejected_scan` naqshi: rollback + log + commit, HTTP xato esa chaqiruvchida.

    Ish markazi aniqlanmasa tekshirilmaydi: u holda chek baribir chiqmaydi
    (`require_printer(None)` -> 422), bu yerda ikkinchi xato berish ortiqcha.
    """
    if machine is None:
        return
    locked, device = await print_device(db, request, machine)
    if not locked:
        return
    if device is not None:
        await touch_device(db, device)
        return
    exc = ScanRejected(
        "E011",
        f"Chekni faqat {machine.name} monoblokidan chiqarish mumkin — bu qurilma "
        "(telefon yoki boshqa kompyuter) chek chiqarishga ulanmagan.",
    )
    # Rollback obyektlarni expire qiladi — kerakli qiymatlar OLDIN olinadi
    user_id, kim, machine_id = user.id, user.name or user.username, machine.id
    await db.rollback()
    log_action(
        db,
        module="print",
        action="device_rejected",
        user_id=user_id,
        entity_type="machine",
        entity_id=machine_id,
        message=f"Chek rad etildi — ulanmagan qurilma: {kim}",
        meta={"code": exc.code, "user_agent": (request.headers.get("user-agent") or "")[:200]},
        # `deps.client_ip` bilan bir xil; servis api qatlamini import qilmaydi
        ip=request.client.host if request.client else None,
    )
    await db.commit()
    raise exc
