from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BirlikRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    barkod: str | None
    item_id: int
    item_name: str | None = None
    item_code: str | None = None
    unit: str | None = None
    ishlab_kod: str | None
    hajm: Decimal
    qoldiq: Decimal
    #: `ombor` | `sex` | `tugadi`
    joy: str
    order_id: int | None
    sexga_at: datetime | None
    created_at: datetime


class BerishLine(BaseModel):
    """Berish varaqasining qatori — bitta material."""

    line_id: int
    #: `sheet` | `band` | `hardware` — qaysi postga tegishli (arra listni, kromka lentani oladi)
    kind: str
    item_id: int | None
    nom: str
    code: str | None
    unit: str | None
    #: Barkodli birlik bilan beriladi (list/rulon) yoki son bilan (furnitura)
    birlikli: bool
    rulon: bool
    kerak: Decimal
    berilgan: Decimal
    qoldi: Decimal
    #: Sexdagi ochiq rulonlar — avval shulardan (foydalanuvchi qarori)
    sexda: list[BirlikRead]
    #: Ombordagi tayyor birliklar soni va yorlig'i yo'q qoldiq
    omborda: int
    yorliqsiz: Decimal


class BerishRead(BaseModel):
    order_id: int
    order_number: str
    #: Rezerv holati (`faol`, `yechildi`, `sarflandi` ...) yoki rezerv yo'q bo'lsa None
    holat: str | None
    tosiq: str | None
    lines: list[BerishLine]


class BerishOrder(BaseModel):
    """Berish navbatidagi buyurtma: rezervi tirik (faol/yechildi)."""

    order_id: int
    order_number: str
    client: str | None
    holat: str
    #: Darvoza yopiq bo'lsa — sababi (material berilmaydi)
    tosiq: str | None
    qatorlar: int
    tayyor: int


class SkanIn(BaseModel):
    #: Tizim barkodi (`EK0000123`), katalog kodi yoki ishlab chiqaruvchi shtrix-kodi
    kod: str = Field(min_length=1, max_length=60)
    #: Faqat birliksiz pozitsiyada (furnitura): nechta
    qty: Decimal | None = Field(default=None, gt=0, le=10**6)


class SkanNatija(BaseModel):
    xabar: str
    ogohlantirish: list[str]
    varaqa: BerishRead


class SorovRead(BaseModel):
    id: int
    order_id: int
    order_number: str | None = None
    post: str
    izoh: str
    holat: str
    created_at: datetime
    created_by: str | None = None


class SorovIn(BaseModel):
    post: str = Field(pattern=r"^(ARRA|KROMKA|OVAL)$")
    izoh: str = Field(default="", max_length=200)


class SexMaterial(BaseModel):
    """Terminal (arra/kromka) uchun: shu postning materiali va ochiq so'rov."""

    order_id: int
    order_number: str
    holat: str | None
    tosiq: str | None
    lines: list[BerishLine]
    sorov: SorovRead | None


class BolakRead(BaseModel):
    """Qoldiq bo'lagi (kroydan ortgan foydali list bo'lagi)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    barkod: str
    item_id: int | None
    item_name: str | None = None
    material_nom: str
    uzunlik: Decimal
    eni: Decimal
    manba_order_id: int | None
    manba_order: str | None = None
    #: `kutish` | `ombor` | `ishlatildi` | `chiqit` | `bekor`
    joy: str
    qty: int
    qty_pending: int
    #: `mes` (ATX yorlig'i) | `mx` (MX Kroy kirimi)
    manba: str
    band_raqam: str | None = None
    order_id: int | None
    created_at: datetime


class KodIn(BaseModel):
    kod: str = Field(min_length=1, max_length=120)


class YorliqIn(BaseModel):
    """Eski (barkodsiz) qoldiqni yorliqlash: `soni` ta birlik, har biri `hajm` (listda 1)."""

    item_id: int
    soni: int = Field(ge=1, le=1000)
    hajm: Decimal | None = Field(default=None, gt=0, le=10**6)
    ishlab_kod: str | None = Field(default=None, max_length=60)
