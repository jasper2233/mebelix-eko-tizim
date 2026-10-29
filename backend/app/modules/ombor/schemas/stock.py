from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Text200 = Annotated[str, Field(max_length=200)]
DocKind = Literal["kirim", "chiqim", "sex"]


class DocLineIn(BaseModel):
    """Hujjat qatori. Qoralamada `item_id` bo'sh bo'lishi mumkin (nom yozilgan, tanlanmagan) —
    tasdiqlashda bunday qator rad etiladi."""

    item_id: int | None = None
    name: Text200 = ""
    qty: Annotated[Decimal, Field(ge=0, le=10**9)] = Decimal(0)
    #: kirimda DOLLAR, chiqimda so'm
    price: Annotated[Decimal, Field(ge=0, le=10**12)] = Decimal(0)
    discount: Annotated[Decimal, Field(ge=0, le=10**12)] = Decimal(0)
    note: Text200 = ""
    #: Kirim, metrdagi pozitsiya: bitta rulon uzunligi (bo'sh — katalogdagi `birlik_hajm`)
    hajm: Annotated[Decimal, Field(gt=0, le=10**6)] | None = None


class DocIn(BaseModel):
    """Hujjat — qoralama sifatida saqlash yoki tasdiqlash uchun. `id` berilsa — o'sha qoralama."""

    id: int | None = None
    kind: DocKind
    doc_date: date
    #: Dizayndagi bosh qism maydonlari (`client`, `supplier`, `rate` ...) — matn sifatida
    head: dict[Annotated[str, Field(max_length=20)], Text200] = Field(default_factory=dict, max_length=20)
    lines: Annotated[list[DocLineIn], Field(max_length=500)] = Field(default_factory=list)


class DocLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    line_no: int
    item_id: int | None
    code: str | None = None
    unit: str | None = None
    catalog: str | None = None
    name: str
    qty: Decimal
    price: Decimal
    discount: Decimal
    note: str
    cost: Decimal | None
    #: Inventarizatsiya: hisobdagi qoldiq (`qty` — sanalgani)
    book_qty: Decimal | None = None
    hajm: Decimal | None = None


class DocRead(BaseModel):
    id: int
    no: str
    kind: str
    status: str
    doc_date: date
    head: dict[str, str]
    rate: Decimal | None
    total: Decimal
    cogs: Decimal | None
    confirmed_at: datetime | None
    created_at: datetime
    lines: list[DocLineRead]


class DocRow(BaseModel):
    """«Hujjatlar» ro'yxatining qatori."""

    id: int
    no: str
    kind: str
    status: str
    doc_date: date
    #: Kim bilan: mijoz yoki yetkazib beruvchi (+ buyurtma / faktura)
    who: str
    rows: int
    total: Decimal
    cogs: Decimal | None
    rate: Decimal | None
    confirmed_at: datetime | None
    created_at: datetime


class LotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    received_on: date
    source: str
    qty: Decimal
    qty_left: Decimal
    unit_cost: Decimal
    usd: Decimal | None


class MoveRead(BaseModel):
    id: int
    created_at: datetime
    item_id: int
    code: str
    name: str
    kind: str
    qty: Decimal
    balance: Decimal
    amount: Decimal | None
    note: str
    doc_id: int | None
    doc_no: str | None


class ItemHistory(BaseModel):
    """Kartochka: QOLGAN partiyalar (eng eskisi birinchi — keyingi chiqim shundan) va harakatlar."""

    lots: list[LotRead]
    moves: list[MoveRead]
    #: Keyingi chiqimning bir birlik tannarxi (eng eski partiya), so'm
    next_cost: Decimal | None


class InventoryCount(BaseModel):
    item_id: int
    #: Sanalgan HAQIQIY miqdor
    qty: Annotated[Decimal, Field(ge=0, le=10**9)]


class InventoryIn(BaseModel):
    """Inventarizatsiya: sanalgan pozitsiyalar — farqi qoldiqqa yoziladi, `INV` hujjati tasdiqlangan holda."""

    doc_date: date
    #: `group` (sanalgan guruh, `F-RC`), `note`
    head: dict[Annotated[str, Field(max_length=20)], Text200] = Field(default_factory=dict, max_length=10)
    counts: Annotated[list[InventoryCount], Field(min_length=1, max_length=5000)]


class SexLogRow(BaseModel):
    """«Sex sarfi» jurnali qatori — kim, qachon, qaysi uskuna uchun nima oldi."""

    doc_id: int
    doc_no: str
    doc_date: date
    taker: str
    equip: str
    order: str
    giver: str
    item_id: int
    code: str
    name: str
    unit: str | None
    qty: Decimal
    amount: Decimal | None


class ReportGroupRow(BaseModel):
    """«Guruh bo'yicha qoldiq va aylanma» qatori — dizayndagi `repRows`."""

    catalog: str
    group_code: str
    group_name: str
    #: Guruhdagi pozitsiyalar soni
    positions: int
    #: Oraliqdagi kirim va chiqim MIQDORI (birliklar aralash — guruh ichida bitta birlik bo'ladi)
    qty_in: Decimal
    qty_out: Decimal
    #: Qoldiq qiymati, so'm
    value: Decimal


class ReportAbcRow(BaseModel):
    """ABC sinfi: nechta pozitsiya va qoldiq qiymatining qancha qismi."""

    cls: Literal["A", "B", "C"]
    positions: int
    value: Decimal
    pct: int


class ReportDeadRow(BaseModel):
    """«Harakatsiz tovar»: qoldig'i bor, lekin oraliqda bitta ham harakati yo'q."""

    item_id: int
    code: str
    name: str
    unit: str | None
    quantity: Decimal
    value: Decimal


class StockReport(BaseModel):
    """Ombor hisoboti (docs/14 §11) — dizayndagi `rep` ekrani.

    Xizmat (`X`) uchala bo'limdan ham chiqarilgan: unda qoldiq ham, qiymat ham yo'q."""

    date_from: date
    date_to: date
    groups: list[ReportGroupRow]
    abc: list[ReportAbcRow]
    dead: list[ReportDeadRow]
    #: Harakatsizlarning JAMI soni (`dead` faqat eng qimmat bir nechtasi)
    dead_total: int
    #: Butun ombor qoldig'ining qiymati va pozitsiyalar soni
    value: Decimal
    positions: int
