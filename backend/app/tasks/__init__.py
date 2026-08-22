import base64
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy import Row
    from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import TASHKENT_TZ
from app.core.db import local_session
from app.services.labels import load_label_data, render_label_png

logger = logging.getLogger(__name__)

PRINT_QUEUE_KEY = "mes:print:queue"  # bridge-agent drains this list (TZ 2.2.2)


def print_queue_key(agent_id: int | None) -> str:
    """Chek navbati kaliti. `agent_id` berilsa — FAQAT o'sha agentniki.

    Ilgari navbat bitta umumiy ro'yxat edi va har ulangan agent undan `BRPOP`
    qilardi. Ikki printer ulanganda (Arra-1 va Prisadka-1) chek qaysi biriga
    tushishi tasodif bo'lib qolardi: arrachi bosgan yorliqning taxminan yarmi
    prisadka printeridan chiqar, arrachi esa "chek chiqarildi" yozuvini ko'rib
    turib qog'ozni kutardi. Bekor qilib qayta bosish yordam bergandek tuyulardi,
    chunki u yangi tasodif edi.

    Manzilsiz job (beyjik, ish markazi biriktirilmagan terminal) umumiy
    ro'yxatda qoladi — uni istalgan printer oladi, ya'ni eski xatti-harakat
    saqlanadi.
    """
    return PRINT_QUEUE_KEY if agent_id is None else f"{PRINT_QUEUE_KEY}:{agent_id}"


#: Agent `last_seen_at` ni har 5 daqiqada yangilaydi — 6 daqiqadan yangi bo'lsa
#: onlayn hisoblanadi (frontend `printers.tsx` bilan AYNAN bir xil chegara).
AGENT_ONLINE_WINDOW = timedelta(minutes=6)


async def printer_agent(db: "AsyncSession", machine_id: int | None) -> "Row | None":
    """Shu ish markazidagi chop etadigan agent: `(id, last_seen_at)`. Yo'q bo'lsa `None`.

    Agent ish markaziga `bridge_agent.machine_id` orqali bog'langan, ish markazi
    esa postga. Ya'ni "qaysi printer" savoliga javob bazada allaqachon bor edi,
    faqat chek jo'natishda ishlatilmasdi.
    """
    from app.models import BridgeAgent

    if machine_id is None:
        return None
    return (
        (
            await db.execute(
                select(BridgeAgent.id, BridgeAgent.last_seen_at).where(
                    BridgeAgent.machine_id == machine_id,
                    BridgeAgent.can_print == True,  # noqa: E712
                    BridgeAgent.token_hash.is_not(None),  # juftlanmagan agent chek ololmaydi
                    BridgeAgent.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .first()
    )


def _print_job(instance_id: int, png_b64: str) -> str:
    """Bitta chop etish topshirig'i. `job_id` — HAR YUBORISHDA yangi.

    Agent shu `job_id` bo'yicha takrorni tashlaydi. `instance_id` bu vazifani
    bajara OLMAYDI: chek bekor qilinganda o'sha nusxa qayta ishlatiladi
    (`terminal.py` da `label_printed_at = None`), ya'ni qayta chiqarishda
    `instance_id` bir xil keladi — u bo'yicha filtrlash operatorning yagona
    tuzatish yo'lini yopib qo'yardi.
    """
    return json.dumps({"type": "print", "job_id": uuid4().hex, "instance_id": instance_id, "png": png_b64})


async def print_label(ctx: dict[str, Any], instance_id: int, agent_id: int | None = None) -> str:
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
        job = _print_job(instance_id, png_b64)
        await redis.lpush(print_queue_key(agent_id), job)
        return f"queued:{instance_id}"

    logger.error("Print job %s uchun Redis navbati mavjud emas", instance_id)
    return f"lost:{instance_id}"


async def print_pachka_label(ctx: dict[str, Any], pachka_id: int, agent_id: int | None = None) -> str:
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
        job = _print_job(pachka_id, png_b64)
        await redis.lpush(print_queue_key(agent_id), job)
        return f"queued:{pachka_id}"

    logger.error("Qadoq cheki %s uchun Redis navbati mavjud emas", pachka_id)
    return f"lost:{pachka_id}"


async def print_badge(ctx: dict[str, Any], employee_id: int, agent_id: int | None = None) -> str:
    """Hodim beyjigini chizib navbatga qo'yadi — detal cheki bilan bir xil zanjir.

    Brauzerdan chop etish o'rniga: u drayverdagi saqlangan qog'oz o'lchamiga
    tayanardi va 80x60 bo'lmasa kontent yorliqqa mos tushmasdi.
    """
    from app.models import Employee
    from app.services.labels import BadgeLabelData, render_badge_png

    async with local_session() as db:
        employee = await db.get(Employee, employee_id)
        if employee is None or employee.is_deleted:
            return f"skip:{employee_id}"
        png_b64 = base64.b64encode(
            render_badge_png(
                BadgeLabelData(
                    full_name=employee.full_name,
                    position=employee.position or "",
                    badge_id=employee.badge_id,
                )
            )
        ).decode()

    redis = ctx.get("redis")
    if redis is not None:
        job = _print_job(employee_id, png_b64)
        await redis.lpush(print_queue_key(agent_id), job)
        return f"queued:{employee_id}"

    logger.error("Beyjik %s uchun Redis navbati mavjud emas", employee_id)
    return f"lost:{employee_id}"


all_tasks = [print_label, print_pachka_label, print_badge]
