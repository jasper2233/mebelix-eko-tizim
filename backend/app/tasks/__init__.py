import base64
import json
import logging
import socket
from typing import Any

from fastapi.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.db import local_session
from app.services.labels import build_label_ezpl, load_label_data, render_label_png

logger = logging.getLogger(__name__)

PRINT_QUEUE_KEY = "mes:print:queue"  # bridge-agent drains this list (TZ 2.2.2)


async def ping(ctx: dict[str, Any]) -> str:
    """Liveness probe task. ARQ requires at least one registered function."""
    return "pong"


def _send_tcp(ezpl: str, ip: str, port: int) -> None:
    with socket.create_connection((ip, port), timeout=10) as sock:
        sock.sendall(ezpl.encode("cp1251", errors="replace"))


async def print_label(ctx: dict[str, Any], instance_id: int) -> str:
    """Build the EZPL label for one physical copy and dispatch it (TZ 7.1.4).

    Remote-first: LPUSH to the Redis print queue — the shop-floor bridge-agent executes it
    on the GoDEX. Local mode (PRINTER_IP set): direct TCP to printer:9100.
    """
    async with local_session() as db:
        data = await load_label_data(db, instance_id)
        if data is None:
            return f"skip:{instance_id}"
        ezpl = build_label_ezpl(data)
        # PNG ham yuboriladi: USB (GDI) rejimidagi agent rasmni chizadi — printer
        # dialektiga bog'liq emas; tarmoq GoDEX esa ezpl'ni oladi
        png_b64 = base64.b64encode(render_label_png(data)).decode()

    if settings.PRINTER_IP:
        try:
            await run_in_threadpool(_send_tcp, ezpl, settings.PRINTER_IP, settings.PRINTER_PORT)
            return f"printed:{instance_id}"
        except OSError:
            logger.exception("Printerga to'g'ridan-to'g'ri yuborib bo'lmadi — navbatga qo'yildi")

    redis = ctx.get("redis")  # arq worker context carries its Redis connection
    if redis is not None:
        job = json.dumps({"type": "print", "instance_id": instance_id, "ezpl": ezpl, "png": png_b64})
        await redis.lpush(PRINT_QUEUE_KEY, job)
        return f"queued:{instance_id}"

    logger.error("Print job %s uchun na printer, na Redis navbati mavjud", instance_id)
    return f"lost:{instance_id}"


all_tasks = [ping, print_label]
