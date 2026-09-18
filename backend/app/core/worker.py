import asyncio
import logging

from arq import cron
from arq.connections import RedisSettings
from arq.worker import Worker

from app.core.health import check_database_connection
from app.core.logger import setup_logging
from app.tasks import IDLE_SWEEP_MINUTES, all_tasks, close_idle_sessions

from .config import settings

try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:  # uvloop is Linux/macOS only; Windows dev runs on the default loop
    pass

setup_logging()  # arq worker entrypoint — JSON logging, xuddi app protsessidagidek
logger = logging.getLogger(__name__)


async def startup(ctx: Worker) -> None:
    logger.info("Worker Started")
    await check_database_connection()


async def shutdown(ctx: Worker) -> None:
    logger.info("Worker Stopped")


class WorkerSettings:
    functions = all_tasks
    # Harakatsiz smenalarni yopish (`services/activity.py`). `unique` (sukut) — bir nechta
    # worker nusxasi bo'lsa ham bitta davrda bitta marta ishlaydi.
    cron_jobs = [cron(close_idle_sessions, minute=set(range(0, 60, IDLE_SWEEP_MINUTES)))]
    redis_settings = RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
    on_startup = startup
    on_shutdown = shutdown
    # handle_signals defaults to True — the worker must catch SIGTERM on `docker stop`
    # so in-flight jobs finish (or re-queue) instead of dying mid-run.
    #
    # Docker healthcheck (`arq ... --check`) Redis'dagi shu yozuvni o'qiydi.
    # arq defaulti 3600s — bir soat: yangi ko'tarilgan worker soat davomida
    # "unhealthy" bo'lib turardi va deploy uni ishlamayapti deb hisoblardi.
    # 30s — healthcheck intervali bilan bir xil.
    health_check_interval = 30
