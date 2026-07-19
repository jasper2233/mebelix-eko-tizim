"""WebSocket endpoints: /ws/events (TZ 2.3, browser clients) and /ws/bridge (TZ 2.2.2,
the shop-floor bridge-agent that executes print jobs on the local GoDEX)."""

import asyncio
import contextlib
import json
import secrets

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis as AsyncRedis

from app.core.config import settings
from app.core.db import local_session
from app.core.security import ACCESS_COOKIE_NAME, TokenType, verify_token
from app.core.ws import WsClient, ws_manager
from app.crud import crud_users
from app.models import Machine
from app.models.enums import UserRole
from app.tasks import PRINT_QUEUE_KEY

router = APIRouter()

_SCOPE_BY_ROLE = {
    UserRole.TERMINAL: "terminal",
    UserRole.TABLO: "tablo",
}


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket, token: str | None = None) -> None:
    raw_token = token or websocket.cookies.get(ACCESS_COOKIE_NAME)
    token_data = verify_token(raw_token, TokenType.ACCESS) if raw_token else None
    if token_data is None:
        await websocket.close(code=4401)
        return

    async with local_session() as db:
        user = await crud_users.get(db, id=token_data.user_id)
        if user is None or not user.is_active or user.token_version != token_data.token_version:
            await websocket.close(code=4401)
            return
        post_id = None
        if user.machine_id is not None:
            machine = await db.get(Machine, user.machine_id)
            post_id = machine.post_id if machine else None

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

    The agent authenticates with BRIDGE_TOKEN, then receives print jobs drained from the
    Redis queue. Each job must be acked ({"ok": true}) after the agent has durably queued
    it locally; un-acked jobs are pushed back so nothing is lost on disconnect.
    """
    if not settings.BRIDGE_TOKEN or not secrets.compare_digest(token, settings.BRIDGE_TOKEN):
        await websocket.close(code=4401)
        return
    await websocket.accept()

    redis = AsyncRedis.from_url(settings.REDIS_URL)
    try:
        while True:
            popped = await redis.brpop([PRINT_QUEUE_KEY], timeout=5)
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
