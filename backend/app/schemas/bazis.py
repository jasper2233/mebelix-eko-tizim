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
    #: Kod buyurtmadagi mahsulotga tushdimi. Tushmasa model baribir ko'rinadi,
    #: lekin detal kodlari MES detallari bilan bog'lanmaydi.
    matched: bool
    warnings: list[str]
    created_at: datetime


class BazisState(BaseModel):
    """Buyurtmaning 3D holati."""

    models: list[BazisModelRead]
    #: `null` — havola hali ochilmagan yoki bekor qilingan. To'liq manzilni
    #: frontend o'zi yig'adi (`window.location.origin`), server domenni bilmaydi.
    share_token: str | None


class PublicProduct(BaseModel):
    """Ochiq sahifadagi mahsulot kartochkasi."""

    code: str
    name: str
    panels: int


class PublicOrder(BaseModel):
    """Ochiq sahifa sarlavhasi: buyurtma raqami va mahsulotlar."""

    number: str
    products: list[PublicProduct]
