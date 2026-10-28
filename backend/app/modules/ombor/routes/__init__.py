"""Ombor HTTP yo'llari — `/catalog` va `/stock` (docs/14)."""

from .catalog import router as catalog_router
from .stock import router as stock_router

__all__ = ["catalog_router", "stock_router"]
