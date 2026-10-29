from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Money = Annotated[Decimal, Field(ge=0, le=10**12)]
Qty = Annotated[Decimal, Field(ge=0, le=10**9)]
Pct = Annotated[Decimal, Field(ge=0, le=1000)]


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


class WarehousePricing(BaseModel):
    """Ombor narx sozlamalari (Boshqaruv paneli). Bitta JSON — `system_setting.warehouse_pricing`."""

    #: 1 $ necha so'm — kirim dollarda, narx so'mda
    usd_rate: Annotated[Decimal, Field(gt=0, le=10**6)] = Decimal(12800)
    #: `{"M-LD": {"S": 450000, ...}, "M-LM": {...}}` — BITTA list narxi
    tier_prices: dict[str, dict[Literal["S", "M", "P"], Money]] = Field(default_factory=dict)
    #: Furnitura ustamasi: umumiy va guruh bo'yicha (`F-RC`: 35)
    markup_all: Pct | None = None
    markup_groups: dict[str, Pct] = Field(default_factory=dict)
    #: Kromka narxi O'LCHAM bo'yicha, 1 METR uchun: `{"19×1": 1100, "21×1": 1300}`.
    #: O'lcham kromkaning NOMIDAN olinadi (`services/warehouse.py: kromka_size`) — varaqda
    #: alohida ustun yo'q. Dekor sinflaridan farqi: kromkada sinf emas, O'LCHAM narxni
    #: belgilaydi (tsexdagi varaq shunday: 19×0,6 — 600, 19×1 — 1100, 21×1 — 1300).
    kromka_prices: dict[str, Money] = Field(default_factory=dict)


class CbRateRead(BaseModel):
    """Markaziy bank dollar kursi — FAQAT solishtirish uchun (`services/cb_rate.py`).

    Hisob-kitobga tushmaydi: narx sexdagi kurs bilan hisoblanadi, bankniki panelda uning
    YONIDA turadi. Bank javob bermasa endpoint `null` qaytaradi va panel kursni
    solishtirmasdan ishlayveradi."""

    rate: Decimal
    #: Bank bergan sana, `17.10.2026`
    date: str
    #: Oldingi kundan farq
    diff: Decimal | None = None


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
    description: str | None
    purchase_usd: Decimal | None
    tier: str | None
    markup_pct: Decimal | None
    tracked: bool
    birlik_hajm: Decimal | None = None
    ishlab_barkod: str | None = None


class CatalogRow(BaseModel):
    """Nomenklatura jadvalining bitta qatori — butun katalog BIR so'rovda keladi (≈2 700 qator):
    dizayndagidek qidiruv va filtr darhol, sahifa almashmasdan ishlaydi."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    catalog: str
    group_code: str
    group_name: str
    name: str
    description: str | None
    decor_name: str | None
    article: str | None
    unit: str | None
    quantity: Decimal
    min_quantity: Decimal | None
    location: str | None
    purchase_price: Decimal | None
    purchase_usd: Decimal | None
    sale_price: Decimal | None
    tier: str | None
    markup_pct: Decimal | None
    tracked: bool
    #: Bitta rulon uzunligi (metrdagi pozitsiya) — kirimda rulonlarga bo'lish uchun
    birlik_hajm: Decimal | None = None
    #: Sotuv narxi QO'LDA qo'yilgan — guruh qoidasi (ustama, kromka o'lchami) unga tegmaydi
    narx_qolda: bool = False
    image_url: str | None
    #: ABC sinfi — qoldiq qiymati bo'yicha (A — qiymatning 80% i); xizmatda None
    abc: str | None = None


class CatalogItemUpdate(BaseModel):
    """Omborchi tahrirlaydigan maydonlar.

    Kod va guruh ATAYLAB yo'q: kod umuman o'zgarmaydi — katalog qoidasi. Narx, nom va tavsif
    2026-10-16 dan OMBORNIKI (`scripts/catalog_import.py` ularni endi qayta yozmaydi)."""

    quantity: Qty | None = None
    min_quantity: Qty | None = None
    location: Annotated[str, Field(max_length=40)] | None = None
    purchase_price: Money | None = None
    sale_price: Money | None = None
    status: Annotated[str, Field(pattern=r"^(Aktiv|Arxiv)$")] | None = None
    note: Annotated[str, Field(max_length=500)] | None = None
    name: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    description: Annotated[str, Field(max_length=200)] | None = None
    unit: Annotated[str, Field(min_length=1, max_length=10)] | None = None
    purchase_usd: Annotated[Decimal, Field(ge=0, le=10**8)] | None = None
    tier: Literal["S", "M", "P"] | None = None
    markup_pct: Pct | None = None
    tracked: bool | None = None
    #: Bitta rulon uzunligi, metr (kromka) — kirimda rulonlarga bo'lish uchun
    birlik_hajm: Annotated[Decimal, Field(gt=0, le=10**6)] | None = None
    ishlab_barkod: Annotated[str, Field(max_length=40)] | None = None


class CatalogItemCreate(BaseModel):
    """Yangi pozitsiya. Kod server tomonida beriladi: guruhning keyingi modeli (`F-RC-104-01`) yoki
    `model` berilsa — shu modelning keyingi varianti (`F-RC-008-10`). O'chirilgan kod qayta berilmaydi."""

    #: `S` — sex xo'jaligi (zapchast, asbob, kanselyariya ...): sotilmaydi, sexga beriladi (docs/14 §10)
    catalog: Literal["M", "F", "X", "S"]
    group_code: Annotated[str, Field(pattern=r"^[A-Z]{2}$")]
    #: Mavjud model (`F-RC-008`) — yangi rang/o'lcham varianti uchun
    model: Annotated[str, Field(pattern=r"^[MFXS]-[A-Z]{2}-\d{3}$")] | None = None
    name: Annotated[str, Field(min_length=1, max_length=200)]
    description: Annotated[str, Field(max_length=200)] | None = None
    unit: Annotated[str, Field(min_length=1, max_length=10)] = "dona"
    quantity: Qty = Decimal(0)
    min_quantity: Qty | None = None
    location: Annotated[str, Field(max_length=40)] | None = None
    purchase_price: Money | None = None
    sale_price: Money | None = None


class CatalogIds(BaseModel):
    ids: Annotated[list[int], Field(min_length=1, max_length=5000)]


class CatalogBulk(CatalogIds):
    """Bir nechta pozitsiyaga birdan: sinf (`""` — sinfni olib tashlash) yoki zaxira belgisi."""

    tier: Literal["S", "M", "P", ""] | None = None
    tracked: bool | None = None


class CatalogImport(BaseModel):
    """Shablon bo'yicha yangi pozitsiyalar (Excel → CSV, brauzer o'qiydi)."""

    rows: Annotated[list[CatalogItemCreate], Field(min_length=1, max_length=2000)]


class CatalogCreated(BaseModel):
    codes: list[str]
