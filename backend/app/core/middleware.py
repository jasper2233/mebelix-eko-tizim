import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core import perf

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach an `X-Request-ID` to every request and log a structured summary on completion."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # Local import keeps this module free of `setup` dependencies during initial app construction.
        from app.core.setup import NON_BUSINESS_PATHS

        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        # Xato ishlovchilari javobga header qo'sha olishi uchun.
        request.state.request_id = request_id

        if request.url.path in NON_BUSINESS_PATHS:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response

        start = time.perf_counter()
        # «Tizim holati»: loop bloklanganda qaysi so'rovlar ishlab turgani (`core/perf.py`)
        perf.inflight[id(request)] = (request.url.path, start)

        def _extra(status_code: int) -> dict[str, object]:
            return {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            }

        try:
            response = await call_next(request)
        except BaseException:
            # Ushlanmagan istisno ham strukturali logga tushsin, keyin yuqoriga uzatiladi.
            logger.exception("request", extra=_extra(500))
            # «Tizim holati» ham: aks holda yiqilgan so'rov 5xx ustunidan ham, vaqtlardan ham tushib qolardi
            perf.record_request(request.method, _route_template(request), (time.perf_counter() - start) * 1000, 500)
            raise
        finally:
            perf.finish(id(request))

        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info("request", extra=_extra(response.status_code))
        perf.record_request(
            request.method, _route_template(request), (time.perf_counter() - start) * 1000, response.status_code
        )
        return response


def _route_template(request: Request) -> str:
    """`/api/v1/terminal/labels/8930` -> `/api/v1/terminal/labels/{instance_id}`: har id alohida qator bo'lmasin.

    `scope["route"].path` — ichki routerning O'Z shabloni, ota prefikslarsiz (`/{order_id}/matrix`);
    u haqiqiy yo'lning OXIRI. Prefiks (parametrsiz) haqiqiy yo'lning boshidan olinadi. Qiymat
    bo'yicha almashtirish emas: id statik segmentga yoki boshqa id ga teng bo'lsa (`/orders/5/files/5`)
    noto'g'ri qator yasardi. Route topilmagan (404) so'rov — xom yo'l o'rniga bitta nom.
    """
    route = request.scope.get("route")
    shablon = getattr(route, "path", None)
    if not isinstance(shablon, str):
        return "(topilmadi)"
    qism = shablon.strip("/").split("/") if shablon.strip("/") else []
    yol = request.url.path.strip("/").split("/")
    return "/" + "/".join(yol[: len(yol) - len(qism)] + qism)
