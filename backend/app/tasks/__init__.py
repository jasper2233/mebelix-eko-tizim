import base64
import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from app.core.config import TASHKENT_TZ
from app.core.db import local_session
from app.services.labels import load_label_data, render_label_png

logger = logging.getLogger(__name__)

PRINT_QUEUE_KEY = "mes:print:queue"  # bridge-agent drains this list (TZ 2.2.2)


async def print_label(ctx: dict[str, Any], instance_id: int) -> str:
    """Render the label PNG for one physical copy and queue it (TZ 7.1.4).

    LPUSH to the Redis print queue — the shop-floor bridge-agent draws the PNG on the
    USB GoDEX (G500-U) via the Windows driver. PNG is printer-dialect agnostic, so no
    EZPL is generated; the shop hardware has no network port.
    """
    async with local_session() as db:
        data = await load_label_data(db, instance_id)
        if data is None:
            return f"skip:{instance_id}"
        png_b64 = base64.b64encode(render_label_png(data)).decode()

    redis = ctx.get("redis")  # arq worker context carries its Redis connection
    if redis is not None:
        job = json.dumps({"type": "print", "instance_id": instance_id, "png": png_b64})
        await redis.lpush(PRINT_QUEUE_KEY, job)
        return f"queued:{instance_id}"

    logger.error("Print job %s uchun Redis navbati mavjud emas", instance_id)
    return f"lost:{instance_id}"


async def print_pachka_label(ctx: dict[str, Any], pachka_id: int) -> str:
    """Qadoq chekini chizib navbatga qo'yadi — detal yorlig'i bilan bir xil zanjir."""
    from app.models import Order, Pachka, PachkaItem
    from app.services.labels import PachkaLabelData, render_pachka_label_png

    async with local_session() as db:
        pachka = await db.get(Pachka, pachka_id)
        if pachka is None or pachka.is_deleted:
            return f"skip:{pachka_id}"
        order = await db.get(Order, pachka.order_id)
        count = (
            await db.execute(
                select(func.count())
                .select_from(PachkaItem)
                .where(PachkaItem.pachka_id == pachka.id, PachkaItem.is_deleted == False)  # noqa: E712
            )
        ).scalar_one()
        png_b64 = base64.b64encode(
            render_pachka_label_png(
                PachkaLabelData(
                    code=pachka.code,
                    order_number=order.number if order else "",
                    project_name=(order.project_name if order else "") or "",
                    part_count=int(count),
                    printed_at=datetime.now(UTC).astimezone(TASHKENT_TZ),
                )
            )
        ).decode()

    redis = ctx.get("redis")
    if redis is not None:
        job = json.dumps({"type": "print", "instance_id": pachka_id, "png": png_b64})
        await redis.lpush(PRINT_QUEUE_KEY, job)
        return f"queued:{pachka_id}"

    logger.error("Qadoq cheki %s uchun Redis navbati mavjud emas", pachka_id)
    return f"lost:{pachka_id}"


all_tasks = [print_label, print_pachka_label]
