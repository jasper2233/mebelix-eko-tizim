"""Structured JSON logging to stdout. 12-factor: the process does not write its own log files."""

import json
import logging
import sys
from typing import Any

_EXTRA_FIELDS = ("request_id", "method", "path", "status_code", "duration_ms")


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in _EXTRA_FIELDS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_logging() -> None:
    """Called explicitly by each long-running entrypoint (create_application, arq worker)."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


# arq CLI o'z dictConfig'ini setup_logging()dan KEYIN qo'llaydi — `--custom-log-dict` bilan
# uzatilmasa arq.* yozuvlari plain + root JSON handleri orqali ikki marta chiqadi.
ARQ_LOG_DICT: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "loggers": {"arq": {"handlers": [], "propagate": True}},
}
