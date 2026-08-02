"""WebSocket endpoints: /ws/events (TZ 2.3, browser clients) and /ws/bridge (TZ 2.2.2,
the shop-floor bridge-agent that executes print jobs on the local GoDEX)."""

import asyncio
import contextlib
import hashlib
import json
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
from app.tasks import PRINT_QUEUE_KEY

router = APIRouter()

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
            await websocket.close(code=4401)
            return
        post_id = None
        if user.machine_id is not None:
            machine = await db.get(Machine, user.machine_id)
            post_id = machine.post_id if machine else None
        elif (post_code := POST_ROLES.get(UserRole(user.role))) is not None:
            # Operator rol (prisadkachi, kromkachi, ...): stanok biriktirilmagan —
            # post roldan olinadi, aks holda postga nishonlangan scan.recorded
            # eventlari yetib bormay jonli yangilanish ishlamaydi
            post = (
                await db.execute(select(Post).where(Post.code == post_code, Post.is_deleted == False))  # noqa: E712
            ).scalar_one_or_none()
            post_id = post.id if post else None

    client = WsClient(
        socket=websocket,
        scope=_SCOPE_BY_ROLE.get(user.role, "dashboard"),
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
    token_hash: str | None = None
    can_print = True
    # bytes solishtirish: non-ASCII tokenda compare_digest(str) TypeError beradi
    legacy = bool(settings.BRIDGE_TOKEN) and secrets.compare_digest(token.encode(), settings.BRIDGE_TOKEN.encode())
    if not legacy:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        async with local_session() as db:
            row = (
                await db.execute(
                    select(BridgeAgent.id, BridgeAgent.can_print).where(
                        BridgeAgent.token_hash == token_hash,
                        BridgeAgent.is_deleted == False,  # noqa: E712
                    )
                )
            ).first()
        if row is None:
            await websocket.close(code=4401)
            return
        agent_id, can_print = row
    await websocket.accept()

    async def touch_agent() -> bool:
        """last_seen_at yangilaydi (paneldagi "Onlayn") va can_print'ni yangilab oladi
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
        await websocket.close(code=4401)
        return
    # Admin "Printerlar" sahifasi darhol "Ulandi" ko'rsatsin — 10s pollingni kutmasdan
    await ws_manager.publish("bridge.connected", {"agent_id": agent_id})
    last_touch = asyncio.get_event_loop().time()

    redis = AsyncRedis.from_url(settings.REDIS_URL)
    try:
        while True:
            if can_print:
                popped = await redis.brpop([PRINT_QUEUE_KEY], timeout=5)
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
                        await redis.rpush(PRINT_QUEUE_KEY, popped[1])
                    await websocket.close(code=4401)
                    return
                last_touch = now
            if popped is None:
                # idle heartbeat so half-open TCP dies fast on shop networks
                await websocket.send_json({"type": "ping"})
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(websocket.receive_text(), timeout=10)
                continue
            _key, raw = popped
            job = raw.decode() if isinstance(raw, bytes) else raw
            try:
                await websocket.send_text(job)
                ack = await asyncio.wait_for(websocket.receive_text(), timeout=15)
                if not json.loads(ack).get("ok"):
                    raise ValueError("bridge nak")
            except Exception:
                await redis.rpush(PRINT_QUEUE_KEY, job)  # requeue — job is never lost
                raise
    except Exception:  # noqa: BLE001 — connection teardown; the job was already requeued
        pass
    finally:
        await redis.close()
        with contextlib.suppress(Exception):
            await ws_manager.publish("bridge.disconnected", {"agent_id": agent_id})
