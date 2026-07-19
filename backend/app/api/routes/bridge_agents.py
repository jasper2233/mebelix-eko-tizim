"""Printer agentlari (TZ 2.2.2) — pairing oqimi (podpiska modeli uchun):

1. Admin panelda "Yangi agent" → 8 belgili bir martalik kod (15 daqiqa).
2. Printerli kompyuterda agent (exe) birinchi ishga tushganda kodni so'raydi va
   POST /bridge-agents/pair orqali doimiy tokenga almashtiradi.
3. Token bazada sha256 xesh ko'rinishida; /ws/bridge shu xesh bo'yicha tanidi.

Serverga SSH kirish ham, .env tahriri ham kerak emas. Har printer o'z tokeni
bilan ishlaydi — birini bekor qilish qolganlariga tegmaydi.

Router himoyasiz ulanadi: /pair ochiq bo'lishi shart (agentda sessiya yo'q),
admin endpointlar esa har biri AdminUser bilan o'zi himoyalanadi.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import update

from app.api.deps import AdminUser, SessionDep
from app.core.config import settings
from app.core.exceptions import NotFoundException
from app.crud import crud_bridge_agents, log_action
from app.models import BridgeAgent
from app.schemas.bridge_agents import (
    BridgeAgentCreate,
    BridgeAgentRead,
    BridgePairRequest,
    BridgePairResponse,
)
from app.schemas.common import Message

router = APIRouter(prefix="/bridge-agents", tags=["bridge-agents"])

# I/L/O/0/1 yo'q — telefonda aytganda adashtirmaydi. 30^8 ≈ 6.5e11 kombinatsiya:
# 15 daqiqalik oynada brute-force amalda imkonsiz.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_CODE_LEN = 8
PAIR_TTL = timedelta(minutes=15)


def _new_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LEN))


def _read(agent: BridgeAgent) -> BridgeAgentRead:
    alive = (
        agent.pair_code is not None and agent.pair_expires_at is not None and agent.pair_expires_at > datetime.now(UTC)
    )
    return BridgeAgentRead(
        id=agent.id,
        name=agent.name,
        paired=agent.token_hash is not None,
        pair_code=agent.pair_code if alive else None,
        pair_expires_at=agent.pair_expires_at if alive else None,
        last_seen_at=agent.last_seen_at,
        created_at=agent.created_at,
    )


@router.get("/", response_model=list[BridgeAgentRead], operation_id="read_bridge_agents")
async def read_bridge_agents(db: SessionDep, _: AdminUser) -> list[BridgeAgentRead]:
    agents, _total = await crud_bridge_agents.get_multi(db, limit=100)
    return [_read(a) for a in agents]


@router.post("/", response_model=BridgeAgentRead, status_code=201, operation_id="create_bridge_agent")
async def create_bridge_agent(
    db: SessionDep, current_user: AdminUser, body: BridgeAgentCreate, request: Request
) -> BridgeAgentRead:
    agent = BridgeAgent(name=body.name, pair_code=_new_code(), pair_expires_at=datetime.now(UTC) + PAIR_TTL)
    db.add(agent)
    await db.flush()
    log_action(
        db,
        module="bridge_agents",
        action="created",
        user_id=current_user.id,
        entity_type="bridge_agent",
        entity_id=agent.id,
        message=f"Agent yaratildi, ulanish kodi berildi: {agent.name}",
        ip=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(agent)
    return _read(agent)


@router.post("/{agent_id}/code", response_model=BridgeAgentRead, operation_id="regenerate_bridge_code")
async def regenerate_bridge_code(
    db: SessionDep, current_user: AdminUser, agent_id: int, request: Request
) -> BridgeAgentRead:
    """Yangi ulanish kodi (kod eskirgan yoki kompyuter almashgan holat).

    Eski token bekor bo'ladi — o'sha kompyuter keyingi ulanishda rad etiladi.
    """
    agent = await crud_bridge_agents.get(db, id=agent_id)
    if agent is None:
        raise NotFoundException("Agent topilmadi.")
    agent.token_hash = None
    agent.pair_code = _new_code()
    agent.pair_expires_at = datetime.now(UTC) + PAIR_TTL
    log_action(
        db,
        module="bridge_agents",
        action="code_regenerated",
        user_id=current_user.id,
        entity_type="bridge_agent",
        entity_id=agent.id,
        message=f"Yangi ulanish kodi: {agent.name} (eski token bekor)",
        ip=request.client.host if request.client else None,
    )
    await db.commit()
    await db.refresh(agent)
    return _read(agent)


@router.delete("/{agent_id}", response_model=Message, operation_id="delete_bridge_agent")
async def delete_bridge_agent(db: SessionDep, current_user: AdminUser, agent_id: int, request: Request) -> Message:
    agent = await crud_bridge_agents.get(db, id=agent_id)
    if agent is None:
        raise NotFoundException("Agent topilmadi.")
    log_action(
        db,
        module="bridge_agents",
        action="deleted",
        user_id=current_user.id,
        entity_type="bridge_agent",
        entity_id=agent.id,
        message=f"Agent bekor qilindi: {agent.name}",
        ip=request.client.host if request.client else None,
    )
    await crud_bridge_agents.delete(db, id=agent_id)
    return Message(message="Agent bekor qilindi — ulanish endi rad etiladi.")


@router.post("/pair", response_model=BridgePairResponse, operation_id="pair_bridge_agent")
async def pair_bridge_agent(db: SessionDep, body: BridgePairRequest, request: Request) -> BridgePairResponse:
    """OCHIQ endpoint: agent bir martalik kodni doimiy tokenga almashtiradi.

    Kod topilmasa/muddati o'tgan bo'lsa — bitta umumiy xato (kod bor-yo'qligi
    oshkor qilinmaydi). Atomik UPDATE: bir kodni ikki kompyuter bir vaqtda
    yuborsa faqat bittasi yutadi.
    """
    code = body.code.replace("-", "").replace(" ", "").upper()
    token = secrets.token_hex(24)
    row = None
    if code:
        row = (
            await db.execute(
                update(BridgeAgent)
                .where(
                    BridgeAgent.pair_code == code,
                    BridgeAgent.is_deleted == False,  # noqa: E712
                    BridgeAgent.pair_expires_at > datetime.now(UTC),
                )
                .values(
                    token_hash=hashlib.sha256(token.encode()).hexdigest(),
                    pair_code=None,
                    pair_expires_at=None,
                )
                .returning(BridgeAgent.id, BridgeAgent.name)
            )
        ).first()
    if row is None:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Ulanish kodi noto'g'ri yoki muddati o'tgan.")

    log_action(
        db,
        module="bridge_agents",
        action="paired",
        user_id=None,
        entity_type="bridge_agent",
        entity_id=row.id,
        message=f"Agent ulandi (pairing): {row.name}",
        ip=request.client.host if request.client else None,
    )
    await db.commit()
    return BridgePairResponse(token=token, name=row.name)


@router.get("/download", operation_id="download_bridge_agent")
async def download_bridge_agent() -> FileResponse:
    """Agent dasturi (Windows exe). Sir saqlamaydi — hamma mijozga bir xil fayl,
    shuning uchun auth talab qilinmaydi (monoblok brauzerida sessiya bo'lmasligi mumkin).
    Yangi versiya: exe'ni uploads/agent/ ga qo'yish kifoya."""
    path = Path(settings.UPLOAD_DIR).resolve() / "agent" / "mebelix-agent.exe"
    if not path.is_file():
        raise NotFoundException("Agent fayli serverga hali yuklanmagan.")
    return FileResponse(path, filename="mebelix-agent.exe", media_type="application/octet-stream")
