"""Stanok to'xtashlari — Pico xom hodisalaridan (`andon_event`) chiqariladi, sababni smenadagi hodim kiritadi.

Qarorlar (2026-09-17, docs/12-oee.md §7):
- qizil chiroq (FAULT) va hammasi o'chiq (OFF) — darhol to'xtash;
- sariq chiroq (IDLE, Pico keyin STOPPED deb ham yuboradi) — Tizim sozlamalaridagi
  `stop_prompt_idle_minutes` dan uzoq yonsa to'xtash. Vaqt SARIQ YONGAN PAYTDAN sanaladi,
  Pico'ning `idle_timeout_s` sozlamasiga bog'liq emas;
- qulf tugmasi (LOCK) — operator sababni o'zi aytib to'xtatadi; shu oraliqda boshlangan Pico
  to'xtashi sababni qulfdan oladi va qayta so'ralmaydi.

KROMKA stansiyasi (2026-09-20) boshqacha gapiradi: unda chiroq yo'q, RUN kirishi bor va u
faqat O'ZGARGANDA `uskuna` hodisasi keladi (`holat` 0/1). `holat=0` — lenta to'xtagan, ya'ni
to'xtash (`OFF`). Bunga ham `stop_prompt_idle_minutes` chegarasi qo'llanadi: kromkada lenta
detal qo'yish uchun qisqa to'xtaydi va har 40 soniyalik pauzada sabab so'ralsa, operator
oynani o'qimasdan yopishga o'rganib qolardi. Chegaradan qisqa to'xtash HISOBGA baribir kiradi
(Availability oraliqlardan hisoblanadi) — faqat SABAB so'ralmaydi.

Yozuvlar IDEMPOTENT: hisob har safar hodisalardan qaytadan yuritiladi va `start_key` (to'xtashni
boshlagan hodisa) bo'yicha mavjud yozuvning faqat `ended_at` i yangilanadi — sabab tegilmaydi.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AndonEvent, Downtime
from app.models.enums import DowntimeKind
from app.services.andon import split_idle, uskuna_spans
from app.services.settings_service import KROMKA_IDLE_MINUTES, STOP_PROMPT_IDLE_MINUTES, get_setting

#: Pico holati -> to'xtash turi. Qolgan holatlar (PROCESSING, AWAIT_PART, BOOT ...) — stanok ishlayapti.
_STOP_KIND = {
    "FAULT": DowntimeKind.FAULT,
    "OFF": DowntimeKind.OFF,
    "IDLE": DowntimeKind.IDLE,
    "STOPPED": DowntimeKind.IDLE,
}
#: Qayta hisoblash oynasi. Undan uzoq davom etayotgan (yopilmagan) to'xtash ham qamraladi:
#: oyna eng eski ochiq yozuvgacha va undan oldingi "ishlayapti" hodisasigacha kengaytiriladi.
SYNC_WINDOW = timedelta(hours=12)


@dataclass
class _Run:
    kind: DowntimeKind
    key: str
    session: str
    start: datetime
    end: datetime | None = None
    #: Sabab so'rash uchun chegara qo'llanadimi (sariq chiroq va kromka to'xtashlari uchun ha)
    chegarali: bool = False


def _stop_kind(ev: AndonEvent) -> tuple[DowntimeKind | None, bool]:
    """Hodisa to'xtash boshlaydimi: `(turi, chegarali)`.

    PRISADKA (`state`) — chiroq holati bo'yicha; qizil va hammasi o'chiq DARHOL, sariq
    chegaradan uzoq bo'lsa. KROMKA (`uskuna`) — RUN kirishi: `holat=0` to'xtash, unga ham
    chegara qo'llanadi (yuqoridagi izoh)."""
    if ev.kind == "state":
        kind = _STOP_KIND.get(ev.state or "")
        return kind, kind == DowntimeKind.IDLE
    if ev.kind == "uskuna":
        return (None, False) if (ev.payload or {}).get("holat") else (DowntimeKind.OFF, True)
    return None, False


