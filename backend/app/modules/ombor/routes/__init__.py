"""Ombor HTTP yo'llari — `/catalog`, `/stock` (docs/14) va `/ombor` (rezerv, TZ §4.3)."""

from .berish import router as berish_router
from .catalog import router as catalog_router
from .rezerv import router as rezerv_router
from .sex import router as sex_router
from .stock import router as stock_router

__all__ = ["berish_router", "catalog_router", "rezerv_router", "sex_router", "stock_router"]
