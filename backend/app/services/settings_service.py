"""Ish vaqtidagi sozlamalar (`system_setting`) — o'qish va yozish bitta joyda.

`app/core/config.py` dagi `.env` sozlamalaridan farqi: bularni admin panelda
o'zgartiradi va konteynerni qayta ishga tushirish shart emas.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemSetting
from app.schemas.settings import DefectReasons, IdealCycle, IdealCycleKromka, IdealCycleRover, WorkSchedule

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
#: KROMKA bo'sh yurishi: lenta yuryapti (RUN yoqiq), lekin shuncha daqiqa bitta ham detal
#: o'tmadi — material/buyurtma yo'q yoki operator ketgan. O'sha vaqt «ishladi» ga kirmasin
#: (`services/andon.split_idle`). Alohida chegara: to'xtash 5 daqiqada so'raladi, bo'sh
#: yurish esa uzunroq bo'lishi normal — detal almashtirish ritmi jazolanmasin.
KROMKA_IDLE_MINUTES = "kromka_idle_minutes"
#: Kromka o'lchovining DOPUSKI, mm: o'lchangan uzunlik kutilganidan shuncha farq qilsa
#: ham «mos» sanaladi. Lenta detalni harakatda o'lchaydi — tezlik va datchik kechikishi
#: bir necha millimetr beradi, nol dopusk har bir detalni brak qilardi.
KROMKA_TOLERANCE_MM = "kromka_tolerance_mm"
#: O'lchov skan bilan bog'lanadigan oyna, SONIYA. Detal birinchi datchikka kirgan
#: lahza (`o'lchov vaqti − ish_ms`) atrofida shuncha soniya ichidagi skanlar nomzod
#: bo'ladi. 2026-09-21 gacha bu «oxirgi skan, N daqiqa ichida» edi va prodda xato
#: berardi: detal datchiklar orasida 8–15 soniya yuradi, operator esa 4–10 soniyada
#: bir marta skanerlaydi — o'lchov keyingi detalning skaniga yopishardi.
KROMKA_BIND_WINDOW_S = "kromka_bind_window_s"
#: O'sha oynaning kirishdan OLDINGI qismi, SONIYA (2026-10-16). Yuqoridagi `kromka_bind_window_s`
#: endi faqat KEYINGI qismi: operator odatda detalni qo'yishdan oldin, ba'zan bir necha detal
#: oldindan skanerlaydi — stansiya egasining tavsiyasi −60 s … +20 s.
KROMKA_BIND_BEFORE_S = "kromka_bind_before_s"

#: Butun son sozlamalar va ularning ruxsat etilgan oralig'i — `PUT /settings/{key}` tashqarisini rad etadi.
INT_RANGES: dict[str, tuple[int, int]] = {
    IDLE_OPERATOR_MINUTES: (10, 1440),
    IDLE_STAFF_MINUTES: (10, 1440),
    STOP_PROMPT_IDLE_MINUTES: (1, 120),
    KROMKA_IDLE_MINUTES: (1, 240),
    KROMKA_TOLERANCE_MM: (1, 50),
    KROMKA_BIND_WINDOW_S: (5, 600),
    KROMKA_BIND_BEFORE_S: (5, 600),
}

#: Sahifada ko'rsatiladigan sozlamalar va ularning sukut qiymati.
DEFAULTS: dict[str, str] = {
    CUSTOM_PART_SUFFIX: "#",
    IDLE_OPERATOR_MINUTES: "90",
    IDLE_STAFF_MINUTES: "240",
    STOP_PROMPT_IDLE_MINUTES: "5",
    KROMKA_IDLE_MINUTES: "10",
    KROMKA_TOLERANCE_MM: "3",
    KROMKA_BIND_WINDOW_S: "20",
    KROMKA_BIND_BEFORE_S: "60",
}

#: Ish jadvali (JSON). `DEFAULTS` da YO'Q: umumiy `PUT /settings/{key}` 8 belgilik
#: qiymat qabul qiladi, jadvalning esa o'z sxemasi va o'z endpointi bor.
WORK_SCHEDULE = "work_schedule"
#: Prisadka ideal sikli koeffitsiyentlari (JSON, `IdealCycle`) — o'z endpointi bilan, jadval kabi.
IDEAL_CYCLE = "ideal_cycle_prisadka"
#: Kromka ideal sikli (JSON, `IdealCycleKromka`) — u yerda ideal vaqtni lenta belgilaydi.
IDEAL_CYCLE_KROMKA = "ideal_cycle_kromka"
#: ROVER ideal sikli (JSON, `IdealCycleRover`) — detalga + kontur metriga soniya.
IDEAL_CYCLE_ROVER = "ideal_cycle_rover"
#: Brak sabablari (JSON, `DefectReasons`) — terminaldagi BRAK oynasi shundan.
DEFECT_REASONS = "defect_reasons"
#: OEE shu KUNDAN boshlab hisoblanadi (ISO sana, bo'sh — cheklov yo'q). Undan oldingi
#: kunlar hisobotga UMUMAN kirmaydi: ish jadvali, sabablar va ideal sikl sozlanmagan
#: paytdagi qayd OEE'ni pastga tortib, raqamni ishonchsiz qilardi. `DEFAULTS` da YO'Q —
#: umumiy `PUT /settings/{key}` 8 belgi oladi, sana esa 10 (o'z endpointi bor).
OEE_START_DATE = "oee_start_date"

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


async def get_ideal_cycle_kromka(db: AsyncSession) -> IdealCycleKromka:
    """Kromka koeffitsiyenti; kiritilmagan bo'lsa sxemadagi sukut (3 s oraliq)."""
    raw = await get_setting(db, IDEAL_CYCLE_KROMKA)
    return IdealCycleKromka.model_validate_json(raw) if raw else IdealCycleKromka()


async def get_ideal_cycle_rover(db: AsyncSession) -> IdealCycleRover:
    """ROVER koeffitsiyentlari; kiritilmagan bo'lsa sxemadagi TAXMINIY sukut qiymatlar."""
    raw = await get_setting(db, IDEAL_CYCLE_ROVER)
    return IdealCycleRover.model_validate_json(raw) if raw else IdealCycleRover()


async def get_oee_start(db: AsyncSession) -> date | None:
    """OEE qaysi kundan hisoblanadi; kiritilmagan bo'lsa None — hamma tarix."""
    raw = await get_setting(db, OEE_START_DATE)
    return date.fromisoformat(raw) if raw else None


async def get_defect_reasons(db: AsyncSession) -> DefectReasons:
    """Brak sabablari; kiritilmagan bo'lsa bo'sh ro'yxat — terminalda BRAK tugmasi umuman chiqmaydi."""
    raw = await get_setting(db, DEFECT_REASONS)
    return DefectReasons.model_validate_json(raw) if raw else DefectReasons()


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
