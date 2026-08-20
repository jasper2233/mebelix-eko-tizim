"""OEE hisobi — Availability, Performance, Quality.

Standart: `OEE = Availability x Performance x Quality`.

  Availability = RUN TIME / PLANNED TIME
  Performance  = (ideal ishlab chiqarish vaqti) / RUN TIME
  Quality      = yaroqli / jami

PLANNED TIME har stanokda kunlik reja (`machine.planned_minutes_per_day`), undan
ishlab chiqarish REJALASHTIRILMAGAN to'xtalishlar ayriladi (tushlik, tanaffus —
`StopReason.excludes_planned`). Qolgan to'xtalishlar RUN dan chiqadi, ya'ni
ular Availability yo'qotishi (sozlash, nosozlik, material yo'q).

Quality keyingi bosqichda qo'shiladi (brak hisobi) — hozircha Availability va
Performance.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import TASHKENT_TZ
from app.models import (
    Machine,
    MachineStop,
    Part,
    PartInstance,
    PartRoute,
    Post,
    Scan,
    StopReason,
    WorkSession,
)
from app.models.enums import PostCode
from app.services.metrics import part_volume


@dataclass
class StopLine:
    """Bitta sabab bo'yicha yig'ma to'xtash — hisobotda eng katta yo'qotish ko'rinsin."""

    reason: str
    minutes: float
    count: int
    excludes_planned: bool


@dataclass
class Availability:
    planned_minutes: float
    run_minutes: float
    #: PLANNED dan ayrilgan (tushlik, tanaffus) — yo'qotish EMAS
    planned_off_minutes: float
    #: RUN dan chiqqan — aynan shu Availability yo'qotishi
    loss_minutes: float
    active_days: int
    stops: list[StopLine] = field(default_factory=list)

    @property
    def value(self) -> float | None:
        """0..1. PLANNED nol bo'lsa None — "0%" ko'rsatish yolg'on bo'lardi."""
        if self.planned_minutes <= 0:
            return None
        return max(0.0, min(1.0, self.run_minutes / self.planned_minutes))


def _overlap_minutes(start: datetime, end: datetime, window_start: datetime, window_end: datetime) -> float:
    """Ikki oraliqning kesishuvi, daqiqada. Manfiy bo'lmaydi."""
    lo = max(start, window_start)
    hi = min(end, window_end)
    return max(0.0, (hi - lo).total_seconds() / 60.0)


async def machine_availability(
    db: AsyncSession, machine: Machine, day_from: date, day_to: date, *, now: datetime | None = None
) -> Availability:
    """Ish markazining [day_from, day_to] oralig'idagi Availability'si (Toshkent kunlari).

    PLANNED faqat FAOL kunlarga hisoblanadi — o'sha kuni shu ish markazida smena
    ochilgan yoki to'xtash yozilgan bo'lsa. Aks holda yakshanba va bayramlar har
    hafta soxta yo'qotish bo'lib chiqardi va ko'rsatkich ma'nosini yo'qotardi.

    ponytail: faol kun = smena yoki to'xtash bo'lgan kun. Haqiqiy ishlab chiqarish
    kalendari (ish kunlari, ikkinchi smena) kerak bo'lganda shu joy almashtiriladi.
    """
    now = now or datetime.now(TASHKENT_TZ)
    start = datetime.combine(day_from, time.min, tzinfo=TASHKENT_TZ)
    end = min(datetime.combine(day_to + timedelta(days=1), time.min, tzinfo=TASHKENT_TZ), now)
    if end <= start:
        return Availability(planned_minutes=0, run_minutes=0, planned_off_minutes=0, loss_minutes=0, active_days=0)

    rows = (
        await db.execute(
            select(MachineStop, StopReason)
            .join(StopReason, StopReason.id == MachineStop.reason_id)
            .where(
                MachineStop.machine_id == machine.id,
                MachineStop.is_deleted == False,  # noqa: E712
                MachineStop.started_at < end,
                (MachineStop.ended_at.is_(None)) | (MachineStop.ended_at > start),
            )
        )
    ).all()

    by_reason: dict[str, StopLine] = {}
    planned_off = 0.0
    loss = 0.0
    for stop, reason in rows:
        # Ochiq to'xtash HOZIRGACHA sanaladi: aks holda tugatilmagan to'xtash
        # hisobotda yo'q bo'lib ko'rinardi va yo'qotish yashirinardi
        minutes = _overlap_minutes(stop.started_at, stop.ended_at or now, start, end)
        if minutes <= 0:
            continue
        if reason.excludes_planned:
            planned_off += minutes
        else:
            loss += minutes
        line = by_reason.get(reason.name)
        if line is None:
            by_reason[reason.name] = StopLine(
                reason=reason.name, minutes=minutes, count=1, excludes_planned=reason.excludes_planned
            )
        else:
            line.minutes += minutes
            line.count += 1

    active_days = await _active_days(db, machine.id, start, end)
    planned = max(0.0, active_days * machine.planned_minutes_per_day - planned_off)
    return Availability(
        planned_minutes=planned,
        run_minutes=max(0.0, planned - loss),
        planned_off_minutes=planned_off,
        loss_minutes=loss,
        active_days=active_days,
        stops=sorted(by_reason.values(), key=lambda s: -s.minutes),
    )


