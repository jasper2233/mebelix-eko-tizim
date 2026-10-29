"""API router ro'yxati — kompozitsiya ildizi: hamma router shu yerda ulanadi.

Alohida faylda (paket `__init__` ida emas): `app.api.deps` yoki `app.api.routes._shared` ni import
qilgan modul butun router daraxtini o'zi bilan tortmasin. Aks holda modul marshrutidan boshlangan
import (skript, orakl) aylana importga tushardi.
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.routes.audit import router as audit_router
from app.api.routes.bridge_agents import router as bridge_agents_router
from app.api.routes.clients import router as clients_router
from app.api.routes.defects import router as defects_router
from app.api.routes.defects_review import router as defects_review_router
from app.api.routes.downtimes import router as downtimes_router
from app.api.routes.employees import router as employees_router
from app.api.routes.health import router as health_router
from app.api.routes.kromka_kalib import router as kromka_kalib_router
from app.api.routes.login import router as login_router
from app.api.routes.logout import router as logout_router
from app.api.routes.machines import router as machines_router
from app.api.routes.orders import router as orders_router
from app.api.routes.pachka import router as pachka_router
from app.api.routes.posts import router as posts_router
from app.api.routes.public import router as public_router
from app.api.routes.reports import router as reports_router
from app.api.routes.scans import router as scans_router
from app.api.routes.settings import router as settings_router
from app.api.routes.system import router as system_router
from app.api.routes.tablo import router as tablo_router
from app.api.routes.terminal import router as terminal_router
from app.api.routes.terminal_devices import router as terminal_devices_router
from app.api.routes.tmo import router as tmo_router
from app.api.routes.users import router as users_router
from app.api.routes.ws import router as ws_router
from app.modules.integratsiya.routes import router as integ_router
from app.modules.ombor.routes import berish_router, catalog_router, kroy_router, rezerv_router, sex_router, stock_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(health_router)
v1_router.include_router(login_router)
# Yig'uvchiga beriladigan 3D havola — YAGONA autentifikatsiyasiz modul, shu
# sababli `_protected` dan TASHQARIDA (himoyasi `public.py` da tushuntirilgan).
v1_router.include_router(public_router)

_protected = [Depends(get_current_user)]
v1_router.include_router(logout_router, dependencies=_protected)
v1_router.include_router(users_router, dependencies=_protected)
v1_router.include_router(clients_router, dependencies=_protected)
v1_router.include_router(employees_router, dependencies=_protected)
v1_router.include_router(machines_router, dependencies=_protected)
v1_router.include_router(kromka_kalib_router, dependencies=_protected)  # Kromka kalibrlash (admin)
v1_router.include_router(posts_router, dependencies=_protected)
v1_router.include_router(orders_router, dependencies=_protected)
v1_router.include_router(pachka_router, dependencies=_protected)
v1_router.include_router(tmo_router, dependencies=_protected)
v1_router.include_router(catalog_router, dependencies=_protected)  # mahsulotlar ombori katalogi
v1_router.include_router(stock_router, dependencies=_protected)  # ombor hujjatlari va FIFO (docs/14 §9)
v1_router.include_router(rezerv_router, dependencies=_protected)  # rezerv va ta'minot (EKO TZ §4.3)
v1_router.include_router(berish_router, dependencies=_protected)  # sexga berish, barkodlar (EKO TZ §4.4)
v1_router.include_router(sex_router, dependencies=_protected)  # sexdan so'rov, rulon tugadi (EKO TZ §4.4)
# MX Kroy (EKO TZ §6, K3/K4): foydalanuvchi emas — xizmat tokeni (`KROY_API_TOKEN`), shuning uchun _protected YO'Q
v1_router.include_router(kroy_router)
v1_router.include_router(integ_router)
v1_router.include_router(audit_router, dependencies=_protected)
v1_router.include_router(terminal_router, dependencies=_protected)
v1_router.include_router(terminal_devices_router, dependencies=_protected)
v1_router.include_router(downtimes_router, dependencies=_protected)
v1_router.include_router(defects_router, dependencies=_protected)  # brak qaydi (/terminal prefiksi)
v1_router.include_router(defects_review_router, dependencies=_protected)  # brakni menejer tasdiqlaydi
v1_router.include_router(scans_router, dependencies=_protected)
v1_router.include_router(settings_router, dependencies=_protected)
v1_router.include_router(tablo_router, dependencies=_protected)
v1_router.include_router(reports_router, dependencies=_protected)
v1_router.include_router(system_router, dependencies=_protected)  # «Tizim holati» (admin)
# Himoyasiz ulanadi: /pair ochiq bo'lishi shart, admin endpointlar o'z ichida AdminUser bilan
v1_router.include_router(bridge_agents_router)
v1_router.include_router(ws_router)  # WebSocket auth is handled inside the endpoint

router = APIRouter(prefix="/api")
router.include_router(v1_router)
