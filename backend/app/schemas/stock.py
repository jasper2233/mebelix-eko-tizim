from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import StockCatalog


class StockItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    catalog: StockCatalog
    group_code: str
    group_name: str
    name: str
    variant: str | None
    size: str | None
    unit: str | None
    qty: Decimal
    min_qty: Decimal
    purchase_usd: Decimal | None
    purchase_uzs: Decimal | None
    sale_uzs: Decimal | None
    note: str | None
    created_at: datetime


class StockGroup(BaseModel):
    """Filtr chipi: guruh va undagi pozitsiyalar soni."""

    catalog: StockCatalog
    group_code: str
    group_name: str
    items: int
    low: int


class StockSummary(BaseModel):
    """Sahifa tepasidagi raqamlar — omborchi birinchi shu uchtasiga qaraydi."""

    items: int
    low: int
    #: Qoldiqning xarid narxidagi qiymati (so'm). Narxi yo'q pozitsiya 0 sanaladi.
    value_uzs: Decimal


class StockItemCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str = Field(min_length=3, max_length=20, examples=["F-RC-001-01"])
    catalog: StockCatalog
    group_code: str = Field(min_length=1, max_length=4)
    group_name: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    variant: str | None = Field(default=None, max_length=40)
    size: str | None = Field(default=None, max_length=40)
    unit: str | None = Field(default=None, max_length=16)
    qty: Decimal = Field(default=Decimal(0), ge=0)
    min_qty: Decimal = Field(default=Decimal(0), ge=0)
    purchase_usd: Decimal | None = Field(default=None, ge=0)
    purchase_uzs: Decimal | None = Field(default=None, ge=0)
    sale_uzs: Decimal | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=200)


class StockItemUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    variant: str | None = Field(default=None, max_length=40)
    size: str | None = Field(default=None, max_length=40)
    unit: str | None = Field(default=None, max_length=16)
    qty: Decimal | None = Field(default=None, ge=0)
    min_qty: Decimal | None = Field(default=None, ge=0)
    purchase_usd: Decimal | None = Field(default=None, ge=0)
    purchase_uzs: Decimal | None = Field(default=None, ge=0)
    sale_uzs: Decimal | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=200)


class StockMove(BaseModel):
    """KIRIM / CHIQIM — qoldiqni to'g'ridan-to'g'ri yozish o'rniga o'zgarish miqdori.

    Nega delta: omborchi "20 ta keldi" deb o'ylaydi, "endi 174 ta bo'ldi" deb
    emas. Ikki kishi bir vaqtda yozsa ham delta yo'qolmaydi, absolyut qiymat esa
    bir-birini bosib ketardi.
    """

    delta: Decimal = Field(examples=[20, -5])
    note: str | None = Field(default=None, max_length=200)