async def _active_days(db: AsyncSession, machine_id: int, start: datetime, end: datetime) -> int:
    """Ish markazi ishlagan kunlar soni (Toshkent kunlari bo'yicha).

    Smena YOKI to'xtash — ikkalasi ham kunni faol qiladi: stanok butun kun
    nosozlikda tursa, o'sha kun rejadan chiqmasligi kerak.
    """
    sessions = select(WorkSession.created_at).where(
        WorkSession.machine_id == machine_id,
        WorkSession.is_deleted == False,  # noqa: E712
        WorkSession.created_at >= start,
        WorkSession.created_at < end,
    )
    stops = select(MachineStop.started_at).where(
        MachineStop.machine_id == machine_id,
        MachineStop.is_deleted == False,  # noqa: E712
        MachineStop.started_at >= start,
        MachineStop.started_at < end,
    )
    days: set[date] = set()
    for query in (sessions, stops):
        for moment in (await db.execute(query)).scalars():
            days.add(moment.astimezone(TASHKENT_TZ).date())
    return len(days)


#: Ideal tezlikning MA'NOSI postdan keladi — har post bitta birlikda ishlaydi
#: (`Mebel_MES_OEE_texnik_talablar.docx` §7). Ikki xil talqin bor va ularni
#: adashtirish Performance'ni ag'darib yuborardi:
#:   "sek"  — BITTA birlik uchun ketadigan vaqt (arra: sek/metr, prisadka: sek/teshik)
#:   "daq"  — DAQIQADA bajariladigan birlik (kromka: metr/daqiqa)
IDEAL_UNITS: dict[str, tuple[str, str]] = {
    PostCode.ARRA: ("metr", "sek"),
    PostCode.KROMKA: ("metr", "daq"),
    PostCode.PRISADKA: ("teshik", "sek"),
}


@dataclass
class Performance:
    """Ishlab chiqarilgan miqdor va uning IDEAL vaqti."""

    quantity: float
    unit: str
    ideal_minutes: float
    run_minutes: float

    @property
    def value(self) -> float | None:
        """0..1. RUN nol bo'lsa None — bo'linma ma'nosiz.

        Yuqoridan CHEKLANMAYDI: 100% dan oshgan Performance ideal tezlik
        noto'g'ri qo'yilganini bildiradi va aynan shu ko'rinishi kerak.
        """
        if self.run_minutes <= 0:
            return None
        return self.ideal_minutes / self.run_minutes


async def machine_performance(
    db: AsyncSession, machine: Machine, post: Post, run_minutes: float, day_from: date, day_to: date
) -> Performance | None:
    """Ish markazida davr ichida ishlangan miqdor va uning ideal vaqti.

    Miqdor SKANLARDAN yig'iladi — skan bitta ish birligini bildiradi va unda
    ish markazi ham, vaqt ham bor. Bekor qilingan skanlar chiqariladi.

    Har post o'z birligida:
      ARRA      `part_instance.cut_meters` — varaq kesimining nusxaga tegishli ulushi
      KROMKA    detalning kromka metri (`metrics.part_volume`), nusxaga va qadamdagi
                skan soniga bo'linadi (KROMKA birinchi kelganda `per_instance` =
                qirralar soni, ya'ni bitta skan = bitta qirra)
      PRISADKA  `xnc_summary` dagi teshiklar soni, xuddi shunday bo'linadi
    """
    if machine.ideal_rate is None or post.code not in IDEAL_UNITS:
        return None
    unit, kind = IDEAL_UNITS[post.code]
    now = datetime.now(TASHKENT_TZ)
    start = datetime.combine(day_from, time.min, tzinfo=TASHKENT_TZ)
    end = min(datetime.combine(day_to + timedelta(days=1), time.min, tzinfo=TASHKENT_TZ), now)

    rows = (
        await db.execute(
            select(PartInstance.cut_meters, Part, PartRoute.per_instance, Part.count)
            .select_from(Scan)
            .join(PartInstance, PartInstance.id == Scan.instance_id)
            .join(Part, Part.id == Scan.part_id)
            .join(PartRoute, PartRoute.id == Scan.route_id)
            .where(
                Scan.machine_id == machine.id,
                Scan.is_cancelled == False,  # noqa: E712
                Scan.is_deleted == False,  # noqa: E712
                Scan.created_at >= start,
                Scan.created_at < end,
            )
        )
    ).all()

    quantity = 0.0
    for cut_meters, part, per_instance, count in rows:
        if post.code == PostCode.ARRA:
            quantity += cut_meters or 0.0
            continue
        # Nusxaga to'g'ri keladigan qiymat, keyin qadamdagi skan soniga bo'linadi
        per_scan = max(1, per_instance or 1)
        if post.code == PostCode.KROMKA:
            total = part_volume(post.code, length=part.length, width=part.width, count=part.count, edges=part.edges)
            quantity += total / max(1, count) / per_scan
        else:  # PRISADKA
            summary = part.xnc_summary or {}
            holes = int(summary.get("bores", 0)) + int(summary.get("edge_bores", 0))
            quantity += holes / per_scan

    ideal_minutes = quantity * machine.ideal_rate / 60 if kind == "sek" else quantity / machine.ideal_rate
    return Performance(quantity=quantity, unit=unit, ideal_minutes=ideal_minutes, run_minutes=run_minutes)
