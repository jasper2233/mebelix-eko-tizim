import base64
import json
import logging
from typing import Any

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


all_tasks = [print_label]
