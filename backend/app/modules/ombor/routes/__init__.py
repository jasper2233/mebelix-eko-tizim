"""Ombor HTTP yo'llari — `/catalog`, `/stock` (docs/14) va `/ombor` (rezerv, TZ §4.3)."""

from .catalog import router as catalog_router
from .rezerv import router as rezerv_router
from .stock import router as stock_router

__all__ = ["catalog_router", "rezerv_router", "stock_router"]
