"""Buyurtma endpointlari. Bitta faylda to'rt mustaqil masala yashagani uchun
mavzu bo'yicha bo'lingan; prefiks, tag va ro'yxatga olish TARTIBI shu yerda.

Tartib muhim: FastAPI birinchi mos kelgan marshrutni oladi va mos kelmasa
pastga tushmaydi. Aynan bir joyda ahamiyatli — `/status-counts` `/{order_id}`
dan oldin (ikkalasi ham `lifecycle` da) va `/files/scx.zip` `/files/{file_id}`
dan oldin (ikkalasi ham `files` da), ya'ni fayl ichidagi tartib saqlansa
yetarli.
"""

from fastapi import APIRouter

from .files import router as files_router
from .lifecycle import router as lifecycle_router
from .matrix import router as matrix_router
from .survey import router as survey_router
from .trace import router as trace_router

router = APIRouter(prefix="/orders", tags=["orders"])
# `trace` BIRINCHI: uning `/instances` yo'li `lifecycle` dagi `/{order_id}` bilan
# raqobatlashadi va FastAPI birinchi mos kelganini oladi.
router.include_router(trace_router)
router.include_router(lifecycle_router)
router.include_router(matrix_router)
router.include_router(files_router)
router.include_router(survey_router)
