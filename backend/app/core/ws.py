"""Real-time bridge (TZ 2.3): WebSocket fan-out with Redis pub/sub across workers.

Room model: every connection registers a scope + optional post/machine filters.
Events published by API handlers go through Redis (`mes:events` channel) so all
gunicorn workers deliver to their local sockets; before the lifespan starts the
listener, or when a `PUBLISH` fails, dispatch degrades to local-only.
"""

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

#: Pub/sub uzilgach qayta obuna oralig'i. Qisqa: fan-out to'xtagan har soniya
#: terminalda "skan ko'rinmadi" degani.
_RESUBSCRIBE_SECONDS = 2

_CHANNEL = "mes:events"


@dataclass
class WsClient:
    socket: WebSocket
    scope: str  # "terminal" | "tablo" | "dashboard"
    post_id: int | None = None
    machine_id: int | None = None

    def wants(self, event: dict[str, Any]) -> bool:
        """Terminallar O'Z posti/ish markazi eventlarini oladi (TZ 2.3.2);
        dashboard va TABLO hammasini; nishonsiz event esa hammaga ketadi."""
        target_post = event.get("post_id")
        target_machine = event.get("machine_id")
        # TABLO — devor ekrani, u BUTUN tsex matritsasini ko'rsatadi, ya'ni post
        # filtri unga ma'nosiz. Qurilma hisobi majburan ish markaziga bog'langani
        # uchun (`users.py`: TERMINAL/TABLO da `machine_id` shart) u ilgari FAQAT
        # bitta postning skanlarini olardi: taxta qolgan 8 postni jonli ko'rmay,
        # 60 soniyalik pollingni kutardi.
        if self.scope in ("dashboard", "tablo"):
            return True
        if target_post is None and target_machine is None:
            return True
        if self.post_id is not None and target_post == self.post_id:
            return True
        return self.machine_id is not None and target_machine == self.machine_id


@dataclass
class WsManager:
    clients: list[WsClient] = field(default_factory=list)
    redis: Redis | None = None
    _listener: asyncio.Task[None] | None = None

    async def connect(self, client: WsClient) -> None:
        await client.socket.accept()
        self.clients.append(client)

    def disconnect(self, client: WsClient) -> None:
        with contextlib.suppress(ValueError):
            self.clients.remove(client)

    async def publish(self, event_type: str, payload: dict[str, Any], **targets: int | None) -> None:
        """Fire an event: type + payload (+ post_id/machine_id targeting)."""
        event: dict[str, Any] = {"type": event_type, "payload": payload}
        event.update({k: v for k, v in targets.items() if v is not None})
        if self.redis is not None:
            try:
                await self.redis.publish(_CHANNEL, json.dumps(event, default=str))
                return
            except Exception:  # Redis down → degrade to local delivery
                logger.exception("WS publish Redis xatosi — lokal yetkazishga o'tildi")
        await self._dispatch(event)

    async def _dispatch(self, event: dict[str, Any]) -> None:
        dead: list[WsClient] = []
        for client in self.clients:
            if not client.wants(event):
                continue
            try:
                await client.socket.send_json(event)
            except Exception:
                dead.append(client)
        for client in dead:
            self.disconnect(client)

    async def start_listener(self, redis: Redis) -> None:
        self.redis = redis
        pubsub = redis.pubsub()
        await pubsub.subscribe(_CHANNEL)

        async def listen() -> None:
            # Redis uzilishi tinglovchini O'LDIRMASLIGI kerak. Ilgari faqat
            # `CancelledError` ushlanardi: bitta tarmoq uzilishi task'ni tashlab
            # ketar, workerlar aro fan-out esa JIMGINA to'xtardi — terminal
            # boshqa workerdagi skanni umuman ko'rmay qolardi va buni hech kim
            # sezmasdi (log ham yo'q edi). Endi qayta obuna bo'lib davom etadi.
            while True:
                try:
                    async for message in pubsub.listen():
                        if message.get("type") != "message":
                            continue
                        with contextlib.suppress(Exception):
                            await self._dispatch(json.loads(message["data"]))
                except asyncio.CancelledError:
                    with contextlib.suppress(Exception):
                        await pubsub.unsubscribe(_CHANNEL)
                    raise
                except Exception:
                    logger.exception(
                        "WS pub/sub tinglovchisi uzildi — %s s dan keyin qayta obuna", _RESUBSCRIBE_SECONDS
                    )
                    await asyncio.sleep(_RESUBSCRIBE_SECONDS)
                    with contextlib.suppress(Exception):
                        await pubsub.subscribe(_CHANNEL)

        self._listener = asyncio.create_task(listen())

    async def stop_listener(self) -> None:
        if self._listener is not None:
            self._listener.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener
            self._listener = None
        self.redis = None


ws_manager = WsManager()
