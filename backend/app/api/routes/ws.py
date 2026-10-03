"""WebSocket endpoints: /ws/events (browser clients) and /ws/bridge (
the shop-floor bridge-agent that executes print jobs on the local GoDEX)."""

import asyncio
import contextlib
import hashlib
import json
import logging
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import select, update

from app.api.deps import resolve_user
from app.core import perf
from app.core.config import settings
from app.core.db import local_session
from app.core.security import ACCESS_COOKIE_NAME
from app.core.ws import WsClient, ws_manager
from app.models import BridgeAgent, Machine, Post
from app.models.enums import POST_ROLES, UserRole
from app.tasks import agent_revoked_key, bridge_conn_key, print_queue_key

router = APIRouter()

# Chek yo'qolganda serverda IZ qolishi uchun. Ilgari bu modulda logging umuman
# yo'q edi va "chek chiqmadi" shikoyati kelganda tekshirish uchun hech narsa
# bo'lmasdi: job qaysi agentga ketgani ham, ack kelgan-kelmagani ham qayd
# etilmasdi. Nosozlikni prodda ajratib bo'lmasligining asosiy sababi shu edi.
logger = logging.getLogger(__name__)

WS_CLOSE_UNAUTHORIZED = 4401  # custom "unauthorized" close code (4000–4999 — application-defined)

#: Ochiq `/ws/events` soketida tokenni qayta tekshirish oralig'i (soniya).
#: `/ws/bridge` dagi `touch_agent` bilan bir xil qadam — DB'ga ortiqcha yuk bo'lmasin.
_RECHECK_SECONDS = 300

_SCOPE_BY_ROLE = {
    UserRole.TERMINAL: "terminal",
    UserRole.TABLO: "tablo",
}


async def _still_authorized(raw_token: str) -> bool:
    """Ochiq soket uchun tokenni QAYTA tekshiradi.

    Ilgari token faqat ulanish paytida tekshirilardi: logout (token_version
    bump) yoki foydalanuvchini o'chirish ochiq brauzer soketiga umuman ta'sir
    qilmasdi — sahifa yopilmaguncha eventlar oqishda davom etardi. Tekshiruv
    BEKOR QILINGANLIK bo'yicha (`verify_exp=False`): ulanishdagi access token
    30 daqiqada eskiradi, tablo/terminal soketi esa kun bo'yi ochiq — muddat
    bo'yicha uzish har ekranni yarim soatda uzib qayta ulardi. DB xatosi
    ulanishni YIQITMAYDI (`touch_agent` uslubi): vaqtinchalik nosozlik jonli
    kanalni uzmasin.
    """
    with contextlib.suppress(Exception):
        async with local_session() as db:
            return await resolve_user(db, raw_token, verify_exp=False) is not None
    return True


@router.websocket("/ws/events")
async def ws_events(websocket: WebSocket) -> None:
    """Brauzer klientlari.

    Auth: token `Authorization` headeridan, bo'lmasa access cookie'dan olinadi.
    `?token=` query param ATAYLAB qabul qilinmaydi — u server access-loglariga
    tushib token'ni sizdirardi (ws/bridge ham aynan shu sababdan headerga o'tgan).
    """
    header_token = websocket.headers.get("authorization", "").removeprefix("Bearer ").strip()
    raw_token = header_token or websocket.cookies.get(ACCESS_COOKIE_NAME)
    if not raw_token:
        await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
        return
    async with local_session() as db:
        user = await resolve_user(db, raw_token)
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
    last_check = asyncio.get_event_loop().time()
    try:
        while True:
            # Heartbeat: clients ping every 30s; any payload is answered with pong.
            await websocket.receive_text()
            now = asyncio.get_event_loop().time()
            if now - last_check >= _RECHECK_SECONDS:
                last_check = now
                if not await _still_authorized(raw_token):
                    logger.info("WS token bekor qilindi — ulanish uzildi: user=%s", user.id)
                    await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
                    break
            with contextlib.suppress(Exception):
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(client)


async def _bridge_claim(redis: AsyncRedis, agent_id: int | None, conn_id: str) -> None:
    """Shu ulanishni agentning eng oxirgisi deb belgilaydi (`bridge_conn_key`).
    Legacy umumiy token (`agent_id is None`) — kalitsiz: jadvalda qatori yo'q."""
    if agent_id is not None:
        await redis.set(bridge_conn_key(agent_id), conn_id, ex=600)


async def _bridge_superseded(redis: AsyncRedis, agent_id: int | None, conn_id: str) -> bool:
    """Agentning YANGIROQ ulanishi bormi — kalitda boshqa ulanishning id'si turibdi.
    Redis xatosi — noma'lum: False, ya'ni eskicha (hodisa chiqadi)."""
    if agent_id is None:
        return False
    with contextlib.suppress(Exception):
        latest = await redis.get(bridge_conn_key(agent_id))
        return latest is not None and latest.decode() != conn_id
    return False


