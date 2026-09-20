from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class SystemSettingRead(BaseModel):
    key: str
    value: str


class SystemSettingUpdate(BaseModel):
    #: Bo'sh qiymat — qoidani o'chirish (nostandart belgisi uchun: hech bir detal
    #: avtomatik belgilanmaydi). 8 belgi yetadi: bu suffiks, nom emas.
    value: str = Field(max_length=8)


#: "HH:MM", 24 soatlik. `time` emas, satr: brauzerdagi `<input type="time">` aynan shu
#: shaklni beradi va oladi — `time` "08:00:00" bo'lib qaytib, maydonda soniya chiqardi.
Clock = Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")]
Name = Annotated[str, Field(min_length=1, max_length=40)]


Seconds = Annotated[float, Field(ge=0, le=600)]


class IdealCycle(BaseModel):
    """Prisadka ideal sikli koeffitsiyentlari, soniya — OEE Performance (`services/performance.py`).

    Sukut qiymatlar TAXMINIY (2026-09-18, egasi «taxminiy raqamlar qo'yib tur» dedi): 2026-09-16 prod
    auditidan — o'rtacha detal 6 teshik, median sikl 3 s kutish + ~24 s ishlov = 27 s; formula shu
    detalga 15 + 6 × 2 = 27 s beradi. Admin Tizim sozlamalarida sekundomer o'lchovi bilan to'g'rilaydi."""

    #: Har detalga qat'iy vaqt: skan, qo'yish, qisish, olish
    load_s: Seconds = 15
    #: Yuza teshik (`xnc_summary.bores`), har biriga
    bore_s: Seconds = 2
    #: Qirra teshik (`edge_bores`) — gorizontal shpindel pozitsiyalanadi
    edge_bore_s: Seconds = 2.5
    #: Paz (`grooves`), har biriga
    groove_s: Seconds = 8
    #: Freza konturi (`mills`), har biriga
    mill_s: Seconds = 12


class IdealCycleKromka(BaseModel):
    """Kromka ideal sikli — OEE Performance (`services/performance.py`).

    Prisadkadagi kabi TAXMINIY koeffitsiyentlar to'plami emas: kromkada ideal vaqtni
    LENTA belgilaydi va uzunlikni stansiyaning o'zi o'lchaydi, ya'ni

        ideal vaqt (bitta o'tish) = L / v  +  oraliq

    `L` — o'lchangan uzunlik (mm), `v` — nominal tezlik (10 yoki 18 m/min, Pico beradi).
    Sozlanadigan yagona narsa — detallar orasidagi bo'shliq: operator keyingi detalni
    qo'yguncha ketadigan vaqt. Tsexda sekundomer bilan aniqlanadi."""

    #: Detallar orasidagi bo'shliq, soniya — lentaga keyingi detal qo'yilguncha
    gap_s: Seconds = 3


class DefectReasons(BaseModel):
    """Brak sabablari — terminaldagi BRAK oynasida tugma bo'lib chiqadi (OEE Quality).

    Alohida jadval EMAS (`downtime_reason` dan farqli): sabab `part_defect.reason` ga
    MATN bo'lib ko'chiriladi, ya'ni FK ham, `is_active` ham kerak emas — ro'yxatdan
    olib tashlangan sabab eski yozuvlarda o'qilaveradi."""

    reasons: list[Name] = Field(default_factory=list, max_length=30)


class WorkBreak(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Name
    start: Clock
    end: Clock


class WorkShift(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: Name
    start: Clock
    #: `end` < `start` — tungi smena, yarim tundan o'tadi.
    end: Clock
    breaks: list[WorkBreak] = Field(default_factory=list, max_length=10)


class Holiday(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    day: date
    name: str = Field(default="", max_length=60)


class WorkSchedule(BaseModel):
    """Ish jadvali — OEE reja vaqti shundan: smenalar minus tanaffuslar, dam olish kunlarida 0.

    Hamma ish markaziga umumiy. Maydonlar orasidagi qoidalar (smenalar ustma-ust
    tushmasin, tanaffus smena ichida bo'lsin) — `settings_service.schedule_error`."""

    shifts: list[WorkShift] = Field(default_factory=list, max_length=4)
    #: Haftalik dam olish kunlari, ISO: 1 = dushanba ... 7 = yakshanba.
    days_off: list[Annotated[int, Field(ge=1, le=7)]] = Field(default_factory=list, max_length=7)
    #: Bayram va boshqa ishlanmaydigan sanalar.
    holidays: list[Holiday] = Field(default_factory=list, max_length=366)
