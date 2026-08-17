from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PaymentMethod, SaleStatus, StockCatalog, StockMoveKind


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
    """Filtr chipi: guruh va undagi tovarlar soni."""

    catalog: StockCatalog
    group_code: str
    group_name: str
    items: int
    low: int


class StockSummary(BaseModel):
    """Sahifa tepasidagi raqamlar — omborchi birinchi shu uchtasiga qaraydi."""

    items: int
    low: int
    #: Qoldiqning xarid narxidagi qiymati (so'm). Narxi yo'q tovar 0 sanaladi.
    value_uzs: Decimal


class StockItemCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    #: Bo'sh qoldirilsa server o'zi beradi: guruhdagi eng katta model raqami + 1
    #: (`F-RC-032-01`). Mavjud modelning yangi VARIANTI kerak bo'lsa (masalan
    #: o'sha ruchkaning boshqa rangi) kod qo'lda yoziladi — `F-RC-001-04`.
    code: str | None = Field(default=None, min_length=3, max_length=20, examples=["F-RC-001-04"])
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


class StockMoveRequest(BaseModel):
    """KIRIM / CHIQIM — qoldiqni to'g'ridan-to'g'ri yozish o'rniga o'zgarish miqdori.

    Nega delta: omborchi "20 ta keldi" deb o'ylaydi, "endi 174 ta bo'ldi" deb
    emas. Ikki kishi bir vaqtda yozsa ham delta yo'qolmaydi, absolyut qiymat esa
    bir-birini bosib ketardi.

    `kind=buyurtma` da `order_id` MAJBURIY: tannarx qaysi buyurtmaga tushishini
    bilmasak, harakatning ma'nosi qolmaydi. `sotuv` bu yerda QABUL QILINMAYDI —
    u `POST /stock/sales` orqali, chunki sotuvda hujjat, mijoz va to'lov bo'ladi.
    """

    delta: Decimal = Field(examples=[20, -5])
    kind: StockMoveKind = StockMoveKind.KIRIM
    order_id: int | None = None
    price_uzs: Decimal | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=200)


class StockMoveRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_item_id: int
    item_code: str = ""
    item_name: str = ""
    qty: Decimal
    kind: StockMoveKind
    order_id: int | None
    order_number: str | None = None
    sale_id: int | None
    price_uzs: Decimal | None
    note: str | None
    user_name: str | None = None
    created_at: datetime


class SaleLine(BaseModel):
    """Sotuv satri. Narx bo'sh bo'lsa katalogdagi sotuv narxi olinadi."""

    item_id: int
    qty: Decimal = Field(gt=0)
    price_uzs: Decimal | None = Field(default=None, ge=0)


class SaleCreate(BaseModel):
    """Ombordan sotuv. To'lov ixtiyoriy — to'lanmasa qarz bo'lib qoladi."""

    lines: list[SaleLine] = Field(min_length=1)
    #: Qarzga sotilganda MAJBURIY — kimdan undirishni bilish kerak
    client_id: int | None = None
    paid_uzs: Decimal = Field(default=Decimal(0), ge=0)
    method: PaymentMethod = PaymentMethod.CASH
    note: str | None = Field(default=None, max_length=200)


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount_uzs: Decimal
    method: PaymentMethod
    note: str | None
    user_name: str | None = None
    created_at: datetime


class PaymentCreate(BaseModel):
    amount_uzs: Decimal = Field(gt=0)
    method: PaymentMethod = PaymentMethod.CASH
    note: str | None = Field(default=None, max_length=200)


class SaleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int | None
    client_name: str | None = None
    total_uzs: Decimal
    paid_uzs: Decimal
    debt_uzs: Decimal = Decimal(0)
    status: SaleStatus
    note: str | None
    user_name: str | None = None
    created_at: datetime
    lines: list[StockMoveRead] = []
    payments: list[PaymentRead] = []


class SaleSummary(BaseModel):
    """Sotuv sahifasining tepasi: davr savdosi va umumiy qarz."""

    sales: int
    total_uzs: Decimal
    paid_uzs: Decimal
    debt_uzs: Decimal