async def _bridge_gone(redis: AsyncRedis, agent_id: int | None, machine_id: int | None, conn_id: str) -> None:
    """«Uzildi» hodisasi — FAQAT agentning eng oxirgi ulanishi yopilganda (sabab: `bridge_conn_key`)."""
    payload = {"agent_id": agent_id, "machine_id": machine_id}
    if await _bridge_superseded(redis, agent_id, conn_id):
        logger.info("Bridge: agent=%s conn=%s — yangiroq ulanish bor, «uzildi» hodisasi yuborilmadi", agent_id, conn_id)
        return
    await ws_manager.publish("bridge.disconnected", payload)
    # Tekshiruv bilan e'lon orasida yangi ulanish kirib ulgurgan bo'lsa, uning «ulandi» si bizning
    # «uzildi» dan OLDIN ketgan — terminal oxirgi hodisaga ishonadi, shuning uchun «ulandi» takrorlanadi.
    if await _bridge_superseded(redis, agent_id, conn_id):
        await ws_manager.publish("bridge.connected", payload)


@router.websocket("/ws/bridge")
async def ws_bridge(websocket: WebSocket, token: str = "") -> None:
    """Bridge-agent uplink: outbound connection from the shop network.

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
    last_touch = asyncio.get_event_loop().time()
    conn_id = uuid.uuid4().hex[:12]  # shu ulanishning id'si: `bridge_conn_key` qiymati va logdagi iz

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
        # Avval "eng oxirgi ulanish — men", KEYIN hodisa: shundan keyin yopilgan eski soket
        # o'zini eskirgan deb ko'radi va «uzildi» chiqarmaydi (`_bridge_gone`).
        await _bridge_claim(redis, agent_id, conn_id)
        logger.info("Bridge ulandi: agent=%s conn=%s", agent_id, conn_id)
        # Admin "MES agentlar" sahifasi darhol "Ulandi" ko'rsatsin — 10s pollingni kutmasdan
        await ws_manager.publish("bridge.connected", {"agent_id": agent_id, "machine_id": agent_machine_id})
        while True:
            if can_print and own_keys:
                popped = await redis.brpop(own_keys, timeout=5)
            else:
                # Printersiz stansiya (skan-forvard): navbatdan chek OLMAYDI —
                # aks holda umumiy navbatdan chekni "o'g'irlab" lokalida qoldiradi
                popped = None
                await asyncio.sleep(5)
            # REVOKE — HAR ITERATSIYADA (arzon Redis GET, ulanishning o'z
            # klienti bilan). Ilgari yagona tekshiruv 5 daqiqalik `touch_agent`
            # edi: admin "yangi kod" bosgach bekor qilingan token yana ~5 daqiqa
            # chek olib chop etaverardi va panel "Ulandi" deb turardi
            # (repro bilan o'lchangan: 295 s). Endi kechikish <= brpop siklining
            # o'zi (~5 s).
            if agent_id is not None and await redis.get(agent_revoked_key(agent_id)):
                if popped is not None:
                    await redis.rpush(popped[0], popped[1])
                logger.info("Agent bekor qilindi — ulanish uzildi: agent=%s", agent_id)
                await websocket.close(code=WS_CLOSE_UNAUTHORIZED)
                return
            now = asyncio.get_event_loop().time()
            if now - last_touch > 300:  # zaxira tekshiruv — DB'ga ortiqcha yuk bo'lmasin
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
            parsed: dict[str, Any] = {}
            with contextlib.suppress(Exception):
                parsed = json.loads(job)
                job_id = parsed.get("job_id", "")
            delivered = False  # nack yo'lida "yetkazildi" deb yozilmasin
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
                        # Agent chekni RAD ETDI (printeri yo'q) — bu tarmoq
                        # xatosi EMAS: ulanish tirik, faqat chiqara olmaydi.
                        # Ilgari ValueError ko'tarilib butun soket yopilardi va
                        # 5 soniyalik ulan-uzil sikli boshlanardi: reconnect ->
                        # o'sha job -> yana nack -> yana uzilish (terminal
                        # chipi ham lip-lip qilardi). Endi job navbatga
                        # qaytadi, ulanish qoladi, 15s pauza — printer drayveri
                        # o'rnatilgach o'zi chiqadi.
                        await redis.rpush(src_key, job)
                        logger.warning(
                            "Agent chekni rad etdi (printer topilmadi?) — navbatda qoladi: agent=%s job=%s",
                            agent_id,
                            job_id,
                        )
                        await asyncio.sleep(15)
                        delivered = False
                        break
                    delivered = True
                    break
                if delivered:
                    logger.info("Chek yetkazildi: agent=%s job=%s", agent_id, job_id)
                    perf.record_delivered(agent_id, parsed)
            except Exception as exc:
                logger.warning(
                    "Chek yetkazilmadi, navbatga qaytarildi: agent=%s job=%s sabab=%s",
                    agent_id,
                    job_id,
                    exc,
                )
                # AYNAN kelgan kalitga qaytadi: umumiy navbatga tashlansa
                # manzil yo'qolib, chek boshqa printerdan chiqib ketardi.
                await redis.rpush(src_key, job)
                raise
    except Exception as exc:  # noqa: BLE001 — connection teardown; the job was already requeued
        # `%r`: starlette `WebSocketDisconnect(code=1006)` ning matni bo'sh — `%s` "sabab=" deb chiqarardi;
        # `%r` istisno turini ko'rsatadi (1006 kodining o'zi ko'rinmaydi — u kalit so'z bilan beriladi)
        logger.info("Bridge ulanishi yopildi: agent=%s conn=%s sabab=%r", agent_id, conn_id, exc)
    finally:
        with contextlib.suppress(Exception):
            await _bridge_gone(redis, agent_id, agent_machine_id, conn_id)
        await redis.aclose()