def _runs(events: list[AndonEvent]) -> list[_Run]:
    """Holat hodisalarini to'xtash oraliqlariga bo'ladi. Oxirgisi davom etayotgan bo'lsa `end=None`.

    Pico sessiyasi almashsa (qayta yuklandi — kompyuter o'chgan/uxlagan) oldingi to'xtash o'sha
    sessiyaning OXIRGI hodisasida yopiladi: undan keyin nima bo'lgani noma'lum (docs/12 — ma'lumotsiz
    vaqt alohida hisoblanadi, bu yerda taxmin qilinmaydi)."""
    out: list[_Run] = []
    cur: _Run | None = None
    prev: AndonEvent | None = None
    for ev in events:
        kind, chegarali = _stop_kind(ev)
        if cur is not None and prev is not None and (ev.session != cur.session or kind != cur.kind):
            cur.end = ev.happened_at if ev.session == cur.session else prev.happened_at
            out.append(cur)
            cur = None
        if kind is not None and cur is None:
            start = ev.happened_at
            # Sariq birinchi marta STOPPED bo'lib kelgan bo'lsa (IDLE hodisasi oynadan tashqarida
            # yoki yo'qolgan) — boshlanish Pico o'lchagan IDLE davomiyligidan tiklanadi.
            if ev.state == "STOPPED" and ev.prev_state == "IDLE" and ev.prev_duration_s:
                start -= timedelta(seconds=ev.prev_duration_s)
            cur = _Run(kind=kind, key=f"{ev.session}-{ev.seq}", session=ev.session, start=start, chegarali=chegarali)
        prev = ev
    if cur is not None:
        out.append(cur)
    return out


async def _bosh_yurish(
    db: AsyncSession, machine_id: int, events: list[AndonEvent], since: datetime, now: datetime
) -> list[_Run]:
    """KROMKA: lenta yuryapti, lekin uzoq vaqt detal o'tmadi — bu ham to'xtash (`IDLE`).

    RUN kirishi «bo'sh yuryapti» deb aytmaydi, stansiya esa har detalni o'lchaydi:
    ikki o'lchov orasidagi uzoq tirqish lenta bo'sh aylanganini bildiradi (material yo'q,
    buyurtma yo'q, operator ketgan). Chegarasi ALOHIDA (`kromka_idle_minutes`, sukut 10):
    to'xtash 5 daqiqada so'raladi, bo'sh yurish esa uzunroq bo'lishi normal.

    Kalit `idle-{boshlanish unix}` — barqaror: boshlanish oxirgi o'lchov yoki lentaning
    yonish lahzasi, ya'ni qayta hisobda o'zgarmaydi va yozuv ikkilanmaydi."""
    uskuna = [e for e in events if e.kind == "uskuna"]
    if not uskuna:
        return []
    gap = timedelta(minutes=int(await get_setting(db, KROMKA_IDLE_MINUTES)))
    olchovlar = (
        (
            await db.execute(
                select(AndonEvent.happened_at).where(
                    AndonEvent.machine_id == machine_id,
                    AndonEvent.kind == "olchov",
                    AndonEvent.happened_at >= since,
                )
            )
        )
        .scalars()
        .all()
    )
    spans = uskuna_spans(
        [(e.machine_id, e.payload or {}, e.happened_at) for e in uskuna],
        {machine_id},  # oxirgi oraliq shu hisob uchun hozirgacha cho'ziladi
    )
    return [
        _Run(kind=DowntimeKind.IDLE, key=f"idle-{int(sp.began.timestamp())}", session="", start=sp.began, end=sp.ended)
        for sp in split_idle(spans, {machine_id: sorted(olchovlar)}, gap, now)
        if sp.state == "IDLE"
    ]


