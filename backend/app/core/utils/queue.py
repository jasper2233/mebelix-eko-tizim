from arq.connections import ArqRedis
from arq.constants import default_queue_name

pool: ArqRedis | None = None

#: Tez navbat — chek chop etish va boshqa soniyalik ishlar (`WorkerSettings`).
#: arq sukuti bilan bir xil: mavjud `enqueue_job(...)` chaqiruvlari o'zgarmasdan shu yerga tushadi.
QUEUE_TEZ = default_queue_name
#: Sekin navbat — hisobotlar, eksport, ESF yuborish, kechki solishtirish (`WorkerSekinSettings`).
#: Tez navbatdagi chekni og'ir ish orqasida kutdirmaslik uchun alohida (EKO TIZIM TZ §2.2).
#: Qo'yish: `pool.enqueue_job("task", ..., _queue_name=QUEUE_SEKIN)`.
QUEUE_SEKIN = "arq:sekin"
