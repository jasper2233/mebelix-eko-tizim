from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
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
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.deps import get_current_superuser
from app.core.health import check_database_connection, check_redis_connection
from app.core.logger import setup_logging
from app.core.middleware import RequestLoggingMiddleware
from app.core.utils.rate_limit import rate_limiter
from app.core.ws import ws_manager

from .config import EnvironmentOption, settings
from .utils import queue


# -------------- thread pool --------------
def set_threadpool_tokens() -> None:
    """Raise AnyIO's thread-pool size (`THREADPOOL_TOKENS`) so blocking calls don't queue behind each other."""
    anyio.to_thread.current_default_thread_limiter().total_tokens = settings.THREADPOOL_TOKENS


# -------------- application factory --------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Open Redis pools, verify connections, then yield. Closes pools on shutdown."""
    set_threadpool_tokens()
    ws_redis: AsyncRedis | None = None
    try:
        queue.pool = await create_pool(ArqRedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT))
        rate_limiter.initialize(settings.REDIS_URL)
        await check_redis_connection()
        # Real-time bridge (TZ 2.3): cross-worker WS fan-out over Redis pub/sub.
        ws_redis = AsyncRedis.from_url(settings.REDIS_URL)
        await ws_manager.start_listener(ws_redis)

        await check_database_connection()
        yield
    finally:
        await ws_manager.stop_listener()
        if ws_redis is not None:
            await ws_redis.aclose()
        if queue.pool is not None:
            await queue.pool.aclose()  # type: ignore
        if rate_limiter.client is not None:
            await rate_limiter.client.aclose()  # type: ignore[attr-defined]


def _install_docs_router(application: FastAPI) -> None:
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


def create_application(router: APIRouter) -> FastAPI:
    """Build the FastAPI app: metadata, lifespan, middleware (CORS + request logging), and env-conditional docs."""
    setup_logging()
    application = FastAPI(
        lifespan=lifespan,
        title=settings.APP_NAME,
        description="MebeliX API",
        # FastAPI's built-in docs are always disabled — we wire our own conditional ones via `_install_docs_router`.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
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
    # `*` QO'YILMAYDI: unda uvicorn hammaga ishonib XFF'ning eng CHAP (mijoz bergan) qiymatini olardi va
    # header almashtirish rate-limit kalitini nolga qaytarardi. Konkret CIDR (compose tarmog'i) berilganda
    # u o'ngdan chapga yurib birinchi ISHONILMAGAN hop'ni — Caddy haqiqatan ko'rgan mijoz IP'sini — oladi.
    application.add_middleware(
        ProxyHeadersMiddleware,  # type: ignore[arg-type]
        trusted_hosts=settings.FORWARDED_ALLOW_IPS,
    )
    _install_metrics(application)
    _install_docs_router(application)
    return application


# Routes excluded from request-count series and the access-log middleware. Single source of truth.
NON_BUSINESS_PATHS: list[str] = ["/metrics", "/api/v1/health", "/api/v1/ready"]


def _install_metrics(application: FastAPI) -> None:
    """Expose Prometheus metrics at `/metrics` — unauthenticated, so it never leaves the compose network:
    Caddy answers `/metrics` with a plain 403 and the scraper goes straight to `api:8000/metrics` instead."""
    Instrumentator(
        excluded_handlers=NON_BUSINESS_PATHS,
    ).instrument(application).expose(application, include_in_schema=False, should_gzip=True)
