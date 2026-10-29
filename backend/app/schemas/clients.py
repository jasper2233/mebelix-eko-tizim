from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from .users import validate_phone

_NAME_FIELD = Field(min_length=2, max_length=150, examples=["Azamat Karimov"])
#: Telefon qoidasi users/employees bilan BITTA funksiyada — pydantic `pattern`
#: xatosi "String should match pattern ..." bo'lib chiqadi, o'zbekchasi esa shu yerda.
_Phone = Annotated[str | None, AfterValidator(validate_phone), Field(examples=["+998901234567"], default=None)]


class ClientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    phone: str | None
    phone_alt: str | None
    address: str | None
    notes: str | None
    #: Doimiy mijoz va kredit limiti (so'm) — EKO TZ Q14; o'zgartirish faqat direktor
    doimiy: bool = False
    kredit_limit: Decimal | None = None
    created_at: datetime
    # Quyidagilar route'da hisoblanadi, bazada saqlanmaydi.
    orders_count: int = 0
    #: Bekor qilinmagan buyurtmalar summasi — mijozning haqiqiy qiymati.
    total_amount: Decimal = Decimal(0)
    #: O'rin (1 — eng yirik) va ulush; reyting AYNAN summadan chiqadi.
    rank: int = 0
    share_pct: float = 0.0
    #: ABC (Pareto) segmenti: A — aylanmaning birinchi 80%, B — 95% gacha, C — qolgani.
    #: Yulduzcha reyting bu ma'lumotda ishlamaydi: prodda o'lchandi, eng yirik
    #: mijoz aylanmaning 81% ini beradi, ya'ni qolgan hamma bir xil past bahoni
    #: olardi. ABC esa aynan shunday nomutanosib taqsimot uchun qilingan.
    segment: str = "C"


class ClientOrderRow(BaseModel):
    """Mijoz kartochkasidagi buyurtma qatori."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    number: str
    project_name: str | None
    status: str
    priority: str
    deadline: date | None
    amount: Decimal | None
    #: Qoldiq to'lov (qarz) kartochkada ko'rinsin — mijoz haqidagi asosiy savol.
    advance_payment: Decimal | None = None
    #: Kassa orderlari bilan to'langan (EKO 4)
    kassa_tolangan: Decimal = Decimal(0)
    created_at: datetime


class ClientDetail(ClientRead):
    """Qator ustiga bosilganda: to'liq ma'lumot + buyurtmalar ro'yxati."""

    orders: list[ClientOrderRow] = []


class ClientCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: Annotated[str, _NAME_FIELD]
    phone: _Phone
    phone_alt: _Phone
    address: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class ClientUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    full_name: Annotated[str | None, _NAME_FIELD] = None
    phone: _Phone
    phone_alt: _Phone
    address: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class ClientCredit(BaseModel):
    """Doimiy mijoz va kredit limiti — moliyaviy qaror, faqat direktor (EKO TZ Q14, Q22).
    `kredit_limit` bo'sh = limit yo'q: doimiy bo'lsa ham to'lovsiz ishga tushmaydi."""

    doimiy: bool
    kredit_limit: Decimal | None = Field(default=None, ge=0, le=Decimal(10) ** 13)
