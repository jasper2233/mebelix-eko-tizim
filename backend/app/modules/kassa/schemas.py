from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Summa = Annotated[Decimal, Field(gt=0, le=Decimal(10) ** 12)]
Matn = Annotated[str, Field(max_length=300)]
#: Kupyura → soni ({"200000": 3, "100000": 5})
Kupyura = Annotated[
    dict[Annotated[str, Field(pattern=r"^\d{1,7}$")], Annotated[int, Field(ge=0, le=100000)]], Field(max_length=20)
]


class HisobRead(BaseModel):
    kod: str
    nom: str
    tur: str
    qoldiq: Decimal


class SmenaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    no: str
    ochilgan_at: datetime
    ochilish_naqd: Decimal
    ochilish_kitob: Decimal
    yopilgan_at: datetime | None
    yopilish_naqd: Decimal | None
    kirim: Decimal | None
    chiqim: Decimal | None
    kutilgan: Decimal | None
    farq: Decimal | None
    terminal_z: Decimal | None
    karta_tushum: Decimal | None
    ochgan: str | None = None
    yopgan: str | None = None


class SmenaOchIn(BaseModel):
    kupyura: Kupyura


class SmenaYopIn(BaseModel):
    kupyura: Kupyura
    #: Karta terminali Z-hisobotidagi summa (bo'lsa) — tizimdagi karta tushumi bilan solishtiriladi
    terminal_z: Annotated[Decimal, Field(ge=0, le=Decimal(10) ** 12)] | None = None


class SmenaHolat(BaseModel):
    smena: SmenaRead | None
    #: Ochiq smenada: hozirgacha naqd kirim/chiqim, kutilgan naqd, karta tushumi
    kirim: Decimal = Decimal(0)
    chiqim: Decimal = Decimal(0)
    kutilgan: Decimal = Decimal(0)
    karta: Decimal = Decimal(0)
    #: Ochishda kitob bilan farq (kassirga ogohlantirish)
    ochilish_farq: Decimal = Decimal(0)
    hisoblar: list[HisobRead]


class TolovIn(BaseModel):
    hisob: Literal["naqd", "karta", "bank"]
    summa: Summa
    #: Dollarda qabul qilinsa: dollar summasi va kurs (`summa` = valyuta × kurs)
    valyuta_summa: Annotated[Decimal, Field(gt=0, le=Decimal(10) ** 9)] | None = None
    kurs: Annotated[Decimal, Field(gt=0, le=Decimal(10) ** 7)] | None = None


class KirimIn(BaseModel):
    maqsad: Literal["avans", "tolov", "qarz", "sotuv", "boshqa"]
    tolovlar: Annotated[list[TolovIn], Field(min_length=1, max_length=3)]
    order_id: int | None = None
    client_id: int | None = None
    stock_doc_id: int | None = None
    kontragent: Annotated[str, Field(max_length=150)] = ""
    izoh: Matn = ""
    mijoz_berdi: Annotated[Decimal, Field(ge=0, le=Decimal(10) ** 12)] | None = None


class ChiqimIn(BaseModel):
    maqsad: Literal["taminotchi", "xarajat", "qaytarish", "inkassatsiya", "boshqa"]
    hisob: Literal["naqd", "karta", "bank"]
    summa: Summa
    kontragent: Annotated[str, Field(max_length=150)] = ""
    turkum: Annotated[str, Field(max_length=60)] = ""
    izoh: Matn = ""
    order_id: int | None = None


class OtkazmaIn(BaseModel):
    dan: Literal["naqd", "karta", "bank"]
    ga: Literal["naqd", "karta", "bank"]
    summa: Summa
    izoh: Matn = ""


class StornoIn(BaseModel):
    sabab: Annotated[str, Field(min_length=1, max_length=200)]


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    no: str
    tur: str
    maqsad: str
    hisob: str | None = None
    summa: Decimal
    valyuta_summa: Decimal | None
    kurs: Decimal | None
    order_id: int | None
    order_number: str | None = None
    client_id: int | None
    kontragent: str
    turkum: str
    izoh: str
    guruh: str | None
    mijoz_berdi: Decimal | None
    qaytim: Decimal | None
    smena_no: str | None = None
    kassir: str | None = None
    storno_of_id: int | None
    #: Shu orderni bekor qilgan storno orderi (bo'lsa)
    storno_no: str | None = None
    created_at: datetime


class AmalNatija(BaseModel):
    orderlar: list[OrderRead]
    xabar: str
    qaytim: Decimal | None = None
    #: «B-2026-101: material biriktirildi» / «… chegaraga yana N so'm kerak»
    rezerv: list[str] = []


class NavbatRow(BaseModel):
    """To'lov navbati: summasi bor, to'liq to'lanmagan buyurtmalar (kassir chapdan tanlaydi)."""

    order_id: int
    order_number: str
    client_id: int
    mijoz: str
    telefon: str | None
    summa: Decimal
    tolangan: Decimal
    qolgan: Decimal
    #: Rezerv chegarasi (eng kam avans) va hali kerak bo'lgani; rezerv yo'q bo'lsa None
    chegara: Decimal | None
    chegaraga_kerak: Decimal | None
    holat: str
