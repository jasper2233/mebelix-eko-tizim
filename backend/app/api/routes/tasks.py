from typing import Any

from arq.jobs import Job as ArqJob
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CurrentUser
from app.core.config import settings
from app.core.utils import queue
from app.core.utils.rate_limit import RateLimit
from app.schemas.job import Job

router = APIRouter(prefix="/tasks", tags=["tasks"])

_TASK_RATE_LIMIT = RateLimit(
    limit=settings.DEFAULT_RATE_LIMIT_LIMIT, period=settings.DEFAULT_RATE_LIMIT_PERIOD
)


def _require_queue() -> None:
    if queue.pool is None:
        raise HTTPException(status_code=503, detail="Navbat xizmati ishlamayapti")


@router.post(
    "/task",
    response_model=Job,
    status_code=201,
    dependencies=[Depends(_TASK_RATE_LIMIT)],
)
async def create_task(
    message: str,
    current_user: CurrentUser,
) -> dict[str, str]:
    """Enqueue a sample background task and return its job id."""
    _require_queue()
    assert queue.pool is not None  # narrowed for type-checker
    job = await queue.pool.enqueue_job("sample_background_task", message)
    if job is None:
        raise HTTPException(status_code=500, detail="Vazifani yaratib bo'lmadi")
    return {"id": job.job_id}


@router.get("/task/{task_id}")
async def get_task(
    task_id: str,
    current_user: CurrentUser,
) -> dict[str, Any] | None:
    """Look up an ARQ job by id. Returns `None` if the job has expired from Redis."""
    _require_queue()
    assert queue.pool is not None
    job_info = await ArqJob(task_id, queue.pool).info()
    return job_info.__dict__ if job_info is not None else None
