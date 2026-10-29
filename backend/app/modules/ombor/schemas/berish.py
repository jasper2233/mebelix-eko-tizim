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


class YorliqIn(BaseModel):
    """Eski (barkodsiz) qoldiqni yorliqlash: `soni` ta birlik, har biri `hajm` (listda 1)."""

    item_id: int
    soni: int = Field(ge=1, le=1000)
    hajm: Decimal | None = Field(default=None, gt=0, le=10**6)
    ishlab_kod: str | None = Field(default=None, max_length=60)
