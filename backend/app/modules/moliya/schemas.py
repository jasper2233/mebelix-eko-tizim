from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

Summa = Annotated[Decimal, Field(ge=0, le=Decimal(10) ** 13)]


class Qator(BaseModel):
    nom: str
    summa: Decimal
    soni: int = 0


class BuyurtmaFoyda(BaseModel):
    order_id: int
    number: str
    mijoz: str
    summa: Decimal
    tannarx: Decimal
    foyda: Decimal


class PnL(BaseModel):
    """Foyda va zarar: sotuv − FIFO tannarx − xarajatlar (oy, mahalliy vaqt)."""

    oy: str
    yopiq: bool = False
    sotuv_buyurtma: Decimal
    sotuv_ombor: Decimal
    sotuv: Decimal
    #: QQS to'lovchida sotuv ichidagi QQS (daromad emas — byudjetga), sof tushum = sotuv − shu
    sotuv_qqs: Decimal = Decimal(0)
    sof_tushum: Decimal = Decimal(0)
    tannarx_buyurtma: Decimal
    tannarx_ombor: Decimal
    tannarx: Decimal
    yalpi: Decimal
    #: Moddalar bo'yicha (bank komissiyasi ham shu yerda)
    xarajatlar: list[Qator]
    #: Smena sanash farqi: kamomad (+) − ortiqcha
    kassa_farqi: Decimal
    #: Aylanmadan soliq (aylanma rejimida) — xarajat
    aylanma_soliq: Decimal = Decimal(0)
    xarajat_jami: Decimal
    sof: Decimal
    #: Shu oy yetkazilgan buyurtmalar rentabelligi
    buyurtmalar: list[BuyurtmaFoyda]


class HisobOqim(BaseModel):
    kod: str
    nom: str
    kirim: Decimal
    chiqim: Decimal
    qoldiq: Decimal


class KassirOqim(BaseModel):
    nom: str
    soni: int
    kirim: Decimal
    chiqim: Decimal


class OyOqim(BaseModel):
    oy: str
    kirim: Decimal
    chiqim: Decimal


class PulOqimi(BaseModel):
    """O'tkazmalarsiz kirim/chiqim (hisobdan hisobga o'tkazma pul oqimi emas)."""

    dan: date
    gacha: date
    kirim: Decimal
    chiqim: Decimal
    saldo: Decimal
    soni: int
    kirim_moddalar: list[Qator]
    chiqim_moddalar: list[Qator]
    hisoblar: list[HisobOqim]
    kassirlar: list[KassirOqim]
    oylar: list[OyOqim]


class Debitor(BaseModel):
    client_id: int
    mijoz: str
    telefon: str | None
    #: Yetkazilgan buyurtmalar summasi
    sotuv: Decimal
    tolangan: Decimal
    #: Yetkazilgan, to'lanmagan qism
    qarz: Decimal
    #: Hali yetkazilmagan buyurtmalarga olingan pul
    avans: Decimal
    #: Eng eski to'lanmagan yetkazilgan buyurtmadan beri kun
    kun: int | None
    muddat_kun: int
    muddati_otgan: bool
    #: Qarzning muddati o'tgan qismi (buyurtma bo'yicha: yetkazilgandan muddatdan ko'p kun o'tgan)
    muddati_otgan_summa: Decimal
    limit: Decimal | None
    limitdan_oshgan: bool
    shartnoma_no: str


class Kreditor(BaseModel):
    nom: str
    faktura: Decimal
    tolangan: Decimal
    qarz: Decimal
    #: Ortiqcha to'langan (berilgan avans)
    avans: Decimal
    hujjatlar: int
    #: Eng yaqin to'lanmagan muddat
    muddat: date | None


class KalendarQator(BaseModel):
    sana: date
    tur: Literal["kirim", "chiqim"]
    nom: str
    summa: Decimal
    #: `mijoz` | `taminotchi` | `reja`
    manba: str
    muddati_otgan: bool
    havola_id: int | None = None


class ByudjetQator(BaseModel):
    nom: str
    limit: Decimal | None
    fakt: Decimal
    foiz: int | None


class Balans(BaseModel):
    pul: Decimal
    debitorlik: Decimal
    ombor: Decimal
    berilgan_avans: Decimal
    aktiv: Decimal
    kreditorlik: Decimal
    olingan_avans: Decimal
    passiv: Decimal
    sof: Decimal


class Vazifa(BaseModel):
    matn: str
    izoh: str
    summa: Decimal | None = None
    #: Frontend qaysi bo'limga olib boradi: `smenalar` `debitorlar` `kalendar` `byudjet` `davrlar`
    bolim: str


class KunOqim(BaseModel):
    sana: date
    kirim: Decimal
    chiqim: Decimal


class Bosh(BaseModel):
    hisoblar: list[HisobOqim]
    pul: Decimal
    debitorlik: Decimal
    debitor_soni: int
    muddati_otgan: Decimal
    olingan_avans: Decimal
    kreditorlik: Decimal
    rejali_30: Decimal
    vazifalar: list[Vazifa]
    kunlar: list[KunOqim]
    pnl: PnL


class AktQator(BaseModel):
    sana: date
    hujjat: str
    izoh: str
    debet: Decimal
    kredit: Decimal
    saldo: Decimal


class Akt(BaseModel):
    """Solishtirma dalolatnoma: debet — yetkazilgan buyurtma va qaytarilgan pul, kredit — to'lov.
    Saldo musbat — mijoz qarzdor, manfiy — biz qarzdormiz (avans)."""

    client_id: int
    mijoz: str
    dan: date
    gacha: date
    boshlangich: Decimal
    qatorlar: list[AktQator]
    debet: Decimal
    kredit: Decimal
    yakuniy: Decimal


class MijozShartIn(BaseModel):
    shartnoma_no: Annotated[str, Field(max_length=40)] = ""
    muddat_kun: Annotated[int, Field(ge=0, le=365)] | None = None
    kredit_limit: Summa | None = None


class RejaIn(BaseModel):
    nom: Annotated[str, Field(min_length=1, max_length=120)]
    tur: Literal["kirim", "chiqim"] = "chiqim"
    summa: Annotated[Decimal, Field(gt=0, le=Decimal(10) ** 13)]
    turkum: Annotated[str, Field(max_length=60)] = ""
    takror: Literal["oylik", "bir"]
    sana: date
    faol: bool = True


class RejaRead(RejaIn):
    id: int


class ModdaIn(BaseModel):
    nom: Annotated[str, Field(min_length=1, max_length=60)]
    oylik_limit: Summa | None = None
    faol: bool = True


class ModdaRead(ModdaIn):
    id: int


class HisobSozlama(BaseModel):
    kod: str
    nom: str
    tur: str
    boshlangich: Decimal
    komissiya_foiz: Decimal
    qoldiq: Decimal


class HisobSozlamaIn(BaseModel):
    boshlangich: Summa | None = None
    komissiya_foiz: Annotated[Decimal, Field(ge=0, le=20)] | None = None


class Sozlamalar(BaseModel):
    eng_kam_avans_foiz: Annotated[int, Field(ge=0, le=100)]
    tolov_muddat_kun: Annotated[int, Field(ge=0, le=365)]


class DavrRead(BaseModel):
    oy: str
    holat: str
    yopgan: str | None
    yopilgan_at: datetime | None
    ochish_sorov: str | None
    ochish_sabab: str
    ochgan: str | None
    ochilgan_at: datetime | None
    sof: Decimal | None


class DavrSababIn(BaseModel):
    sabab: Annotated[str, Field(min_length=1, max_length=200)]
