"""OEE Availability — reja vaqti (ish jadvali) va stanok to'xtashlari bo'yicha. Sof funksiyalar, DB yo'q.

Formula (docs/12-oee.md §1):

    smena vaqti  = ish jadvalidagi smenalar − tanaffuslar (dam olish kuni va bayramda 0)
    reja vaqti   = smena vaqti − REJALI to'xtashlar
    ishlagan     = reja vaqti − rejasiz to'xtashlar − ma'lumotsiz vaqt
    Availability = ishlagan ÷ reja vaqti

To'xtash qoidasi `services/downtimes.py` bilan BIR XIL: qizil (FAULT) va hammasi o'chiq (OFF) —
darhol; sariq (IDLE/STOPPED) — `stop_prompt_idle_minutes` dan uzoq yonsa, qisqasi mikro-to'xtash
(Performance yo'qotishi, Availability emas). Pico'dan ma'lumot yo'q vaqt — to'xtash (2026-09-17
qarori: Prisadka Nanxing kompyuterisiz ishlamaydi, Pico shu kompyuterdan quvvat oladi).

Oraliqlar `services/andon.andon_spans` dan olinadi, `downtime` jadvali esa faqat SABAB uchun:
shunda jadval paydo bo'lishidan oldingi kunlar ham to'g'ri hisoblanadi.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from app.core.config import TASHKENT_TZ
from app.schemas.settings import WorkSchedule
from app.services.andon import AndonSpan

Interval = tuple[datetime, datetime]

_DAY_MIN = 24 * 60
_YELLOW = ("IDLE", "STOPPED")
_STOP_STATES = ("FAULT", "OFF", *_YELLOW)
#: Ketma-ket sariq oraliqlar bitta to'xtash: Pico davomiylikni butun soniyada beradi,
#: ya'ni IDLE tugashi bilan STOPPED boshlanishi orasida 1-2 soniyalik "tirqish" chiqadi.
_JOIN_GAP = timedelta(seconds=2)


@dataclass
class StopRun:
    """Bitta to'xtash (hisobot oralig'iga kesilmagan). Sabab `reason_of` orqali keyin biriktiriladi."""

    began: datetime
    ended: datetime
    reason_id: int | None = None
    reason_name: str | None = None
    is_planned: bool = False


@dataclass
class DayTotals:
    shift_s: int = 0
    planned_stop_s: int = 0
    unplanned_stop_s: int = 0
    no_data_s: int = 0

    @property
    def planned_s(self) -> int:
        return self.shift_s - self.planned_stop_s

    @property
    def run_s(self) -> int:
        return max(self.planned_s - self.unplanned_stop_s - self.no_data_s, 0)

    @property
    def availability_pct(self) -> float | None:
        return round(self.run_s * 100 / self.planned_s, 1) if self.planned_s > 0 else None

    @property
    def coverage_pct(self) -> float | None:
        return round((self.shift_s - self.no_data_s) * 100 / self.shift_s, 1) if self.shift_s > 0 else None


@dataclass
class ReasonTotals:
    reason_id: int | None
    name: str | None
    is_planned: bool
    seconds: int = 0
    count: int = 0


@dataclass
class Availability:
    total: DayTotals = field(default_factory=DayTotals)
    days: dict[date, DayTotals] = field(default_factory=dict)
    reasons: list[ReasonTotals] = field(default_factory=list)


def _minutes(clock: str) -> int:
    hours, minutes = clock.split(":")
    return int(hours) * 60 + int(minutes)


def _merge(items: Iterable[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for a, b in sorted(i for i in items if i[1] > i[0]):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _intersect(xs: list[Interval], ys: list[Interval]) -> list[Interval]:
    """Ikki BIRLASHTIRILGAN (`_merge`) ro'yxatning kesishmasi."""
    out: list[Interval] = []
    i = j = 0
    while i < len(xs) and j < len(ys):
        a, b = max(xs[i][0], ys[j][0]), min(xs[i][1], ys[j][1])
        if b > a:
            out.append((a, b))
        if xs[i][1] < ys[j][1]:
            i += 1
        else:
            j += 1
    return out


