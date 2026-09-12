"""Printer agentlari — pairing oqimi (podpiska modeli uchun):

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
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import select, update

from app.api.deps import AdminUser, SessionDep, client_ip
from app.core.config import settings
from app.core.exceptions import DuplicateValueException, NotFoundException
from app.core.ws import ws_manager
from app.crud import crud_bridge_agents, crud_machines, log_action
from app.models import BridgeAgent, Machine, Post
from app.schemas.bridge_agents import (
    AgentRelease,
    BridgeAgentCreate,
    BridgeAgentRead,
    BridgeAgentUpdate,
    BridgeLogPush,
    BridgePairRequest,
    BridgePairResponse,
    BridgeScanRequest,
)
from app.schemas.common import Message
from app.schemas.terminal import ScanResult
from app.services.scanning import (
    ScanRejected,
    active_session,
    finalize_scan,
    log_rejected_scan,
    record_scan_at,
    scan_error,
)
from app.tasks import agent_revoked_key, print_queue_key

router = APIRouter(prefix="/bridge-agents", tags=["bridge-agents"])

# I/L/O/0/1 yo'q — telefonda aytganda adashtirmaydi. 31^8 ≈ 8.5e11 kombinatsiya:
# 15 daqiqalik oynada brute-force amalda imkonsiz.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

# Agent loglari REDISDA, jadvalda emas: diagnostika uchun oxirgi N satr kerak,
# tarix emas. Ro'yxat o'zi kesiladi (LTRIM), ya'ni o'sishni boshqarish shart
# emas va migratsiya ham kerak bo'lmaydi. 7 kundan keyin o'zi yo'qoladi —
# ulanmagan agentning eski loglari bo'sh joy egallab yotmasin.
AGENT_LOG_KEY = "mes:agent:log:{}"
AGENT_LOG_KEEP = 200
AGENT_LOG_TTL = 7 * 24 * 3600
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


async def _ensure_machine_free(db: SessionDep, machine_id: int, exclude_id: int | None = None) -> None:
    """Bitta ish markazi — bitta agent. Ikki agent bitta ish markazida bo'lsa cheklar
    ular orasida bo'linib, yarmi o'lik navbatda qolardi (`printer_agent` bittasini tanlaydi)."""
    query = select(BridgeAgent.name).where(
        BridgeAgent.machine_id == machine_id,
        BridgeAgent.is_deleted == False,  # noqa: E712
    )
    if exclude_id is not None:
        query = query.where(BridgeAgent.id != exclude_id)
    band = (await db.execute(query)).scalar_one_or_none()
    if band is not None:
        raise DuplicateValueException(f"Bu ish markaziga «{band}» agenti allaqachon bog'langan — avval uni uzing.")


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
    """Ish markazi bog'lash (skan-forvard) va chek-chiqarish belgisi. Maydonlar
    alohida yuboriladi — berilmagani tegilmaydi (exclude_unset)."""
    agent = await crud_bridge_agents.get_or_404(db, "Agent topilmadi.", id=agent_id)
    sent = body.model_dump(exclude_unset=True)
    machine_name: str | None = None
    if "machine_id" in sent:
        if body.machine_id is not None:
            await _ensure_machine_free(db, body.machine_id, exclude_id=agent.id)
            machine = await crud_machines.get_or_404(db, "Ish markazi topilmadi.", id=body.machine_id)
            machine_name = machine.name
        agent.machine_id = body.machine_id
        linked = body.machine_id is not None
        log_action(
            db,
            module="bridge_agents",
            action="machine_linked" if linked else "machine_unlinked",
            user_id=current_user.id,
            entity_type="bridge_agent",
            entity_id=agent.id,
            message=(
                f"Agent ish markaziga bog'landi: {agent.name} -> {machine_name}"
                if linked
                else f"Agent ish markazidan uzildi: {agent.name}"
            ),
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
    machine = None
    if body.machine_id is not None:
        machine = await crud_machines.get_or_404(db, "Ish markazi topilmadi.", id=body.machine_id)
        await _ensure_machine_free(db, body.machine_id)
    agent = BridgeAgent(
        name=body.name,
        machine_id=body.machine_id,
        pair_code=_new_code(),
        pair_expires_at=datetime.now(UTC) + PAIR_TTL,
    )
    db.add(agent)
    await db.flush()
    log_action(
        db,
        module="bridge_agents",
        action="created",
        user_id=current_user.id,
        entity_type="bridge_agent",
        entity_id=agent.id,
        message=(
            f"Agent yaratildi, ulanish kodi berildi: {agent.name}"
            + (f" -> {machine.name}" if machine else " (ish markazisiz — faqat beyjik chop etish)")
        ),
        ip=client_ip(request),
    )
    await db.commit()
    await db.refresh(agent)
    return _read(agent, machine.name if machine else None)


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
    # Panel DARHOL "Uzilgan" ko'rsatsin: `last_seen_at` eski qiymatida qolsa
    # 6 daqiqalik onlayn oynasi tufayli "Ulandi" deb yolg'on ko'rsatardi.
    agent.last_seen_at = None
    await _revoke_live_connection(agent.id)
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
    # Navbatda qolgan cheklar: agent o'chirilgach ularni HECH KIM olmaydi
    # (har chek aniq agentga manzillangan) — kalit jimgina abadiy qolardi.
    # Nechta chek bekor bo'lganini AYTAMIZ, aks holda operator "chek yuborildi"
    # xabarini ko'rib qog'oz kutib qolardi.
    qolgan = await _revoke_live_connection(agent.id, purge_queue=True)
    await crud_bridge_agents.delete(db, id=agent_id)
    if qolgan:
        return Message(message=f"Agent bekor qilindi — ulanish rad etiladi. Navbatdagi {qolgan} ta chek bekor qilindi.")
    return Message(message="Agent bekor qilindi — ulanish endi rad etiladi.")


async def _revoke_live_connection(agent_id: int, *, purge_queue: bool = False) -> int:
    """Jonli WS ulanishni darhol uzish uchun Redis bayrog'i; ixtiyoriy — navbatni
    tozalash. Qaytaradi: tozalangan cheklar soni (`purge_queue` bo'lmasa 0).

    `/ws/bridge` sikli har iteratsiyada shu bayroqni o'qiydi (~5 s), ya'ni
    "yangi kod"/"o'chirish" bosilgach ulanish deyarli darhol uziladi. Ilgari
    yagona tekshiruv 5 daqiqalik `touch_agent` edi.
    """
    async with AsyncRedis.from_url(settings.REDIS_URL) as redis:
        await redis.set(agent_revoked_key(agent_id), "1", ex=600)
        if not purge_queue:
            return 0
        key = print_queue_key(agent_id)
        n = int(await redis.llen(key) or 0)
        if n:
            await redis.delete(key)
        return n


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
                .returning(BridgeAgent.id, BridgeAgent.name, BridgeAgent.machine_id)
            )
        ).first()
    if row is None:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Ulanish kodi noto'g'ri yoki muddati o'tgan.")

    # Yangi juftlanish bayroqni bekor qiladi: aks holda endi qonuniy bo'lgan
    # ulanish TTL tugaguncha (10 daqiqa) uzilib turardi.
    async with AsyncRedis.from_url(settings.REDIS_URL) as redis:
        await redis.delete(agent_revoked_key(row.id))
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
    machine_name = None
    if row.machine_id is not None:
        machine = await crud_machines.get(db, id=row.machine_id)
        machine_name = machine.name if machine is not None else None
    return BridgePairResponse(token=token, name=row.name, machine_name=machine_name)


async def _agent_by_token(db: SessionDep, authorization: str) -> BridgeAgent:
    """Bearer token bo'yicha agentni topadi — `/scan` va `/logs` uchun umumiy."""
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
    return agent


@router.post("/logs", response_model=Message, operation_id="push_bridge_logs")
async def push_bridge_logs(
    db: SessionDep,
    body: BridgeLogPush,
    authorization: str = Header(default=""),
) -> Message:
    """Agent o'z loglarini yuboradi — admin ularni panelda ko'radi.

    Nega HTTP, `/ws/bridge` orqali emas: o'sha soketda chek jo'natish, ack kutish
    va qayta navbatga qo'yish mantiqi bor. Log xabari ack o'rniga o'qilsa job
    "nak" deb hisoblanib chop etish buzilardi. Diagnostika uchun ishlab chiqarish
    yo'lini xavf ostiga qo'yish mantiqsiz.

    Autentifikatsiya — agentning o'sha doimiy tokeni. Boshqa agentning logini
    ko'rish yoki yozish imkonsiz: kalit token egasining `id` sidan quriladi.
    """
    agent = await _agent_by_token(db, authorization)
    lines = [ln[:500] for ln in body.lines if ln.strip()]
    if not lines:
        return Message(message="bo'sh")
    async with AsyncRedis.from_url(settings.REDIS_URL) as redis:
        key = AGENT_LOG_KEY.format(agent.id)
        # Eng yangisi boshida tursin: LPUSH teskari tartibda beriladi
        await redis.lpush(key, *reversed(lines))
        await redis.ltrim(key, 0, AGENT_LOG_KEEP - 1)
        await redis.expire(key, AGENT_LOG_TTL)
    return Message(message=f"{len(lines)} satr")


@router.get("/{agent_id}/logs", response_model=list[str], operation_id="read_bridge_logs")
async def read_bridge_logs(db: SessionDep, _: AdminUser, agent_id: int) -> list[str]:
    r"""Agentning oxirgi log satrlari (eng yangisi birinchi).

    Ilgari admin operatordan `%APPDATA%\MebelixAgent\agent.log` ni ochishni
    so'rashga majbur edi — tsexdagi kompyuterga masofadan kirish yo'q."""
    await crud_bridge_agents.get_or_404(db, "Agent topilmadi.", id=agent_id)
    async with AsyncRedis.from_url(settings.REDIS_URL) as redis:
        rows = await redis.lrange(AGENT_LOG_KEY.format(agent_id), 0, AGENT_LOG_KEEP - 1)
    return [r.decode() if isinstance(r, bytes) else r for r in rows]


#: Beyjik QR'i — UUID (Employee.badge_id String(36)). Detal QR'ida esa DOIM `_`
#: bo'ladi, ya'ni ikkalasi hech qachon chalkashmaydi.
_BADGE_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


@router.post("/scan", response_model=ScanResult, operation_id="bridge_scan")
async def bridge_scan(
    db: SessionDep,
    body: BridgeScanRequest,
    authorization: str = Header(default=""),
) -> ScanResult:
    """Skan-forvard: stanok skaneri o'qigan QR agent orqali MES'ga ham yoziladi.

    Auth — agentning doimiy tokeni (Bearer). Skan agentga bog'langan ish markazining
    AKTIV sessiyasi nomidan yoziladi (monoblokda operator kirgan bo'lishi shart) —
    hisob-kitob odatdagi skan bilan bir xil yo'ldan o'tadi.
    """
    agent = await _agent_by_token(db, authorization)
    # BEYJIK — detal skani EMAS. Operator monoblokda smena ochish uchun beyjigini
    # skanerlaydi; agentning global klaviatura kuzatuvchisi o'sha zarbalarni ham
    # ilib olib bu yerga yuboradi. Ilgari u odatdagi yo'ldan o'tib E002 ("QR
    # formati buzuq") bilan rad etilardi: audit logga yozilar va terminal
    # ekraniga QIZIL banner + xato ovozi chiqardi — qonuniy beyjik skanidan.
    # Prodda 9 marta o'lchandi. Endi jimgina chetlab o'tiladi: log ham,
    # WS xabari ham yo'q. Yangi agent (v1.4.4+) buni umuman jo'natmaydi —
    # bu yerdagi tekshiruv eski agentlar uchun himoya.
    # QOLDIQ (ATX-) va PACHKA (PK-) QR'lari detal skani EMAS: ularning o'z
    # oqimi bor (terminal `/scans` ATX uchun to'liq ma'lumot qaytaradi, PK esa
    # TMO qabulida ishlatiladi). Stanok skaneridan o'tsa ular `_QR_RE` dan
    # yiqilib E002 "QR formati buzuq" degan QIZIL xato berardi — chek aslida
    # butun. Jimgina chetlab o'tamiz.
    _qr = body.qr_text.strip().upper()
    if _qr.startswith(("ATX-", "PK-")):
        raise scan_error("SKIP", "Bu QR detal skani emas — terminalda skanerlang.")
    if _BADGE_RE.match(body.qr_text.strip()):
        raise scan_error("BADGE", "Beyjik skani — detal skani emas, o'tkazib yuborildi.")
    if agent.machine_id is None:
        raise HTTPException(
            status_code=409,
            detail="Agent ish markaziga bog'lanmagan — admin panelda Printer agentlar bo'limida tanlang.",
        )
    machine = await db.get(Machine, agent.machine_id)
    if machine is None or machine.is_deleted:
        raise HTTPException(status_code=409, detail="Bog'langan ish markazi topilmadi.")
    post = await db.get(Post, machine.post_id)
    if post is None:
        raise HTTPException(status_code=409, detail="Ish markazining posti topilmadi.")
    # Idlar SHU YERDA olinadi: quyidagi `log_rejected_scan` ichida `db.rollback()`
    # bor va u identity map'dagi HAMMA obyektni expire qiladi. Undan keyin
    # `machine.id` ni o'qish lazy refresh talab qilib, async kontekstda
    # `MissingGreenlet` bilan 500 berardi — stanok skani jimgina yo'qolardi.
    # `agent` ham SHU RO'YXATDA: u ham `db` dan yuklangan va rollback uni ham expire
    # qiladi — `log_rejected_scan` chaqiruvida `agent.name`/`agent.id` argument sifatida
    # o'qilardi, ya'ni takroriy `client_event_id` poygasida stanok skani 500 ga aylanib
    # logga ham tushmasdi.
    machine_id, post_id = machine.id, post.id
    agent_name, agent_id = agent.name, agent.id
    # Terminal bilan AYNAN bir xil qoida: `active_session` langar smenani beradi va
    # egasining nofaol emasligini ham tekshiradi. Ilgari bu yerda `crew[0]` to'g'ridan
    # olinardi — nofaol hodim langar bo'lsa terminal skanni rad etib, stanok skani
    # o'sha odam nomidan yozilaverardi.
    try:
        session = await active_session(db, machine)
    except ScanRejected as exc:
        # Terminal ekraniga ham chiqsin: ilgari bu holat (smena ochilmagan,
        # hodim nofaol) FAQAT agent logiga tushardi — stanokda skanerlagan
        # operator hech qanday signal ko'rmasdi va skanini yo'qotganini
        # bilmasdi. Skan hisobga OLINMAYDI, bu faqat xabar.
        await ws_manager.publish(
            "scan.rejected",
            {"qr_text": body.qr_text, "code": exc.code, "message": exc.message, "machine_id": machine_id},
            post_id=post_id,
            machine_id=machine_id,
        )
        raise HTTPException(status_code=409, detail=exc.message) from exc

    try:
        outcome = await record_scan_at(
            db,
            machine=machine,
            post=post,
            session=session,
            qr_text=body.qr_text,
            client_event_id=body.client_event_id,
        )
    except ScanRejected as exc:
        await log_rejected_scan(
            db, exc, body.qr_text, source=f" (stanok, {agent_name})", meta_extra={"agent_id": agent_id}
        )
        # Stanokdagi rad etilgan skan endi terminal ekraniga ham chiqadi. Bu
        # FAQAT shu yo'lga tegishli: terminalning o'z skani 422 javobning
        # o'zidan xabar oladi, ya'ni umumiy `log_rejected_scan` ga parametr
        # qo'shishning hojati yo'q.
        await ws_manager.publish(
            "scan.rejected",
            {"qr_text": body.qr_text, "code": exc.code, "message": exc.message, "machine_id": machine_id},
            post_id=post_id,
            machine_id=machine_id,
        )
        raise scan_error(exc.code, exc.message) from None

    return await finalize_scan(db, outcome, source=f" (stanok, {agent.name})", agent_id=agent.id)


# Agent exe tarqatish (2026-08-27, flashka o'rniga). 2026-08-02 da yuklab olish
# endpointi olib tashlangan edi — sababi diskda ESKI exe qolib adashtirishi.
# Endi manba yagona: CI har deploy'da windows-runner'da exe qurib version.json
# (versiya + sha256) bilan `agent-dist/` ga qo'yadi — eskirishning iloji yo'q.
# Ochiq (himoyasiz): agentda sessiya yo'q, exe sir emas, /pair ham ochiq.

_AGENT_DIST = Path("agent-dist")


@router.get("/latest", response_model=AgentRelease, operation_id="agent_latest_release")
async def agent_latest_release() -> AgentRelease:
    """Oxirgi agent versiyasi — agent har 10 daqiqada va har qayta ulanishda shu yerdan tekshiradi."""
    manifest = _AGENT_DIST / "version.json"
    if not manifest.is_file():
        raise NotFoundException("Agent fayli serverda yo'q — CI hali qurmagan.")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return AgentRelease(version=data["version"], sha256=data["sha256"])


@router.get("/download", operation_id="download_agent_exe")
async def download_agent_exe() -> FileResponse:
    """mebelix-agent.exe — agent o'zini yangilashda, admin birinchi o'rnatishda."""
    exe = _AGENT_DIST / "mebelix-agent.exe"
    if not exe.is_file():
        raise NotFoundException("Agent fayli serverda yo'q — CI hali qurmagan.")
    return FileResponse(exe, media_type="application/octet-stream", filename="mebelix-agent.exe")
