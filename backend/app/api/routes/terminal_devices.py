"""Chek chiqara oladigan post qurilmalari (monoblok) — ulanish oqimi.

1. Admin /agents sahifasida "Yangi qurilma" → ish markazi tanlanadi, 8 belgili
   bir martalik kod (15 daqiqa) — `bridge_agents` bilan bir xil kod.
2. Postning monoblokida terminal ekranida "Qurilmani ulash" → kod kiritiladi.
   Monoblok shu ish markazining hisobi bilan kirgan bo'lishi SHART: boshqa
   postdagi kompyuter kodni ololmaydi.
3. Brauzerga httpOnly cookie (token) yoziladi, bazada — sha256 xeshi.

Ish markazida ulangan qurilma paydo bo'lishi bilan chek faqat shu cookie'li
brauzerdan chiqadi (`services/terminal_device.py`).
"""

import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select, update

from app.api.deps import AdminUser, SessionDep, client_ip
from app.api.routes.bridge_agents import PAIR_TTL, new_pair_code
from app.api.routes.terminal import TerminalCtx, TerminalUser
from app.core.ws import ws_manager
from app.crud import crud_machines, crud_terminal_devices, log_action
from app.models import Machine, TerminalDevice
from app.schemas.common import Message
from app.schemas.terminal_devices import (
    TerminalDeviceCreate,
    TerminalDevicePairRequest,
    TerminalDevicePairResponse,
    TerminalDeviceRead,
)
from app.services.terminal_device import device_token_hash, machine_locked, set_device_cookie

router = APIRouter(prefix="/terminal-devices", tags=["terminal-devices"])


def _read(device: TerminalDevice, machine_name: str | None) -> TerminalDeviceRead:
    alive = (
        device.pair_code is not None
        and device.pair_expires_at is not None
        and device.pair_expires_at > datetime.now(UTC)
    )
    return TerminalDeviceRead(
        id=device.id,
        name=device.name,
        machine_id=device.machine_id,
        machine_name=machine_name,
        paired=device.token_hash is not None,
        pair_code=device.pair_code if alive else None,
        pair_expires_at=device.pair_expires_at if alive else None,
        last_seen_at=device.last_seen_at,
        paired_at=device.paired_at if device.token_hash is not None else None,
        paired_user_agent=device.paired_user_agent if device.token_hash is not None else None,
        created_at=device.created_at,
    )


async def _machine_name(db: SessionDep, machine_id: int) -> str | None:
    machine = await db.get(Machine, machine_id)
    return machine.name if machine is not None else None


@router.get("/", response_model=list[TerminalDeviceRead], operation_id="read_terminal_devices")
async def read_terminal_devices(db: SessionDep, _: AdminUser) -> list[TerminalDeviceRead]:
    devices, _total = await crud_terminal_devices.get_multi(db, limit=100)
    machines = {m.id: m.name for m in (await db.execute(select(Machine))).scalars()}
    return [_read(d, machines.get(d.machine_id)) for d in devices]


