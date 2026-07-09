from typing import Any


async def ping(ctx: dict[str, Any]) -> str:
    """Liveness probe task. ARQ requires at least one registered function; real MES tasks replace this."""
    return "pong"


all_tasks = [ping]
