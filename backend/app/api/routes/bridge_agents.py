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
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select, update

from app.api.deps import AdminUser, SessionDep, client_ip
from app.core.exceptions import NotFoundException
from app.core.ws import ws_manager
from app.crud import crud_bridge_agents, log_action
from app.models import BridgeAgent, Machine, Post
from app.schemas.bridge_agents import (
    BridgeAgentCreate,
    BridgeAgentRead,
    BridgeAgentUpdate,
    BridgePairRequest,
    BridgePairResponse,
    BridgeScanRequest,
)
from app.schemas.common import Message
from app.schemas.terminal import ScanResult
from app.services.scanning import (
    ScanRejected,
    crew_sessions,
    finalize_scan,
    log_rejected_scan,
    record_scan_at,
)

router = APIRouter(prefix="/bridge-agents", tags=["bridge-agents"])

# I/L/O/0/1 yo'q — telefonda aytganda adashtirmaydi. 31^8 ≈ 8.5e11 kombinatsiya:
# 15 daqiqalik oynada brute-force amalda imkonsiz.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_CODE_LEN = 8
PAIR_TTL = timedelta(minutes=15)


def _new_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LEN))


def _read(agent: BridgeAgent, machine_name: str | None = None) -> BridgeAgentRead:
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
        machine_id=agent.machine_id,
        machine_name=machine_name,
        version=agent.version,
        can_print=agent.can_print,
    )


@router.get("/", response_model=list[BridgeAgentRead], operation_id="read_bridge_agents")
async def read_bridge_agents(db: SessionDep, _: AdminUser) -> list[BridgeAgentRead]:
    agents, _total = await crud_bridge_agents.get_multi(db, limit=100)
    machines = {
        m.id: m.name
        for m in (await db.execute(select(Machine).where(Machine.is_deleted == False))).scalars()  # noqa: E712
    }
    return [_read(a, machines.get(a.machine_id) if a.machine_id else None) for a in agents]


@router.patch("/{agent_id}", response_model=BridgeAgentRead, operation_id="update_bridge_agent")
async def update_bridge_agent(
    db: SessionDep, current_user: AdminUser, agent_id: int, body: BridgeAgentUpdate, request: Request
) -> BridgeAgentRead:
    """Stanok bog'lash (skan-forvard) va chek-chiqarish belgisi. Maydonlar
    alohida yuboriladi — berilmagani tegilmaydi (exclude_unset)."""
    agent = await crud_bridge_agents.get_or_404(db, "Agent topilmadi.", id=agent_id)
    sent = body.model_dump(exclude_unset=True)
    machine_name: str | None = None
    if "machine_id" in sent:
        if body.machine_id is not None:
            machine = await db.get(Machine, body.machine_id)
            if machine is None or machine.is_deleted:
                raise NotFoundException("Stanok topilmadi.")
            machine_name = machine.name
        agent.machine_id = body.machine_id
        log_action(
            db,
            module="bridge_agents",
            action="machine_linked",
            user_id=current_user.id,
            entity_type="bridge_agent",
            entity_id=agent.id,
            message=f"Agent stanokka bog'landi: {agent.name} -> {machine_name or '—'}",
            ip=client_ip(request),
        )
    if body.can_print is not None:
        agent.can_print = body.can_print
        log_action(
            db,
            module="bridge_agents",
            action="can_print_changed",
            user_id=current_user.id,
            entity_type="bridge_agent",
            entity_id=agent.id,
            message=f"Chek chiqarish: {agent.name} -> {'ha' if body.can_print else 'yoq'}",
            ip=client_ip(request),
        )
    await db.commit()
    await db.refresh(agent)
    if machine_name is None and agent.machine_id is not None:
        m = await db.get(Machine, agent.machine_id)
        machine_name = m.name if m else None
    return _read(agent, machine_name)


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
        ip=client_ip(request),
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
    agent = await crud_bridge_agents.get_or_404(db, "Agent topilmadi.", id=agent_id)
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
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(agent)
    return _read(agent)


