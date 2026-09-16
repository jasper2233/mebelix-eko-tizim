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
