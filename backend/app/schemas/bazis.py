"""Bazis 3D modellari: texnolog paneli va OCHIQ havola javoblari.

Ochiq javoblarda mijoz ma'lumoti, narx va ichki holat YO'Q — havolani usta ham,
mijoz ham ochadi, kim ekani bilinmaydi (`docs/13` §5).
"""

from datetime import datetime

from pydantic import BaseModel


class BazisModelRead(BaseModel):
    """Bitta `.b3d` = bitta mahsulot. Texnolog ro'yxatida shu ko'rinadi."""

    file_id: int
    product_code: str
    product_name: str
    filename: str
    size: int | None
    panels: int
    #: Kod buyurtmadagi (tirik) mahsulotga tushadimi — O'QISHDA hisoblanadi, `.project`
    #: qayta yuklansa ham to'g'ri qoladi. Tushmasa model baribir ko'rinadi, lekin
    #: chekdagi Detal ID uning detallarini topmaydi.
    matched: bool
    #: Parser va tasdiq ogohlantirishlari. «Mahsulot topilmadi» bu yerda YO'Q —
    #: u `matched` ning o'zi (frontend holat sifatida ko'rsatadi).
    warnings: list[str]
    created_at: datetime


class BazisProductRead(BaseModel):
    """Buyurtmadagi mahsulot (`.project` dan) — 3D ro'yxatining bir qatori."""

    code: str
    name: str
    count: int


class BazisState(BaseModel):
    """Buyurtmaning 3D holati."""

    models: list[BazisModelRead]
    #: Buyurtma mahsulotlari: qaysi biriga model yetishmayotgani shundan ko'rinadi
    products: list[BazisProductRead]
    #: `null` — havola hali ochilmagan yoki bekor qilingan. To'liq manzilni
    #: frontend o'zi yig'adi (`window.location.origin`), server domenni bilmaydi.
    share_token: str | None


class PublicProduct(BaseModel):
    """Ochiq sahifadagi mahsulot kartochkasi."""

    code: str
    name: str
    panels: int
    #: Model buyurtmadagi mahsulotga bog'langanmi. Bog'lanmagan modelda chekdagi
    #: Detal ID ishlamaydi — ustaga detal nomi bilan qidirish aytiladi.
    linked: bool


class PublicOrder(BaseModel):
    """Ochiq sahifa sarlavhasi: buyurtma raqami va mahsulotlar."""

    number: str
    products: list[PublicProduct]
