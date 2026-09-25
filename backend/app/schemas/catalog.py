from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class CatalogGroup(BaseModel):
    """Kategoriya daraxtining bitta bandi — `M-LD`, «LDSP dekorlar», 836 pozitsiya."""

    catalog: str
    group_code: str
    group_name: str
    count: int


class CatalogTree(BaseModel):
    """Butun daraxt + har katalogdagi jami. Bitta so'rovda: ro'yxat sahifasi
    ochilishi bilan chap ustun ham, sanoqlar ham kerak bo'ladi."""

    groups: list[CatalogGroup]
    totals: dict[str, int]


class CatalogItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    catalog: str
    group_code: str
    group_name: str
    model_no: int
    variant_no: int
    name: str
    unit: str | None
    size_text: str | None
    thickness_mm: Decimal | None
    article: str | None
    decor_no: int | None
    decor_name: str | None
    matrix: str | None
    image_url: str | None
    quantity: Decimal
    min_quantity: Decimal | None
    location: str | None
    purchase_price: Decimal | None
    sale_price: Decimal | None
    status: str
    note: str | None
    extra: dict[str, Any]


class CatalogItemUpdate(BaseModel):
    """Omborchi tahrirlaydigan maydonlar.

    Kod, nom, guruh va o'lcham ATAYLAB yo'q: ular katalogdan (`Katalog.xlsx` →
    `scripts/catalog_import.py`) keladi va shu yerda o'zgartirilsa keyingi
    yuklashda ustiga yozilardi. Kod esa umuman o'zgarmaydi — katalog qoidasi."""

    quantity: Annotated[Decimal, Field(ge=0, le=10**9)] | None = None
    min_quantity: Annotated[Decimal, Field(ge=0, le=10**9)] | None = None
    location: Annotated[str, Field(max_length=40)] | None = None
    purchase_price: Annotated[Decimal, Field(ge=0, le=10**12)] | None = None
    sale_price: Annotated[Decimal, Field(ge=0, le=10**12)] | None = None
    status: Annotated[str, Field(pattern=r"^(Aktiv|Arxiv)$")] | None = None
    note: Annotated[str, Field(max_length=500)] | None = None
