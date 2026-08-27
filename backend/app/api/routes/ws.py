"""WebSocket endpoints: /ws/events (TZ 2.3, browser clients) and /ws/bridge (TZ 2.2.2,
the shop-floor bridge-agent that executes print jobs on the local GoDEX)."""

import asyncio
import contextlib
import hashlib
import json
import logging
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import select, update

from app.api.deps import resolve_user
from app.core.config import settings
from app.core.db import local_session
from app.core.security import ACCESS_COOKIE_NAME
from app.core.ws import WsClient, ws_manager
from app.models import BridgeAgent, Machine, Post
from app.models.enums import POST_ROLES, UserRole
from app.tasks import print_queue_key

router = APIRouter()

# Chek yo'qolganda serverda IZ qolishi uchun. Ilgari bu modulda logging umuman
# yo'q edi va "chek chiqmadi" shikoyati kelganda tekshirish uchun hech narsa
# bo'lmasdi: job qaysi agentga ketgani ham, ack kelgan-kelmagani ham qayd
# etilmasdi. Nosozlikni prodda ajratib bo'lmasligining asosiy sababi shu edi.
logger = logging.getLogger(__name__)

WS_CLOSE_UNAUTHORIZED = 4401  # custom "unauthorized" close code (4000–4999 — application-defined)

_SCOPE_BY_ROLE = {
    UserRole.TERMINAL: "terminal",
    UserRole.TABLO: "tablo",
}


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket, token: str | None = None) -> None:
    raw_token = token or websocket.cookies.get(ACCESS_COOKIE_NAME)
    async with local_session() as db:
        user = await resolve_user(db, raw_token) if raw_token else None
        if user is None:
            await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
            return
        post_id = None
        if user.machine_id is not None:
            machine = await db.get(Machine, user.machine_id)
            post_id = machine.post_id if machine else None
        elif (post_code := POST_ROLES.get(UserRole(user.role))) is not None:
            # Operator rol (prisadkachi, kromkachi, ...): ish markazi biriktirilmagan —
            # post roldan olinadi, aks holda postga nishonlangan scan.recorded
            # eventlari yetib bormay jonli yangilanish ishlamaydi
            post = (
                await db.execute(select(Post).where(Post.code == post_code, Post.is_deleted == False))  # noqa: E712
            ).scalar_one_or_none()
            post_id = post.id if post else None

    # Operator rollar ham "terminal" scope — aks holda dashboard'ga tushib HAMMA
    # postning eventini olar, yuqoridagi post_id filtri esa umuman ishlamasdi
    role = UserRole(user.role)
    scope = _SCOPE_BY_ROLE.get(role) or ("terminal" if role in POST_ROLES else "dashboard")
    client = WsClient(
        socket=websocket,
        scope=scope,
        post_id=post_id,
        machine_id=user.machine_id,
    )
    await ws_manager.connect(client)
    try:
        while True:
            # Heartbeat (TZ 2.3.2): clients ping every 30s; any payload is answered with pong.
            await websocket.receive_text()
            with contextlib.suppress(Exception):
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(client)


