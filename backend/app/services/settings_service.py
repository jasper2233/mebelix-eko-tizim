"""Ish vaqtidagi sozlamalar (`system_setting`) — o'qish va yozish bitta joyda.

`app/core/config.py` dagi `.env` sozlamalaridan farqi: bularni admin panelda
o'zgartiradi va konteynerni qayta ishga tushirish shart emas.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemSetting
from app.schemas.settings import IdealCycle, WorkSchedule

#: Bazisda detal nomi shu belgi bilan tugasa — yuklashda NOSTANDART.
#: Bo'sh qiymat qoidani BUTUNLAY o'chiradi (belgisiz hamma detal nostandart
#: bo'lib qolmasin — `str.endswith("")` har doim rost).
CUSTOM_PART_SUFFIX = "custom_part_suffix"

#: Harakatsizlikdan keyin chiqarish, daqiqa (`services/activity.py`). Tsex: TERMINAL
#: va post rollari; ofis: qolganlar (TABLO chiqarilmaydi). 90 — tushlik (1 soat)
#: smenani yopib qo'ymasin.
IDLE_OPERATOR_MINUTES = "idle_logout_operator_minutes"
IDLE_STAFF_MINUTES = "idle_logout_staff_minutes"
#: Sariq chiroq (stanok ishlamayapti) shuncha daqiqa yonsa to'xtash yoziladi va sababi so'raladi.
#: Vaqt sariq yongan paytdan — Pico `idle_timeout_s` ga bog'liq emas (`services/downtimes.py`).
STOP_PROMPT_IDLE_MINUTES = "stop_prompt_idle_minutes"

#: Butun son sozlamalar va ularning ruxsat etilgan oralig'i — `PUT /settings/{key}` tashqarisini rad etadi.
INT_RANGES: dict[str, tuple[int, int]] = {
    IDLE_OPERATOR_MINUTES: (10, 1440),
    IDLE_STAFF_MINUTES: (10, 1440),
    STOP_PROMPT_IDLE_MINUTES: (1, 120),
}

#: Sahifada ko'rsatiladigan sozlamalar va ularning sukut qiymati.
DEFAULTS: dict[str, str] = {
    CUSTOM_PART_SUFFIX: "#",
    IDLE_OPERATOR_MINUTES: "90",
    IDLE_STAFF_MINUTES: "240",
    STOP_PROMPT_IDLE_MINUTES: "5",
}

#: Ish jadvali (JSON). `DEFAULTS` da YO'Q: umumiy `PUT /settings/{key}` 8 belgilik
#: qiymat qabul qiladi, jadvalning esa o'z sxemasi va o'z endpointi bor.
WORK_SCHEDULE = "work_schedule"
#: Prisadka ideal sikli koeffitsiyentlari (JSON, `IdealCycle`) — o'z endpointi bilan, jadval kabi.
IDEAL_CYCLE = "ideal_cycle_prisadka"

_DAY = 24 * 60


async def get_setting(db: AsyncSession, key: str) -> str:
    """Qiymat yoki sukut. Yo'q kalit uchun ham xato emas — sahifa hali ochilmagan bo'lishi mumkin."""
    row = (
        await db.execute(
            select(SystemSetting.value).where(
                SystemSetting.key == key,
                SystemSetting.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    return row if row is not None else DEFAULTS.get(key, "")


async def set_setting(db: AsyncSession, key: str, value: str, user_id: int) -> SystemSetting:
    """Bor bo'lsa yangilaydi, yo'q bo'lsa yaratadi. `flush` chaqiruvchida."""
    row = (
        await db.execute(
            select(SystemSetting).where(
                SystemSetting.key == key,
                SystemSetting.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = SystemSetting(key=key, value=value, updated_by_id=user_id)
        db.add(row)
    else:
        row.value = value
        row.updated_by_id = user_id
    return row


async def get_work_schedule(db: AsyncSession) -> WorkSchedule:
    """Saqlangan ish jadvali; hali kiritilmagan bo'lsa bo'sh jadval."""
    raw = await get_setting(db, WORK_SCHEDULE)
    return WorkSchedule.model_validate_json(raw) if raw else WorkSchedule()


async def get_ideal_cycle(db: AsyncSession) -> IdealCycle:
    """Saqlangan koeffitsiyentlar; hali kiritilmagan bo'lsa sxemadagi TAXMINIY sukut qiymatlar."""
    raw = await get_setting(db, IDEAL_CYCLE)
    return IdealCycle.model_validate_json(raw) if raw else IdealCycle()


def _minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def schedule_error(schedule: WorkSchedule) -> str | None:
    """Maydonlar orasidagi qoida buzilgan bo'lsa — admin ko'radigan matn, aks holda None.

    Shaklni (HH:MM, 1..7, uzunliklar) Pydantic tekshiradi. Bu yerdagi xato ODDIY SATR
    bo'lib qaytadi: 422 massivini frontend umumiy "noto'g'ri" matniga almashtirardi va
    admin qaysi smena xato ekanini bilmasdi. Vaqtlar sutka aylanasida (daqiqa, mod 1440)
    solishtiriladi — tungi smena (22:00-06:00) oddiy smena kabi tekshiriladi."""
    seen: list[tuple[int, int, str]] = []  # (boshlanish, uzunlik, nom)
    for shift in schedule.shifts:
        start = _minutes(shift.start)
        length = (_minutes(shift.end) - start) % _DAY
        if length == 0:
            return f"«{shift.name}» smenasining boshlanishi va tugashi bir xil."
        for other_start, other_length, other_name in seen:
            if (other_start - start) % _DAY < length or (start - other_start) % _DAY < other_length:
                return f"«{shift.name}» va «{other_name}» smenalari vaqti ustma-ust tushadi."
        seen.append((start, length, shift.name))

        previous_end = 0
        for brk in sorted(shift.breaks, key=lambda b: (_minutes(b.start) - start) % _DAY):
            brk_start = (_minutes(brk.start) - start) % _DAY
            brk_end = (_minutes(brk.end) - start) % _DAY
            if not brk_start < brk_end <= length:
                return f"«{brk.name}» tanaffusi «{shift.name}» smenasi ichida emas."
            if brk_start < previous_end:
                return f"«{shift.name}» smenasidagi tanaffuslar vaqti ustma-ust tushadi."
            previous_end = brk_end

    if len(set(schedule.days_off)) != len(schedule.days_off):
        return "Dam olish kuni takrorlangan."
    days = [holiday.day for holiday in schedule.holidays]
    if len(set(days)) != len(days):
        return "Bayram sanasi takrorlangan."
    return None
