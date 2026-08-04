"""Shared production volume math (TZ 9.3.1 HAJM / 4.3 capacity forecast)."""

from typing import Any

from app.models.enums import PostCode


def part_volume(
    post_code: str, *, length: float | None, width: float | None, count: int, edges: dict[str, Any]
) -> float:
    """Full-part volume in the post's unit.

    Obyekt emas, qiymatlar qabul qiladi: TABLO o'n minglab marshrutni to'liq ORM
    obyekti sifatida qurmay, faqat shu to'rt ustunni tanlay olsin (669 ms -> 175 ms).

    ponytail: PAZ meters approximated as pieces — groove lengths are not persisted
    per part; upgrade when reports need exact meters.
    """
    if post_code == PostCode.ARRA:
        return ((length or 0) * (width or 0) / 1_000_000) * count
    if post_code == PostCode.KROMKA:
        total = 0.0
        for side in edges:
            total += (width or 0) if side in ("l", "r") else (length or 0)
        return total * count / 1000
    return float(count)
