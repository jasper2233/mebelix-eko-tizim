"""Shared production volume math (TZ 9.3.1 HAJM / 4.3 capacity forecast)."""

from app.models import Part


def part_volume(part: Part, post_code: str) -> float:
    """Full-part volume in the post's unit. ponytail: PAZ meters approximated as pieces —
    groove lengths are not persisted per part; upgrade when reports need exact meters."""
    if post_code == "ARRA":
        return ((part.length or 0) * (part.width or 0) / 1_000_000) * part.count
    if post_code == "KROMKA":
        total = 0.0
        for side in part.edges:
            total += (part.width or 0) if side in ("l", "r") else (part.length or 0)
        return total * part.count / 1000
    return float(part.count)
