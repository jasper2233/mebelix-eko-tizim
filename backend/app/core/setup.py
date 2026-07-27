import asyncio
import logging
from collections.abc import AsyncGenerator, Callable
from contextlib import _AsyncGeneratorContextManager, asynccontextmanager
from typing import Any

import anyio
import fastapi
from arq import create_pool
from arq.connections import RedisSettings as ArqRedisSettings
from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from prometheus_fastapi_instrumentator import Instrumentator
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import text
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.deps import get_current_superuser
from app.core.middleware import RequestLoggingMiddleware
from app.core.utils.rate_limit import rate_limiter
from app.core.ws import ws_manager

from .config import EnvironmentOption, Settings, settings
from .db import async_engine as engine
from .utils import queue


# -------------- connection probes --------------
async def _retry_async(label: str, fn: Callable[[], Any]) -> None:
    """Run `fn` up to STARTUP_RETRY_MAX_ATTEMPTS times, sleeping STARTUP_RETRY_DELAY_SECONDS between tries.

    Cancellation (`KeyboardInterrupt`, `asyncio.CancelledError`) propagates immediately.
    """
    max_attempts = settings.STARTUP_RETRY_MAX_ATTEMPTS
    delay = settings.STARTUP_RETRY_DELAY_SECONDS
    for attempt in range(1, max_attempts + 1):
        try:
            await fn()
            return
        except (asyncio.CancelledError, KeyboardInterrupt):
            logging.info("%s check cancelled by user.", label)
            raise
        except Exception as e:
            if attempt == max_attempts:
                logging.error("%s failed after %s attempts: %s", label, max_attempts, e)
                raise
            logging.warning("%s attempt %s failed: %s. Retrying in %ss...", label, attempt, e, delay)
            await anyio.sleep(delay)


async def check_database_connection() -> None:
    async def _probe() -> None:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logging.info(
            "Database connection successful to %s:%s/%s",
            settings.POSTGRES_SERVER,
            settings.POSTGRES_PORT,
            settings.POSTGRES_DB,
        )

    await _retry_async("Database connection", _probe)


async def check_redis_connection() -> None:
    checks: list[tuple[str, Any]] = []
    if queue.pool is not None:
        checks.append(("Queue", queue.pool))
    if rate_limiter.client is not None:
        checks.append(("RateLimit", rate_limiter.client))

    async def _probe() -> None:
        for _, connection in checks:
            await connection.ping()
        logging.info(
            "Redis connection successful to %s:%s (verified: %s)",
            settings.REDIS_HOST,
            settings.REDIS_PORT,
            ", ".join(name for name, _ in checks),
        )

    await _retry_async("Redis connection", _probe)


# -------------- Redis pools --------------
async def create_redis_queue_pool() -> None:
    queue.pool = await create_pool(ArqRedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT))


async def close_redis_queue_pool() -> None:
    if queue.pool is not None:
        await queue.pool.aclose()  # type: ignore


async def create_redis_rate_limit_pool() -> None:
    rate_limiter.initialize(settings.REDIS_URL)


async def close_redis_rate_limit_pool() -> None:
    if rate_limiter.client is not None:
        await rate_limiter.client.aclose()  # type: ignore[attr-defined]


# -------------- thread pool --------------
def set_threadpool_tokens() -> None:
    """Raise AnyIO's thread-pool size (`THREADPOOL_TOKENS`) so blocking calls don't queue behind each other."""
    anyio.to_thread.current_default_thread_limiter().total_tokens = settings.THREADPOOL_TOKENS


# -------------- application factory --------------
def lifespan_factory(settings: Settings) -> Callable[[FastAPI], _AsyncGeneratorContextManager[Any]]:
    """Build the app lifespan: open Redis pools, verify connections, then yield. Closes pools on shutdown."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator:
        set_threadpool_tokens()
        ws_redis: AsyncRedis | None = None
        try:
            await create_redis_queue_pool()
            await create_redis_rate_limit_pool()
            await check_redis_connection()
            # Real-time bridge (TZ 2.3): cross-worker WS fan-out over Redis pub/sub.
            ws_redis = AsyncRedis.from_url(settings.REDIS_URL)
            await ws_manager.start_listener(ws_redis)

            await check_database_connection()
            yield
        finally:
            await ws_manager.stop_listener()
            if ws_redis is not None:
                await ws_redis.close()
            await close_redis_queue_pool()
            await close_redis_rate_limit_pool()

    return lifespan


def _install_docs_router(application: FastAPI, settings: Settings) -> None:
    """In production: no docs at all. In staging: docs require a superuser. In local: docs are open."""
    if settings.ENVIRONMENT == EnvironmentOption.PRODUCTION:
        return

    deps = [Depends(get_current_superuser)] if settings.ENVIRONMENT != EnvironmentOption.LOCAL else []
    docs_router = APIRouter(dependencies=deps)

    @docs_router.get("/docs", include_in_schema=False)
    async def get_swagger_documentation() -> fastapi.responses.HTMLResponse:
        return get_swagger_ui_html(openapi_url="/openapi.json", title="docs")

    @docs_router.get("/redoc", include_in_schema=False)
    async def get_redoc_documentation() -> fastapi.responses.HTMLResponse:
        return get_redoc_html(openapi_url="/openapi.json", title="docs")

    @docs_router.get("/openapi.json", include_in_schema=False)
    async def openapi() -> dict[str, Any]:
        return get_openapi(title=application.title, version=application.version, routes=application.routes)

    application.include_router(docs_router)


def create_application(
    router: APIRouter,
    settings: Settings,
    **kwargs: Any,
) -> FastAPI:
    """Build the FastAPI app: metadata, lifespan, middleware (CORS + request logging), and env-conditional docs."""
    kwargs.update(
        title=settings.APP_NAME,
        description="MebeliX API",
        license_info={"name": "MIT"},
        # FastAPI's built-in docs are always disabled — we wire our own conditional ones via `_install_docs_router`.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    application = FastAPI(lifespan=lifespan_factory(settings), **kwargs)
    application.include_router(router)
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=settings.CORS_METHODS,
        allow_headers=settings.CORS_HEADERS,
    )
    # Trust X-Forwarded-* from the reverse proxy (Caddy in prod). Without this, `request.client.host` is the
    # proxy IP for every request, which would collapse all users into a single rate-limit bucket.
    # `FORWARDED_ALLOW_IPS=["*"]` is permissive — appropriate when only Caddy/nginx fronts the app.
    application.add_middleware(
        ProxyHeadersMiddleware,  # type: ignore[arg-type]
        trusted_hosts=settings.FORWARDED_ALLOW_IPS,
    )
    _install_metrics(application)
    _install_docs_router(application, settings)
    return application


# Routes excluded from request-count series and the access-log middleware. Single source of truth.
NON_BUSINESS_PATHS: list[str] = ["/metrics", "/api/v1/health", "/api/v1/ready"]


def _install_metrics(application: FastAPI) -> None:
    """Expose Prometheus metrics at `/metrics`. In production, restrict access at the proxy layer
    (Caddy → only allow scrapes from the metrics network) — this endpoint is unauthenticated."""
    Instrumentator(
        excluded_handlers=NON_BUSINESS_PATHS,
    ).instrument(application).expose(application, include_in_schema=False, should_gzip=True)
