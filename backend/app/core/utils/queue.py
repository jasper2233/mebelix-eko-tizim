from typing import Any

from arq.connections import ArqRedis
from arq.constants import default_queue_name

from app.core.tenancy import tenant

pool: ArqRedis | None = None

#: Tez navbat — chek chop etish va boshqa soniyalik ishlar (`WorkerSettings`).
#: arq sukuti bilan bir xil: mavjud `enqueue_job(...)` chaqiruvlari o'zgarmasdan shu yerga tushadi.
QUEUE_TEZ = default_queue_name
#: Sekin navbat — hisobotlar, eksport, ESF yuborish, kechki solishtirish (`WorkerSekinSettings`).
#: Tez navbatdagi chekni og'ir ish orqasida kutdirmaslik uchun alohida (EKO TIZIM TZ §2.2).
QUEUE_SEKIN = "arq:sekin"

#: Vazifaga obunachini yetkazadigan kalit-argument (`tasks.tenant_task` uni oladi).
#: Pastki chiziqsiz: arq `_` bilan boshlanuvchi argumentlarni o'zi uchun band qilgan.
TENANT_KWARG = "eko_tenant"


async def enqueue(function: str, *args: Any, sekin: bool = False) -> None:
    """Vazifani JORIY obunachi nomidan navbatga qo'yadi. To'g'ridan-to'g'ri `pool.enqueue_job`
    ishlatilmaydi — unda worker vazifani standart obunachi bazasida bajarardi."""
    if pool is None:
        raise RuntimeError("arq navbati ishga tushmagan")
    # kalit nomi = TENANT_KWARG (mypy `**dict` ni arq'ning `_`-argumentlariga solishtirib rad etadi)
    await pool.enqueue_job(function, *args, _queue_name=QUEUE_SEKIN if sekin else QUEUE_TEZ, eko_tenant=tenant())