@router.delete("/{agent_id}", response_model=Message, operation_id="delete_bridge_agent")
async def delete_bridge_agent(db: SessionDep, current_user: AdminUser, agent_id: int, request: Request) -> Message:
    agent = await crud_bridge_agents.get_or_404(db, "Agent topilmadi.", id=agent_id)
    log_action(
        db,
        module="bridge_agents",
        action="deleted",
        user_id=current_user.id,
        entity_type="bridge_agent",
        entity_id=agent.id,
        message=f"Agent bekor qilindi: {agent.name}",
        ip=client_ip(request),
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
        ip=client_ip(request),
    )
    await db.commit()
    # Kod terilishi bilan admin sahifasi darhol yangilanadi (pollingni kutmasdan)
    await ws_manager.publish("bridge.paired", {"agent_id": row.id})
    return BridgePairResponse(token=token, name=row.name)


@router.post("/scan", response_model=ScanResult, operation_id="bridge_scan")
async def bridge_scan(
    db: SessionDep,
    body: BridgeScanRequest,
    authorization: str = Header(default=""),
) -> ScanResult:
    """Skan-forvard (TZ 12.5): stanok skaneri o'qigan QR agent orqali MES'ga ham yoziladi.

    Auth — agentning doimiy tokeni (Bearer). Skan agentga bog'langan stanokning
    AKTIV sessiyasi nomidan yoziladi (monoblokda operator kirgan bo'lishi shart) —
    hisob-kitob odatdagi skan bilan bir xil yo'ldan o'tadi.
    """
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Token yo'q.")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    agent = (
        await db.execute(
            select(BridgeAgent).where(
                BridgeAgent.token_hash == token_hash,
                BridgeAgent.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=401, detail="Token bekor qilingan.")
    if agent.machine_id is None:
        raise HTTPException(
            status_code=409,
            detail="Agent stanokka bog'lanmagan — admin panelda Printer agentlar bo'limida stanok tanlang.",
        )
    machine = await db.get(Machine, agent.machine_id)
    if machine is None or machine.is_deleted:
        raise HTTPException(status_code=409, detail="Bog'langan stanok topilmadi.")
    post = await db.get(Post, machine.post_id)
    if post is None:
        raise HTTPException(status_code=409, detail="Stanok posti topilmadi.")
    # Terminal bilan bir xil qoida: 12 soatlik smena muddati stanok skanida ham
    # amal qiladi (`crew_sessions` muddati o'tganini o'zi yopadi). Brigadadan
    # LANGAR smena olinadi — `active_session` ham aynan shunday tanlaydi.
    crew = await crew_sessions(db, machine.id)
    session = crew[0] if crew else None
    if session is None:
        raise HTTPException(
            status_code=409,
            detail="Terminalda aktiv sessiya yo'q — operator monoblokda tizimga kirgan bo'lishi kerak.",
        )

    try:
        outcome = await record_scan_at(
            db,
            machine=machine,
            post=post,
            session=session,
            qr_text=body.qr_text,
            client_event_id=body.client_event_id or uuid.uuid4().hex,
        )
    except ScanRejected as exc:
        # Stanokdagi rad etilgan skan operatorga ko'rinmaydi — hech bo'lmasa logda qolsin
        await log_rejected_scan(
            db, exc, body.qr_text, source=f" (stanok, {agent.name})", meta_extra={"agent_id": agent.id}
        )
        raise HTTPException(status_code=422, detail={"code": exc.code, "message": exc.message}) from None

    return await finalize_scan(db, outcome, source=f" (stanok, {agent.name})", agent_id=agent.id)


# "Agentni yuklab olish" endpointi olib tashlangan (2026-08-02): u diskdagi
# eski exe'ni berib adashtirardi — deploy uploads/ ni yangilamaydi. Agent exe
# qo'lda tarqatiladi (bridge-agent/README.md).
