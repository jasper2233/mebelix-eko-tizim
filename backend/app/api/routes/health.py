import logging
from datetime import UTC, datetime

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.health import check_database_health, check_redis_health
from app.schemas.health import HealthCheck, ReadyCheck

router = APIRouter(tags=["health"])

STATUS_HEALTHY = "healthy"
STATUS_UNHEALTHY = "unhealthy"

LOGGER = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _status(ok: bool) -> str:
    return STATUS_HEALTHY if ok else STATUS_UNHEALTHY


@router.get("/health", response_model=HealthCheck)
async def health() -> JSONResponse:
    """Liveness probe — confirm the process is up and the event loop is responsive."""
    payload = {
        "status": STATUS_HEALTHY,
        "environment": settings.ENVIRONMENT.value,
        "version": settings.APP_VERSION,
        "timestamp": _now(),
    }
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload)


@router.get("/ready", response_model=ReadyCheck)
async def ready(db: SessionDep) -> JSONResponse:
    """Readiness probe — verify the app can serve traffic by pinging every external dependency it relies on."""
    database_ok = await check_database_health(db=db)
    redis_ok = await check_redis_health()
    everything_ok = database_ok and redis_ok

    payload = {
        "status": _status(everything_ok),
        "environment": settings.ENVIRONMENT.value,
        "version": settings.APP_VERSION,
        "app": STATUS_HEALTHY,
        "database": _status(database_ok),
        "redis": _status(redis_ok),
        "timestamp": _now(),
    }
    http_status = status.HTTP_200_OK if everything_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=http_status, content=payload)
