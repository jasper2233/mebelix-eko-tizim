import logging
from typing import Any

logger = logging.getLogger(__name__)


async def ping(ctx: dict[str, Any]) -> str:
    """Liveness probe task. ARQ requires at least one registered function."""
    return "pong"


all_tasks = [ping]
