"""Buyurtma endpointlari. Bitta faylda to'rt mustaqil masala yashagani uchun
mavzu bo'yicha bo'lingan; prefiks, tag va ro'yxatga olish TARTIBI shu yerda.

Tartib muhim: FastAPI birinchi mos kelgan marshrutni oladi va mos kelmasa
pastga tushmaydi. Fayllar ARO: `trace` `lifecycle` dan oldin ulanadi (`/instances`
aks holda `/{order_id}` deb o'qiladi). Fayl ICHIDA: `/status-counts` `/{order_id}`
dan oldin (`lifecycle`), `/files/scx.zip` `/files/{file_id}` dan oldin (`files`),
`/bazis/share` `/bazis/{file_id}` dan oldin (`bazis`).
"""

from fastapi import APIRouter

from .bazis import router as bazis_router
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
router.include_router(bazis_router)