def _subtract(xs: list[Interval], ys: list[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for a, b in xs:
        cur = a
        for c, d in ys:
            if d <= cur or c >= b:
                continue
            if c > cur:
                out.append((cur, c))
            cur = max(cur, d)
        if cur < b:
            out.append((cur, b))
    return out


def _by_day(items: Iterable[Interval]) -> dict[date, int]:
    """Soniyalar Toshkent kuni bo'yicha; yarim tundan o'tgan oraliq ikki kunga bo'linadi."""
    out: dict[date, int] = {}
    for a, b in items:
        cur = a
        while cur < b:
            day = cur.astimezone(TASHKENT_TZ).date()
            nxt = datetime.combine(day + timedelta(days=1), time.min, tzinfo=TASHKENT_TZ)
            seg_end = min(b, nxt)
            out[day] = out.get(day, 0) + int((seg_end - cur).total_seconds())
            cur = seg_end
    return out


def plan_windows(schedule: WorkSchedule, start: datetime, end: datetime) -> list[Interval]:
    """Ish jadvali bo'yicha ish vaqti oraliqlari (tanaffuslar chiqarilgan), [start, end] ga kesilgan.

    Smena BOSHLANGAN kuniga tegishli: 22:00 da boshlangan tungi smena ertasi kuni dam olish
    bo'lsa ham 06:00 gacha davom etadi, dam olish kuni kechqurun esa smena boshlanmaydi."""
    days_off = set(schedule.days_off)
    holidays = {h.day for h in schedule.holidays}
    work: list[Interval] = []
    breaks: list[Interval] = []
    day = start.astimezone(TASHKENT_TZ).date() - timedelta(days=1)  # kechagi tungi smena bugunga o'tadi
    last = end.astimezone(TASHKENT_TZ).date()
    while day <= last:
        if day.isoweekday() not in days_off and day not in holidays:
            midnight = datetime.combine(day, time.min, tzinfo=TASHKENT_TZ)
            for shift in schedule.shifts:
                first = _minutes(shift.start)
                length = (_minutes(shift.end) - first) % _DAY_MIN
                began = midnight + timedelta(minutes=first)
                work.append((began, began + timedelta(minutes=length)))
                for brk in shift.breaks:
                    offset = (_minutes(brk.start) - first) % _DAY_MIN
                    brk_len = (_minutes(brk.end) - _minutes(brk.start)) % _DAY_MIN
                    breaks.append((began + timedelta(minutes=offset), began + timedelta(minutes=offset + brk_len)))
        day += timedelta(days=1)
    return _intersect(_subtract(_merge(work), _merge(breaks)), [(start, end)])


def stop_runs(spans: Iterable[AndonSpan], idle_threshold: timedelta, now: datetime) -> list[StopRun]:
    """Bitta ish markazining holat oraliqlaridan to'xtashlar. Qisqa sariq (mikro-to'xtash) tashlanadi."""
    out: list[StopRun] = []
    cur: tuple[str, datetime, datetime] | None = None  # (sinf, boshlanish, tugash)

    def close() -> None:
        if cur is not None and (cur[0] != "YELLOW" or cur[2] - cur[1] >= idle_threshold):
            out.append(StopRun(cur[1], cur[2]))

    for span in sorted((s for s in spans if s.state in _STOP_STATES), key=lambda s: s.began):
        kind = "YELLOW" if span.state in _YELLOW else span.state
        ended = span.ended or now
        if cur is not None and cur[0] == kind and span.began - cur[2] <= _JOIN_GAP:
            cur = (kind, cur[1], max(cur[2], ended))
            continue
        close()
        cur = (kind, span.began, ended)
    close()
    return out


def availability(
    spans: list[AndonSpan],
    windows: list[Interval],
    idle_threshold: timedelta,
    now: datetime,
    reason_of: Callable[[StopRun], tuple[int, str, bool] | None],
) -> Availability:
    """Bitta ish markazi uchun. `windows` — `plan_windows` natijasi (hozirgacha kesilgan).

    `reason_of(run)` — to'xtashga mos `(reason_id, nom, rejali)` yoki None (sabab kiritilmagan).
    """
    known = _merge((s.began, s.ended or now) for s in spans)
    planned: list[Interval] = []
    unplanned: list[Interval] = []
    reasons: dict[int | None, ReasonTotals] = {}
    for run in stop_runs(spans, idle_threshold, now):
        inside = _intersect([(run.began, run.ended)], windows)
        seconds = sum(int((b - a).total_seconds()) for a, b in inside)
        if not seconds:
            continue
        found = reason_of(run)
        if found is not None:
            run.reason_id, run.reason_name, run.is_planned = found
        (planned if run.is_planned else unplanned).extend(inside)
        row = reasons.setdefault(run.reason_id, ReasonTotals(run.reason_id, run.reason_name, run.is_planned))
        row.seconds += seconds
        row.count += 1

    parts = {
        "shift_s": _by_day(windows),
        "planned_stop_s": _by_day(_merge(planned)),
        "unplanned_stop_s": _by_day(_merge(unplanned)),
        "no_data_s": _by_day(_subtract(windows, known)),
    }
    out = Availability(reasons=sorted(reasons.values(), key=lambda r: -r.seconds))
    for name, per_day in parts.items():
        for day, seconds in per_day.items():
            totals = out.days.setdefault(day, DayTotals())
            setattr(totals, name, getattr(totals, name) + seconds)
            setattr(out.total, name, getattr(out.total, name) + seconds)
    return out
