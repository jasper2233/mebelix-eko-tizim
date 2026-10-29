from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Raqam = Annotated[str, Field(pattern=r"^\d*$")]
Foiz = Annotated[Decimal, Field(ge=0, le=50)]


class KorxonaIO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nomi: Annotated[str, Field(max_length=200)] = ""
    stir: Annotated[str, Field(pattern=r"^(\d{9})?$")] = ""
    manzil: Annotated[str, Field(max_length=300)] = ""
    bank: Annotated[str, Field(max_length=150)] = ""
    mfo: Annotated[str, Field(pattern=r"^(\d{5})?$")] = ""
    hisob_raqam: Annotated[str, Field(pattern=r"^(\d{20})?$")] = ""
    direktor: Annotated[str, Field(max_length=120)] = ""
    buxgalter: Annotated[str, Field(max_length=120)] = ""
    qqs_kod: Annotated[str, Field(max_length=20)] = ""
    esf_operator: Literal["sinov"] = "sinov"
    buyurtma_nomi: Annotated[str, Field(max_length=200)] = "Mebel (buyurtma bo'yicha)"
    buyurtma_mxik: Annotated[str, Field(pattern=r"^(\d{17})?$")] = ""
    buyurtma_birlik: Annotated[str, Field(max_length=10)] = ""


class RejimIn(BaseModel):
    amal_boshi: date
    rejim: Literal["qqs", "aylanma"]
    qqs_foiz: Foiz
    aylanma_foiz: Foiz


class RejimRead(RejimIn):
    model_config = ConfigDict(from_attributes=True)

    id: int


class MijozIO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    yuridik: bool = False
    nomi: Annotated[str, Field(max_length=200)] = ""
    stir: Annotated[str, Field(pattern=r"^(\d{9})?$")] = ""
    jshshir: Annotated[str, Field(pattern=r"^(\d{14})?$")] = ""
    bank: Annotated[str, Field(max_length=150)] = ""
    mfo: Annotated[str, Field(pattern=r"^(\d{5})?$")] = ""
    hisob_raqam: Annotated[str, Field(pattern=r"^(\d{20})?$")] = ""
    qqs_kod: Annotated[str, Field(max_length=20)] = ""


class MxikIn(BaseModel):
    mxik: Annotated[str, Field(pattern=r"^(\d{17})?$")] = ""
    birlik_kod: Annotated[str, Field(max_length=10)] = ""
    qqs_turi: Literal["standart", "nol", "ozod"] = "standart"


class EsfRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    no: str
    tur: str
    holat: str
    sana: date
    raqam: str
    order_id: int | None
    order_number: str | None = None
    stock_doc_id: int | None
    stock_doc_no: str | None = None
    client_id: int | None
    kontragent: str
    kontragent_stir: str
    rekvizit: dict[str, Any]
    qatorlar: list[dict[str, Any]]
    rejim: str
    summa: Decimal
    qqs: Decimal
    jami: Decimal
    operator: str
    operator_id: str | None
    xato: str
    urinish: int
    yuborilgan_at: datetime | None
    javob_at: datetime | None
    created_at: datetime


class EsfBuyurtmaIn(BaseModel):
    order_id: int


class EsfHujjatIn(BaseModel):
    stock_doc_id: int
    client_id: int


class JavobIn(BaseModel):
    qabul: bool
    sabab: Annotated[str, Field(max_length=300)] = ""


class SinovKiruvchiIn(BaseModel):
    """Lokal sinov operatori: yetkazib beruvchi yuborgan ESF (QQS bilan jami)."""

    sotuvchi_nomi: Annotated[str, Field(min_length=1, max_length=200)]
    sotuvchi_stir: Annotated[str, Field(pattern=r"^\d{9}$")]
    raqam: Annotated[str, Field(min_length=1, max_length=40)]
    sana: date
    jami: Annotated[Decimal, Field(gt=0, le=Decimal(10) ** 13)]
    qqs_foiz: Foiz = Decimal(12)


class Nomzod(BaseModel):
    """ESF yozilmagan, ESF ga tegishli sotuv: yetkazilgan buyurtma yoki ombor sotuvi."""

    tur: Literal["buyurtma", "hujjat"]
    id: int
    no: str
    sana: date
    mijoz: str
    client_id: int | None
    summa: Decimal
    #: Mijoz yuridik va rekvizitlari to'liqmi
    tayyor: bool


class OySoliqRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    oy: str
    rejim: str | None
    qqs_foiz: Decimal
    aylanma_foiz: Decimal
    aylanma: Decimal
    buyurtma: Decimal
    dokon: Decimal
    sotuv_qqs: Decimal
    xarid_qqs: Decimal
    tolanadigan_qqs: Decimal
    aylanma_soliq: Decimal
    jami_soliq: Decimal


class Kitob(BaseModel):
    oy: OySoliqRead
    sotuv: list[EsfRead]
    xarid: list[EsfRead]
    #: ESF siz (chakana, jismoniy shaxs) sotuvdagi QQS: hisoblangan − sotuv kitobidagi
    esfsiz_qqs: Decimal
