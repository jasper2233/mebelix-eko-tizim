"""Obunachini `Host` sarlavhasidan aniqlash (`multi` rejim) — EKO TIZIM TZ §2.4.

Sof ASGI middleware (HTTP va WebSocket ikkalasi uchun). ContextVar shu yerda o'rnatiladi va
ichkaridagi hamma narsa (BaseHTTPMiddleware vazifalari ham) uni meros oladi, shuning uchun u
ENG TASHQI qatlam bo'lishi kerak (`setup.py` da oxirgi `add_middleware`).
"""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.tenancy import current_tenant, is_multi, tenant_from_host
from app.modules.platforma import service as platforma

#: Obunachisiz ishlaydigan yo'llar — konteyner healthcheck'i va monitoring (platforma bazasiga qaraydi)
OPEN_PATHS = frozenset({"/api/v1/health", "/api/v1/ready", "/metrics"})


class TenantMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket") or not is_multi() or scope.get("path") in OPEN_PATHS:
            await self.app(scope, receive, send)
            return
        host = next((v.decode("latin-1") for k, v in scope.get("headers", []) if k == b"host"), "")
        kod = tenant_from_host(host)
        info = await platforma.resolve(kod) if kod else None
        if info is None:
            await _reject(scope, receive, send, 404, "Obunachi topilmadi.")
            return
        if not info.faol:
            await _reject(scope, receive, send, 403, "Obuna to'xtatilgan. Administrator bilan bog'laning.")
            return
        token = current_tenant.set(info.kod)
        try:
            await self.app(scope, receive, send)
        finally:
            current_tenant.reset(token)


async def _reject(scope: Scope, receive: Receive, send: Send, status: int, detail: str) -> None:
    if scope["type"] == "websocket":
        # accept'dan oldin close = qo'l siqishuv rad etiladi (brauzerda 403)
        await send({"type": "websocket.close", "code": 4000 + status, "reason": detail})
        return
    await JSONResponse({"detail": detail}, status_code=status)(scope, receive, send)
