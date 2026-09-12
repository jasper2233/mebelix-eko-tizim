"""Shared production volume math (HAJM)."""

from dataclasses import dataclass
from typing import Any

from app.models.enums import PostCode


@dataclass(slots=True)
class VolumeShare:
    """Detalning BITTA postdagi hajmi va o'sha postdagi marshrut qatorlari yig'indisi.

    `part_volume` TO'LIQ detal hajmini beradi, marshrutda esa bitta post ikki qator
    berishi mumkin — takror kod (`[3, 6, 3]`) yoki bitta postga tushadigan ikki xil
    amal (Raspil+45°, Kromka+Fasat). Shuning uchun hajm juftlik uchun BIR MARTA
    yoziladi (`volume`), ulush esa o'sha juftlikning HAMMA qatoridan yig'iladi.

    Ulushni birinchi uchragan qatordan olish YARAMAYDI: `tablo.py`/`reports.py`
    so'rovlarida `ORDER BY` yo'q, ya'ni qator tartibi heap tartibi — bitta qator
    yangilanishi (skan, `autovacuum`) bilan o'zgaradi va devordagi HAJM bir xil
    ma'lumotda 100% dan 0% ga sakrardi (o'lchangan). Yig'indi esa barqaror va
    SONI ustuni bilan bir xil javob beradi: 8/10 -> 80%.
    """

    volume: float
    #: Ulush surati — chaqiruvchiga qarab BAJARILGAN (tablo) yoki QOLGAN (dashboard) skanlar
    scans: int = 0
    #: Ulush maxraji — o'sha juftlikdagi hamma qatorning `total_required` yig'indisi
    required: int = 0

    def share(self) -> float:
        """Hajmning `scans/required` ulushi; qator talab qilmasa — 0."""
        return self.volume * (self.scans / self.required) if self.required else 0.0


def part_volume(
    post_code: str, *, length: float | None, width: float | None, count: int, edges: dict[str, Any]
) -> float:
    """Full-part volume in the post's unit.

    Obyekt emas, qiymatlar qabul qiladi: TABLO o'n minglab marshrutni to'liq ORM
    obyekti sifatida qurmay, faqat shu to'rt ustunni tanlay olsin (669 ms -> 175 ms).

    ponytail: OVAL (birligi metr) dona bilan approksimatsiya qilinadi — egri
    qirra uzunligi detal bo'yicha saqlanmaydi; hisobot aniq birlik so'raganda
    yangilanadi.
    """
    if post_code in (PostCode.ARRA, PostCode.UPAKOVKA):
        return ((length or 0) * (width or 0) / 1_000_000) * count
    if post_code == PostCode.KROMKA:
        total = 0.0
        for side in edges:
            total += (width or 0) if side in ("l", "r") else (length or 0)
        return total * count / 1000
    return float(count)
