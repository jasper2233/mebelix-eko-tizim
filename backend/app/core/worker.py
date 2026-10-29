import asyncio
import logging

from arq import cron
from arq.connections import RedisSettings
from arq.worker import Worker

from app.core.health import check_database_connection
from app.core.logger import setup_logging
from app.tasks import (
    DOWNTIME_SWEEP_MINUTES,
    IDLE_SWEEP_MINUTES,
    REZERV_SWEEP_MINUTES,
    all_tasks,
    bux_sinxron_all,
    close_idle_sessions_all,
    expire_reservations_all,
    kroy_katalog_all,
    kroy_outbox_all,
    ombor_solishtirish_all,
    soliq_esf_all,
    sync_downtimes_all,
)

from .config import settings
from .utils.queue import QUEUE_SEKIN

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
    cron_jobs = [
        cron(close_idle_sessions_all, minute=set(range(0, 60, IDLE_SWEEP_MINUTES))),
        # Pico to'xtashlarini yozish (`services/downtimes.py`) — terminal o'chiq bo'lsa ham
        cron(sync_downtimes_all, minute=set(range(0, 60, DOWNTIME_SWEEP_MINUTES))),
        # To'lov muddati o'tgan rezervlarni bo'shatish (EKO TZ §4.3)
        cron(expire_reservations_all, minute=set(range(0, 60, REZERV_SWEEP_MINUTES))),
        # Kechki ombor solishtirishi (EKO 2.4): 21:30 UTC = 02:30 Toshkent, ish yo'q payt
        cron(ombor_solishtirish_all, hour={21}, minute={30}),
        # MES → MX Kroy xabarlari (EKO 3d): har daqiqa; MX javob bermasa navbatda qoladi
        cron(kroy_outbox_all, second={15}),
        cron(soliq_esf_all, second={45}),  # ESF navbati (EKO 6)
        cron(bux_sinxron_all, minute=set(range(2, 60, 5))),  # provodkalar sinxroni (EKO 7)
        # MES katalogi → MX (EKO 3e, K5): faqat o'zgarganlari, navbat orqali
        cron(kroy_katalog_all, minute=set(range(0, 60, 10)), second={40}),
    ]
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


class WorkerSekinSettings:
    """Sekin navbat ishchisi (`QUEUE_SEKIN`). Funksiyalar bir xil — qaysi navbatga tushishini
    chaqiruvchi hal qiladi. Cron'lar faqat tez ishchida: ikki marta ishlamasin.

    `WorkerSettings` dan MEROS OLINMAYDI: arq sozlamalarni `cls.__dict__` dan o'qiydi va meros
    maydonlarni ko'rmaydi — o'lchandi: funksiyasiz «at least one function» bilan yiqildi va
    `--check` sukutdagi 6379 portga ulanmoqchi bo'ldi.
    """

    functions = all_tasks
    queue_name = QUEUE_SEKIN
    redis_settings = WorkerSettings.redis_settings
    on_startup = startup
    on_shutdown = shutdown
    health_check_interval = WorkerSettings.health_check_interval
