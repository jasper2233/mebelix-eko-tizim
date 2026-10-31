from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RezervLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    tashqi_kalit: str
    tashqi_nom: str
    fayl_qty: Decimal
    fayl_birlik: str
    item_id: int | None
    item_name: str | None = None
    item_unit: str | None = None
    kerak_qty: Decimal
    qoplangan_qty: Decimal
    #: Sexga berilgan; kerakdan ko'p bo'lsa — kroy berilgandan keyin o'zgargan, ortig'i qaytariladi
    berilgan_qty: Decimal = Decimal(0)


class RezervRead(BaseModel):
    id: int
    order_id: int
    holat: str
    muddat: datetime
    yechilgan_at: datetime | None
    tasdiq_at: datetime | None
    #: To'langan va chegara (so'm) — kassagacha `advance_payment` va `amount × foiz`
    tolangan: Decimal
    chegara: Decimal
    #: Ishlab chiqarishga to'siq sababi (yo'q bo'lsa null)
    tosiq: str | None
    lines: list[RezervLineRead]


class ShortageRead(BaseModel):
    item_id: int | None
    #: Faqat moslanmagan qatorda: moslash uchun kalit
    kind: str | None = None
    tashqi_kalit: str | None = None
    nom: str
    birlik: str
    kerak: Decimal
    qoplangan: Decimal
    yetmaydi: Decimal
    buyurtmalar: int


class MaterialMapIn(BaseModel):
    kind: Literal["sheet", "band", "hardware", "linear"]
    tashqi_kalit: str = Field(min_length=1, max_length=200)
    item_id: int
    #: Fayl birligidan katalog birligiga ko'paytiruvchi (bir xil birlikda 1)
    koef: Decimal = Field(default=Decimal(1), gt=0, le=Decimal(100000))


class FurnituraTaklif(BaseModel):
    """Qidiruv taklifi: `erkin` — boshqa buyurtmalarga band qilinmagan qoldiq."""

    model_config = ConfigDict(from_attributes=True)

    item_id: int
    code: str
    name: str
    unit: str
    qoldiq: Decimal
    erkin: Decimal


class FurnituraQator(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    #: Qo'lda qo'shilgan qator id si; fayldan kelgani tahrirlanmaydi (null)
    id: int | None
    #: `fayl` (MX Kroy yoki `.project`) | `qolda`
    manba: str
    kalit: str
    code: str | None
    nom: str
    soni: Decimal
    birlik: str
    item_id: int | None
    kim: str | None
    vaqt: datetime | None
    #: Rezerv ustunlari — shu kalitning umumiy qatori (fayl + qo'lda)
    moslangan: bool
    kerak: Decimal
    qoplangan: Decimal
    berilgan: Decimal


class FurnituraRoyxat(BaseModel):
    qatorlar: list[FurnituraQator]
    #: Fayldan ham kelgan bo'lsa — qo'shish javobida ogohlantirish
    ogoh: str | None = None


class FurnituraQosh(BaseModel):
    """Katalogdan (`item_id`) yoki katalogda yo'q bo'lsa nom bilan (`nom`)."""

    item_id: int | None = None
    nom: str | None = Field(default=None, max_length=200)
    soni: Decimal = Field(gt=0, le=Decimal(1000000), decimal_places=3)


class FurnituraSoni(BaseModel):
    soni: Decimal = Field(gt=0, le=Decimal(1000000), decimal_places=3)
