"""Stanok to'xtashlari — Pico xom hodisalaridan (`andon_event`) chiqariladi, sababni smenadagi hodim kiritadi.

Qarorlar (2026-09-17, docs/12-oee.md §7; chegara qoidasi 2026-09-20 da o'zgardi):
- HAR QANDAY to'xtash — qizil chiroq (FAULT), hamma chiroq o'chgani (OFF), sariq chiroq
  (IDLE/STOPPED), kromka va rover lentasining to'xtashi — Tizim sozlamalaridagi
  `stop_prompt_idle_minutes` dan UZOQ davom etsagina sabab so'raydi. Ilgari qizil va
  o'chiq holat darhol so'rardi: tsexda bir daqiqalik kutishda ham oyna chiqib, operator
  uni o'qimasdan yopishga o'rganib qolardi (2026-09-20 tsex talabi);
- vaqt to'xtash BOSHLANGAN paytdan sanaladi, Pico'ning `idle_timeout_s` iga bog'liq emas;
- qulf tugmasi (LOCK) — operator sababni o'zi aytib to'xtatadi; shu oraliqda boshlangan Pico
  to'xtashi sababni qulfdan oladi va qayta so'ralmaydi (unga chegara qo'llanmaydi).

KROMKA va ROVER (2026-09-20) boshqacha gapiradi: ularda chiroq yo'q, RUN kirishi bor va u
faqat O'ZGARGANDA `uskuna` hodisasi keladi (`holat` 0/1). `holat=0` — lenta/shpindel to'xtagan,
ya'ni to'xtash (`OFF`); ROVER'da stanok yoqiq bo'lsa — bo'sh turish (`IDLE`, `andon.uskuna_state`).

Chegaradan qisqa to'xtash HISOBGA baribir kiradi (Availability oraliqlardan hisoblanadi) —
faqat SABAB so'ralmaydi.

Yozuvlar IDEMPOTENT: hisob har safar hodisalardan qaytadan yuritiladi va `start_key` (to'xtashni
boshlagan hodisa) bo'yicha mavjud yozuvning faqat `ended_at` i yangilanadi — sabab tegilmaydi.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AndonEvent, Downtime
from app.models.enums import DowntimeKind
from app.services.andon import rover_facts, split_idle, uskuna_spans, uskuna_state
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


def _stop_kind(ev: AndonEvent) -> DowntimeKind | None:
    """Hodisa to'xtash boshlaydimi va qaysi turdagi.

    PRISADKA (`state`) — chiroq holati bo'yicha; KROMKA/ROVER (`uskuna`) — RUN kirishi
    bo'yicha. Chegara TURGA bog'liq emas: hammasiga bir xil qo'llanadi (yuqoridagi izoh)."""
    if ev.kind == "state":
        return _STOP_KIND.get(ev.state or "")
    if ev.kind == "uskuna":
        return _STOP_KIND.get(uskuna_state(ev.payload or {}))
    return None


def _runs(events: list[AndonEvent]) -> list[_Run]:
    """Holat hodisalarini to'xtash oraliqlariga bo'ladi. Oxirgisi davom etayotgan bo'lsa `end=None`.

    Pico sessiyasi almashsa (qayta yuklandi — kompyuter o'chgan/uxlagan) oldingi to'xtash o'sha
    sessiyaning OXIRGI hodisasida yopiladi: undan keyin nima bo'lgani noma'lum (docs/12 — ma'lumotsiz
    vaqt alohida hisoblanadi, bu yerda taxmin qilinmaydi)."""
    out: list[_Run] = []
    cur: _Run | None = None
    prev: AndonEvent | None = None
    for ev in events:
        kind = _stop_kind(ev)
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
            cur = _Run(kind=kind, key=f"{ev.session}-{ev.seq}", session=ev.session, start=start)
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
                    AndonEvent.is_deleted == False,  # noqa: E712
                    AndonEvent.happened_at >= since,
                )
            )
        )
        .scalars()
        .all()
    )
    # Faqat ISHLAYOTGAN oraliqlar bo'linadi: ROVER'ning o'z IDLE holati (yoqiq, shpindel
    # to'xtagan) `_runs` da allaqachon to'xtash — bu yerga tushsa ikkinchi `idle-*` yozuv
    # bo'lib, chegarasiz (3 daqiqalik pauzaga ham) sabab so'ralardi.
    spans = [
        sp
        for sp in uskuna_spans(
            [(e.machine_id, e.payload or {}, e.happened_at) for e in uskuna],
            {machine_id},  # oxirgi oraliq shu hisob uchun hozirgacha cho'ziladi
        )
        if sp.state == "PROCESSING"
    ]
    return [
        _Run(kind=DowntimeKind.IDLE, key=f"idle-{int(sp.began.timestamp())}", session="", start=sp.began, end=sp.ended)
        for sp in split_idle(spans, {machine_id: sorted(olchovlar)}, gap, now)
        if sp.state == "IDLE"
    ]


