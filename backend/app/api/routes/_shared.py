"""Router'lar orasida bo'linadigan mayda yordamchilar."""

from collections.abc import Iterable
from typing import Any


def drop_forbidden_nulls(update_data: dict[str, Any], nullable: Iterable[str] = ()) -> dict[str, Any]:
    """PATCH tanasidagi aniq `null`larni tashlab yuboradi.

    Faqat haqiqatan nullable ustunlar null qabul qiladi (`nullable`) — qolganlari
    NOT NULL ustunga tushib IntegrityError (500) berardi.
    """
    allowed = set(nullable)
    return {k: v for k, v in update_data.items() if v is not None or k in allowed}