async def sync_machine(db: AsyncSession, machine_id: int, now: datetime) -> None:
    """Ish markazining Pico to'xtashlarini `downtime` jadvaliga yozadi yoki yangilaydi. Commit chaqiruvchida."""
    earliest_open = (
        await db.execute(
            select(func.min(Downtime.started_at)).where(
                Downtime.machine_id == machine_id,
                Downtime.kind != DowntimeKind.LOCK,
                Downtime.ended_at.is_(None),
                Downtime.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar()
    since = now - SYNC_WINDOW
    if earliest_open is not None and earliest_open < since:
        since = earliest_open
    # Oyna to'xtash O'RTASIDAN boshlanmasin: aks holda o'sha to'xtash boshqa kalit bilan ikkinchi
    # marta yozilardi. Oyna oldingi "ishlayapti" hodisasiga surib qo'yiladi.
    # «Ishlayapti» hodisasi: prisadkada to'xtash bo'lmagan chiroq holati, kromkada `holat=1`
    ishlayapti = or_(
        and_(AndonEvent.kind == "state", AndonEvent.state.notin_(list(_STOP_KIND))),
        and_(AndonEvent.kind == "uskuna", AndonEvent.payload["holat"].as_integer() == 1),
    )
    working_before = (
        await db.execute(
            select(func.max(AndonEvent.happened_at)).where(
                AndonEvent.machine_id == machine_id,
                ishlayapti,
                AndonEvent.happened_at <= since,
            )
        )
    ).scalar()
    if working_before is not None:
        since = working_before

    events = list(
        (
            await db.execute(
                select(AndonEvent)
                .where(
                    AndonEvent.machine_id == machine_id,
                    AndonEvent.kind.in_(("state", "uskuna")),
                    AndonEvent.happened_at >= since,
                )
                .order_by(AndonEvent.happened_at, AndonEvent.id)
            )
        )
        .scalars()
        .all()
    )
    threshold = timedelta(minutes=int(await get_setting(db, STOP_PROMPT_IDLE_MINUTES)))
    # Chegara sariq chiroqqa (prisadka) va kromka to'xtashlariga qo'llanadi — qisqasi
    # mikro-to'xtash, uning sababi so'ralmaydi
    runs = [r for r in _runs(events) if not r.chegarali or (r.end or now) - r.start >= threshold]
    runs += await _bosh_yurish(db, machine_id, events, since, now)
    if not runs:
        return

    existing = {
        d.start_key: d
        for d in (
            await db.execute(
                select(Downtime).where(
                    Downtime.machine_id == machine_id,
                    Downtime.start_key.in_([r.key for r in runs]),
                )
            )
        ).scalars()
    }
    locks = list(
        (
            await db.execute(
                select(Downtime).where(
                    Downtime.machine_id == machine_id,
                    Downtime.kind == DowntimeKind.LOCK,
                    Downtime.reason_id.is_not(None),
                    (Downtime.ended_at.is_(None)) | (Downtime.ended_at >= since),
                    Downtime.is_deleted == False,  # noqa: E712
                )
            )
        ).scalars()
    )
    for run in runs:
        row = existing.get(run.key)
        if row is not None:
            if row.ended_at != run.end:
                row.ended_at = run.end
            continue
        row = Downtime(machine_id=machine_id, kind=run.kind, start_key=run.key, started_at=run.start, ended_at=run.end)
        lock = next(
            (lk for lk in locks if lk.started_at <= run.start and (lk.ended_at is None or run.start <= lk.ended_at)),
            None,
        )
        if lock is not None:
            # Operator ketishdan oldin sababni aytgan — qulf ostida boshlangan to'xtash qayta so'ralmaydi
            row.reason_id, row.note, row.employee_id, row.reason_at = lock.reason_id, lock.note, lock.employee_id, now
        db.add(row)
    await db.flush()


async def close_open_locks(db: AsyncSession, machine_id: int, at: datetime) -> None:
    """Qulf to'xtashini yopadi — kimdir shu ish markazida smenani ochdi yoki qulfni beyjik bilan ochdi.

    `scanning.open_badge_session` chaqiradi: beyjik kirishi, terminaldagi tanlov va parol bilan
    kirish HAMMASI shu yerdan o'tadi. Commit chaqiruvchida."""
    await db.execute(
        update(Downtime)
        .where(
            Downtime.machine_id == machine_id,
            Downtime.kind == DowntimeKind.LOCK,
            Downtime.ended_at.is_(None),
            Downtime.is_deleted == False,  # noqa: E712
        )
        .values(ended_at=at)
    )