@router.post("/", response_model=TerminalDeviceRead, status_code=201, operation_id="create_terminal_device")
async def create_terminal_device(
    db: SessionDep, current_user: AdminUser, body: TerminalDeviceCreate, request: Request
) -> TerminalDeviceRead:
    machine = await crud_machines.get_or_404(db, "Ish markazi topilmadi.", id=body.machine_id)
    device = TerminalDevice(
        name=body.name,
        machine_id=machine.id,
        pair_code=new_pair_code(),
        pair_expires_at=datetime.now(UTC) + PAIR_TTL,
    )
    db.add(device)
    await db.flush()
    log_action(
        db,
        module="terminal_devices",
        action="created",
        user_id=current_user.id,
        entity_type="terminal_device",
        entity_id=device.id,
        message=f"Chek qurilmasi yaratildi, ulanish kodi berildi: {device.name} -> {machine.name}",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(device)
    # Postning terminali "Qurilmani ulash" tugmasini sahifa yangilanmasdan ko'rsatsin
    await ws_manager.publish("terminal_device.code", {"device_id": device.id, "machine_id": device.machine_id})
    return _read(device, machine.name)


@router.post("/{device_id}/code", response_model=TerminalDeviceRead, operation_id="regenerate_terminal_device_code")
async def regenerate_terminal_device_code(
    db: SessionDep, current_user: AdminUser, device_id: int, request: Request
) -> TerminalDeviceRead:
    """Yangi ulanish kodi (monoblok almashgan yoki brauzer tozalangan).

    Eski token DARHOL bekor: o'sha brauzer keyingi chekda rad etiladi.
    """
    device = await crud_terminal_devices.get_or_404(db, "Qurilma topilmadi.", id=device_id)
    device.token_hash = None
    device.pair_code = new_pair_code()
    device.pair_expires_at = datetime.now(UTC) + PAIR_TTL
    device.last_seen_at = None
    device.paired_at = None
    device.paired_user_agent = None
    log_action(
        db,
        module="terminal_devices",
        action="code_regenerated",
        user_id=current_user.id,
        entity_type="terminal_device",
        entity_id=device.id,
        message=f"Chek qurilmasiga yangi kod: {device.name} (eski ulanish bekor)",
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(device)
    await ws_manager.publish("terminal_device.code", {"device_id": device.id, "machine_id": device.machine_id})
    return _read(device, await _machine_name(db, device.machine_id))


@router.delete("/{device_id}", response_model=Message, operation_id="delete_terminal_device")
async def delete_terminal_device(db: SessionDep, current_user: AdminUser, device_id: int, request: Request) -> Message:
    device = await crud_terminal_devices.get_or_404(db, "Qurilma topilmadi.", id=device_id)
    log_action(
        db,
        module="terminal_devices",
        action="deleted",
        user_id=current_user.id,
        entity_type="terminal_device",
        entity_id=device.id,
        message=f"Chek qurilmasi o'chirildi: {device.name}",
        ip=client_ip(request),
    )
    machine_id = device.machine_id
    await crud_terminal_devices.delete(db, id=device_id)
    await ws_manager.publish("terminal_device.deleted", {"device_id": device_id, "machine_id": machine_id})
    # Cheklov ULANGAN qurilmalar bilan yashaydi: oxirgisi ketsa u o'chadi — buni
    # aytamiz, aks holda admin "endi faqat monoblokdan" deb o'ylab qolardi
    machine = await db.get(Machine, machine_id)
    if machine is not None and not await machine_locked(db, machine):
        return Message(
            message=f"Qurilma o'chirildi. {machine.name} ishida ulangan qurilma qolmadi — "
            "chek endi har qurilmadan chiqadi."
        )
    return Message(message="Qurilma o'chirildi — chek faqat qolgan ulangan qurilmadan chiqadi.")


@router.post("/pair", response_model=TerminalDevicePairResponse, operation_id="pair_terminal_device")
async def pair_terminal_device(
    db: SessionDep,
    user: TerminalUser,
    ctx: TerminalCtx,
    body: TerminalDevicePairRequest,
    request: Request,
    response: Response,
) -> TerminalDevicePairResponse:
    """Monoblok bir martalik kodni cookie'ga almashtiradi.

    Kod faqat O'Z ish markazida ishlaydi: arra kodi rover monoblokida kiritilsa
    rad etiladi — aks holda noto'g'ri kompyuter arraning chekini chiqarardi.
    Atomik UPDATE: bir kodni ikki brauzer bir vaqtda yuborsa faqat bittasi yutadi.
    """
    machine, _post = ctx
    code = body.code.replace("-", "").replace(" ", "").upper()
    token = secrets.token_hex(24)
    now = datetime.now(UTC)
    user_agent = (request.headers.get("user-agent") or "")[:200]
    row = None
    if code:
        row = (
            await db.execute(
                update(TerminalDevice)
                .where(
                    TerminalDevice.pair_code == code,
                    TerminalDevice.machine_id == machine.id,
                    TerminalDevice.is_deleted == False,  # noqa: E712
                    TerminalDevice.pair_expires_at > now,
                )
                .values(
                    token_hash=device_token_hash(token),
                    pair_code=None,
                    pair_expires_at=None,
                    last_seen_at=now,
                    paired_at=now,
                    paired_user_agent=user_agent or None,
                )
                .returning(TerminalDevice.id, TerminalDevice.name)
            )
        ).first()
    if row is None:
        await db.rollback()
        # Kod BOSHQA ish markaziniki bo'lsa buni aytamiz — admin kodni noto'g'ri
        # postga aytgan bo'lsa "noto'g'ri kod" deyish uni adashtirardi
        other = None
        if code:
            other = (
                await db.execute(
                    select(Machine.name)
                    .join(TerminalDevice, TerminalDevice.machine_id == Machine.id)
                    .where(
                        TerminalDevice.pair_code == code,
                        TerminalDevice.is_deleted == False,  # noqa: E712
                        TerminalDevice.pair_expires_at > now,
                    )
                )
            ).scalar_one_or_none()
        if other is not None:
            raise HTTPException(
                status_code=400,
                detail=f"Bu kod «{other}» ish markazi uchun — uni o'sha postning monoblokida kiriting.",
            )
        raise HTTPException(status_code=400, detail="Ulanish kodi noto'g'ri yoki muddati o'tgan.")

    log_action(
        db,
        module="terminal_devices",
        action="paired",
        user_id=user.id,
        entity_type="terminal_device",
        entity_id=row.id,
        message=f"Chek qurilmasi ulandi: {row.name} -> {machine.name}",
        # Kod qaysi brauzerda kiritilgani — telefonga ulab olingan bo'lsa admin ko'radi
        meta={"user_agent": user_agent},
        ip=client_ip(request),
    )
    await db.commit()
    set_device_cookie(response, token)
    await ws_manager.publish("terminal_device.paired", {"device_id": row.id, "machine_id": machine.id})
    return TerminalDevicePairResponse(name=row.name, machine_name=machine.name)
