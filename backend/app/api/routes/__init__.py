from fastapi import APIRouter, Depends

from app.api.deps import get_current_user

from .audit import router as audit_router
from .bridge_agents import router as bridge_agents_router
from .clients import router as clients_router
from .employees import router as employees_router
from .health import router as health_router
from .login import router as login_router
from .logout import router as logout_router
from .machines import router as machines_router
from .materials import router as materials_router
from .orders import router as orders_router
from .posts import router as posts_router
from .reports import router as reports_router
from .scans import router as scans_router
from .tablo import router as tablo_router
from .terminal import router as terminal_router
from .users import router as users_router
from .ws import router as ws_router

router = APIRouter(prefix="/v1")
router.include_router(health_router)
router.include_router(login_router)

_protected = [Depends(get_current_user)]
router.include_router(logout_router, dependencies=_protected)
router.include_router(users_router, dependencies=_protected)
router.include_router(clients_router, dependencies=_protected)
router.include_router(employees_router, dependencies=_protected)
router.include_router(machines_router, dependencies=_protected)
router.include_router(posts_router, dependencies=_protected)
router.include_router(materials_router, dependencies=_protected)
router.include_router(orders_router, dependencies=_protected)
router.include_router(audit_router, dependencies=_protected)
router.include_router(terminal_router, dependencies=_protected)
router.include_router(scans_router, dependencies=_protected)
router.include_router(tablo_router, dependencies=_protected)
router.include_router(reports_router, dependencies=_protected)
# Himoyasiz ulanadi: /pair ochiq bo'lishi shart, admin endpointlar o'z ichida AdminUser bilan
router.include_router(bridge_agents_router)
router.include_router(ws_router)  # WebSocket auth is handled inside the endpoint