#: Pico va agent bitta to'xtashni bir necha soniya farq bilan ko'radi (agent 10 s da so'raydi,
#: Pico RUN tushishini 30 s birlashtiradi) — shu oraliqda boshlangan yozuv o'sha to'xtash.
_ROVER_MOS = timedelta(seconds=60)


async def _rover_pico(
    db: AsyncSession, machine_id: int, since: datetime, threshold: timedelta, stops: list[_Run]
) -> list[_Run]:
    """ROVER: agent KO'RMAGAN to'xtashlar — Pico'ning fleshdagi yopiq davrlaridan.

    Agent uzilgan paytda shpindel to'xtashi va stanok o'chirilishi agentning `uskuna`
    zanjirida yo'q, Pico esa ularni aniq vaqt bilan saqlab, qaytgach yuboradi
    (`SPINDLE_IDLE`/`UNPLANNED_STOP`/`AUTO_SHUTDOWN` → IDLE, `POWER_CYCLE` → OFF). Agent o'zi
    ko'rgan to'xtash IKKINCHI marta yozilmaydi: o'sha turdagi yozuv (yoki shu sinxrondagi agent
    oralig'i) Pico davri bilan ustma-ust tushsa — o'tkazib yuboriladi; agent uni ulanish
    almashganda nol uzunlikda yopib qo'ygan bo'lsa — tugashi Pico'nikiga cho'ziladi.

    Kalit `rv-{seq}` — Pico raqami, qayta hisobda o'zgarmaydi."""
    rows = (
        await db.execute(
            select(AndonEvent.seq, AndonEvent.payload).where(
                AndonEvent.machine_id == machine_id,
                AndonEvent.kind == "rover",
                AndonEvent.is_deleted == False,  # noqa: E712
                AndonEvent.happened_at >= since,
            )
        )
    ).all()
    out: list[_Run] = []
    for seq, payload in rows:
        fact = rover_facts(payload or {})
        if fact is None or fact[0] == "ON" or fact[2] - fact[1] < threshold:
            continue
        label, a, b = fact
        kind = DowntimeKind.OFF if label == "OFF" else DowntimeKind.IDLE
        if any(
            r.kind == kind and r.start <= b + _ROVER_MOS and (r.end is None or r.end >= a - _ROVER_MOS) for r in stops
        ):
            continue
        agent_row = (
            await db.execute(
                select(Downtime)
                .where(
                    Downtime.machine_id == machine_id,
                    Downtime.kind == kind,
                    Downtime.is_deleted == False,  # noqa: E712
                    Downtime.start_key != f"rv-{seq}",
                    Downtime.started_at <= b + _ROVER_MOS,
                    (Downtime.ended_at.is_(None)) | (Downtime.ended_at >= a - _ROVER_MOS),
                )
                .limit(1)
            )
        ).scalar()
        if agent_row is not None:
            if agent_row.ended_at is not None and agent_row.ended_at == agent_row.started_at:
                agent_row.ended_at = b
            continue
        out.append(_Run(kind=kind, key=f"rv-{seq}", session="", start=a, end=b))
    return out


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
                AndonEvent.is_deleted == False,  # noqa: E712
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
                    AndonEvent.is_deleted == False,  # noqa: E712
                    AndonEvent.happened_at >= since,
                )
                .order_by(AndonEvent.happened_at, AndonEvent.id)
            )
        )
        .scalars()
        .all()
    )
    threshold = timedelta(minutes=int(await get_setting(db, STOP_PROMPT_IDLE_MINUTES)))
    stops = _runs(events)
    bosh = await _bosh_yurish(db, machine_id, events, since, now)
    bosh += await _rover_pico(db, machine_id, since, threshold, stops)
    if not stops and not bosh:
        return

    existing = {
        d.start_key: d
        for d in (
            await db.execute(
                select(Downtime).where(
                    Downtime.machine_id == machine_id,
                    Downtime.start_key.in_([r.key for r in [*stops, *bosh]]),
                )
            )
        ).scalars()
    }
    # Chegara HAMMA to'xtashga qo'llanadi (qizil chiroq ham): undan qisqasi — mikro-to'xtash,
    # uning sababi so'ralmaydi. Availability bunga bog'liq emas, u oraliqlardan hisoblanadi.
    # Lekin OCHIQ yozuv filtrdan qat'i nazar yangilanadi: ochiq paytida yozilgan to'xtash keyin
    # qisqa bo'lib yopilishi mumkin (Pico "o'chdi" hodisasidan keyin kompyuter o'chsa, oraliq
    # o'sha sessiyaning oxirgi hodisasida — ya'ni boshlanishida — yopiladi). Filtr uni ham
    # tashlasa yozuv MANGU ochiq qolardi va oynani (`since`) o'zi bilan orqaga tortardi:
    # 2026-09-26 da Kromka-1 ning 16 ta shunday yozuvi oynani 6 kunga cho'zgan, har so'rov
    # ~7 s CPU yeb o'sha jarayondagi boshqa so'rovlarni (chek chiqarish ham) kuttirgan.
    # Yopilgan yozuvga tegilmaydi — avvalgidek.
    runs = [
        r
        for r in stops
        if (r.end or now) - r.start >= threshold or (r.key in existing and existing[r.key].ended_at is None)
    ] + bosh

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
    # Qulf stanok ISHLAY BOSHLAGUNCHA amal qiladi (docs/12 §4.24): odatda qulf smena ochilganda yopiladi,
    # lekin stanok terminalga kirmasdan ham yurishi mumkin (Kromka skanersiz o'lchaydi, ertasi kuni
    # boshqa odam yoqadi). Shunda qulf ochiq qolib, keyingi HAMMA to'xtashga o'z (masalan rejali
    # «Tushlik») sababini berardi. Qulf yozuvining o'ziga tegilmaydi — terminal ekrani o'z holatida.
    lock_end: dict[int, datetime | None] = {}
    for lk in locks:
        ish = await db.scalar(
            select(func.min(AndonEvent.happened_at)).where(
                AndonEvent.machine_id == machine_id,
                AndonEvent.is_deleted == False,  # noqa: E712
                or_(
                    and_(AndonEvent.kind == "state", AndonEvent.state == "PROCESSING"),
                    and_(AndonEvent.kind == "uskuna", AndonEvent.payload["holat"].as_integer() == 1),
                ),
                AndonEvent.happened_at > lk.started_at,
            )
        )
        lock_end[lk.id] = min((t for t in (lk.ended_at, ish) if t is not None), default=None)
    for run in runs:
        row = existing.get(run.key)
        if row is not None:
            if row.ended_at != run.end:
                row.ended_at = run.end
            continue
        row = Downtime(machine_id=machine_id, kind=run.kind, start_key=run.key, started_at=run.start, ended_at=run.end)
        lock = next(
            (
                lk
                for lk in locks
                if lk.started_at <= run.start and ((end := lock_end[lk.id]) is None or run.start <= end)
            ),
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
