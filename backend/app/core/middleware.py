import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

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

        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info("request", extra=_extra(response.status_code))
        return response
