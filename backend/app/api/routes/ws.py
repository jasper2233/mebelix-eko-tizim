"""WebSocket endpoint: /ws/events (TZ 2.3) — brauzer mijozlari uchun jonli yangilanishlar."""

import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.db import local_session
from app.core.security import ACCESS_COOKIE_NAME, TokenType, verify_token
from app.core.ws import WsClient, ws_manager
from app.crud import crud_users
from app.models import Machine
from app.models.enums import UserRole

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
