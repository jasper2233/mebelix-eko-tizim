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
            raise
        finally:
            perf.inflight.pop(id(request), None)

        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info("request", extra=_extra(response.status_code))
        perf.record_request(
            request.method, _route_template(request), (time.perf_counter() - start) * 1000, response.status_code
        )
        return response


def _route_template(request: Request) -> str:
    """`/api/v1/terminal/labels/8930` -> `/api/v1/terminal/labels/{instance_id}`: har id alohida qator bo'lmasin.

    `scope["route"].path` bu yerda yaramaydi — u ichki routerning o'z yo'li (`/status-counts`),
    ota prefikslarsiz. Shablon haqiqiy yo'ldan, yo'l parametrlarining qiymatini nomi bilan
    almashtirib yasaladi. Route topilmagan (404) so'rovda parametr yo'q — xom yo'l o'rniga bitta nom.
    """
    if request.scope.get("route") is None:
        return "(topilmadi)"
    nomlar = {str(v): k for k, v in request.path_params.items()}
    return "/".join(f"{{{nomlar[s]}}}" if s in nomlar else s for s in request.url.path.split("/"))