@router.websocket("/ws/bridge")
async def ws_bridge(websocket: WebSocket, token: str = "") -> None:
    """Bridge-agent uplink (TZ 2.2.2): outbound connection from the shop network.

    Auth: pairing orqali berilgan per-agent token (bridge_agent.token_hash) yoki
    legacy umumiy BRIDGE_TOKEN. Token Authorization headerda keladi — server
    access-loglariga tushmasin; query param eski agentlar uchun fallback.

    Each job must be acked ({"ok": true}) after the agent has durably queued it
    locally; un-acked jobs are pushed back so nothing is lost on disconnect.
    """
    if not token:
        token = websocket.headers.get("authorization", "").removeprefix("Bearer ").strip()
    agent_version = websocket.headers.get("x-agent-version", "").strip()[:20] or None
    agent_id: int | None = None
    agent_machine_id: int | None = None
    token_hash: str | None = None
    can_print = True
    # bytes solishtirish: non-ASCII tokenda compare_digest(str) TypeError beradi
    legacy = bool(settings.BRIDGE_TOKEN) and secrets.compare_digest(token.encode(), settings.BRIDGE_TOKEN.encode())
    if not legacy:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        async with local_session() as db:
            row = (
                await db.execute(
                    select(BridgeAgent.id, BridgeAgent.can_print, BridgeAgent.machine_id).where(
                        BridgeAgent.token_hash == token_hash,
                        BridgeAgent.is_deleted == False,  # noqa: E712
                    )
                )
            ).first()
        if row is None:
            await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
            return
        agent_id, can_print, agent_machine_id = row
    await websocket.accept()

    async def touch_agent() -> bool:
        """last_seen_at yangilaydi (paneldagi "Ulandi") va can_print'ni yangilab oladi
        (admin belgini o'zgartirsa ~5 daqiqada kuchga kiradi). False = token bekor
        qilingan (revoke yoki yangi kod) — ulanish yopilishi kerak. DB xatosi
        ulanishni YIQITMAYDI: qo'lda turgan print job yo'qolmasin."""
        nonlocal can_print
        if agent_id is None:  # legacy umumiy token — jadvalda qatori yo'q
            return True
        with contextlib.suppress(Exception):
            async with local_session() as db:
                res = await db.execute(
                    update(BridgeAgent)
                    .where(
                        BridgeAgent.id == agent_id,
                        BridgeAgent.token_hash == token_hash,
                        BridgeAgent.is_deleted == False,  # noqa: E712
                    )
                    .values(last_seen_at=datetime.now(UTC), version=agent_version)
                    .returning(BridgeAgent.can_print)
                )
                row = res.first()
                await db.commit()
                if row is None:
                    return False
                can_print = row[0]
                return True
        return True

    if not await touch_agent():
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return
    # Admin "Printerlar" sahifasi darhol "Ulandi" ko'rsatsin — 10s pollingni kutmasdan
    await ws_manager.publish("bridge.connected", {"agent_id": agent_id, "machine_id": agent_machine_id})
    last_touch = asyncio.get_event_loop().time()

    # HAR chek aniq bir agentga manzillangan (`tasks.require_printer`), shuning
    # uchun agent FAQAT o'zining navbatidan oladi. Umumiy `PRINT_QUEUE_KEY`
    # ATAYLAB o'qilmaydi: aynan u "ofisdagi test printeri tsexdagi chekni tortib
    # oldi" nuqsonining mexanizmi edi — kim birinchi ulgursa, chek o'shanikiga
    # chiqardi. Endi manzilsiz job umuman yaratilmaydi (chaqiruvchi 422 beradi),
    # ya'ni bu kalit bo'sh turadi.
    #
    # Tanitilmagan agent (legacy umumiy `BRIDGE_TOKEN`, `agent_id is None`) hech
    # qanday chek OLMAYDI: qaysi ish markazi ekani noma'lum, ya'ni unga chek
    # berish — yana o'sha tasodif.
    own_keys = [] if agent_id is None else [print_queue_key(agent_id)]
    redis = AsyncRedis.from_url(settings.REDIS_URL)
    try:
        while True:
            if can_print and own_keys:
                popped = await redis.brpop(own_keys, timeout=5)
            else:
                # Printersiz stansiya (skan-forvard): navbatdan chek OLMAYDI —
                # aks holda umumiy navbatdan chekni "o'g'irlab" lokalida qoldiradi
                popped = None
                await asyncio.sleep(5)
            now = asyncio.get_event_loop().time()
            if now - last_touch > 300:  # har 5 daqiqada — DB'ga ortiqcha yuk bo'lmasin
                if not await touch_agent():
                    # Revoke jonli ulanishni ham uzadi (maks ~5 daqiqa kechikish).
                    # Qo'lda turgan job navbatga qaytadi — yo'qolmaydi.
                    if popped is not None:
                        await redis.rpush(popped[0], popped[1])
                    await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
                    return
                last_touch = now
            if popped is None:
                # idle heartbeat so half-open TCP dies fast on shop networks
                await websocket.send_json({"type": "ping"})
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(websocket.receive_text(), timeout=10)
                continue
            src_key, raw = popped
            job = raw.decode() if isinstance(raw, bytes) else raw
            job_id = ""
            with contextlib.suppress(Exception):
                job_id = json.loads(job).get("job_id", "")
            try:
                # 10s dan KECH kelgan ping-javob soketda qolib keyingi jobning
                # ack'i bo'lib o'qilardi (eski agent pingga ham {"ok":true} beradi)
                # — job diskka yozilmasdan "yetkazildi" hisoblanib yo'qolardi.
                # Jo'natishdan oldin eskirgan javoblar tashlab yuboriladi.
                with contextlib.suppress(TimeoutError):
                    while True:
                        await asyncio.wait_for(websocket.receive_text(), timeout=0.05)
                await websocket.send_text(job)
                # Yangi agent pingga {"type":"pong"} qaytaradi — ack kutishda
                # bunday xabarlar o'tkazib yuboriladi
                deadline = asyncio.get_event_loop().time() + 15
                while True:
                    left = deadline - asyncio.get_event_loop().time()
                    if left <= 0:
                        raise TimeoutError("bridge ack timeout")
                    ack = json.loads(await asyncio.wait_for(websocket.receive_text(), timeout=left))
                    if ack.get("type") == "pong":
                        continue
                    if not ack.get("ok"):
                        raise ValueError("bridge nak")
                    break
                logger.info("Chek yetkazildi: agent=%s job=%s", agent_id, job_id)
            except Exception as exc:
                logger.warning(
                    "Chek yetkazilmadi, navbatga qaytarildi: agent=%s job=%s sabab=%s",
                    agent_id,
                    job_id,
                    exc,
                )
                # AYNAN kelgan kalitga qaytadi: umumiy navbatga tashlansa
                # manzil yo'qolib, chek boshqa printerdan chiqib ketardi.
                await redis.rpush(src_key, job)  # requeue — job is never lost
                raise
    except Exception as exc:  # noqa: BLE001 — connection teardown; the job was already requeued
        logger.info("Bridge ulanishi yopildi: agent=%s sabab=%s", agent_id, exc)
    finally:
        await redis.close()
        with contextlib.suppress(Exception):
            await ws_manager.publish(
                "bridge.disconnected",
                {"agent_id": agent_id, "machine_id": agent_machine_id},
            )
