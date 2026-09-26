from fastapi import APIRouter, Depends

from app.api.deps import get_current_user

from .audit import router as audit_router
from .bridge_agents import router as bridge_agents_router
from .catalog import router as catalog_router
from .clients import router as clients_router
from .defects import router as defects_router
from .defects_review import router as defects_review_router
from .downtimes import router as downtimes_router
from .employees import router as employees_router
from .health import router as health_router
from .login import router as login_router
from .logout import router as logout_router
from .machines import router as machines_router
from .orders import router as orders_router
from .pachka import router as pachka_router
from .posts import router as posts_router
from .public import router as public_router
from .reports import router as reports_router
from .scans import router as scans_router
from .settings import router as settings_router
from .system import router as system_router
from .tablo import router as tablo_router
from .terminal import router as terminal_router
from .tmo import router as tmo_router
from .users import router as users_router
from .ws import router as ws_router

router = APIRouter(prefix="/v1")
router.include_router(health_router)
router.include_router(login_router)
# Yig'uvchiga beriladigan 3D havola — YAGONA autentifikatsiyasiz modul, shu
# sababli `_protected` dan TASHQARIDA (himoyasi `public.py` da tushuntirilgan).
router.include_router(public_router)

_protected = [Depends(get_current_user)]
router.include_router(logout_router, dependencies=_protected)
router.include_router(users_router, dependencies=_protected)
router.include_router(clients_router, dependencies=_protected)
router.include_router(employees_router, dependencies=_protected)
router.include_router(machines_router, dependencies=_protected)
router.include_router(posts_router, dependencies=_protected)
router.include_router(orders_router, dependencies=_protected)
router.include_router(pachka_router, dependencies=_protected)
router.include_router(tmo_router, dependencies=_protected)
router.include_router(catalog_router, dependencies=_protected)  # mahsulotlar ombori katalogi
router.include_router(audit_router, dependencies=_protected)
router.include_router(terminal_router, dependencies=_protected)
router.include_router(downtimes_router, dependencies=_protected)
router.include_router(defects_router, dependencies=_protected)  # brak qaydi (/terminal prefiksi)
router.include_router(defects_review_router, dependencies=_protected)  # brakni menejer tasdiqlaydi
router.include_router(scans_router, dependencies=_protected)
router.include_router(settings_router, dependencies=_protected)
router.include_router(tablo_router, dependencies=_protected)
router.include_router(reports_router, dependencies=_protected)
router.include_router(system_router, dependencies=_protected)  # «Tizim holati» (admin)
# Himoyasiz ulanadi: /pair ochiq bo'lishi shart, admin endpointlar o'z ichida AdminUser bilan
router.include_router(bridge_agents_router)
router.include_router(ws_router)  # WebSocket auth is handled inside the endpoint
