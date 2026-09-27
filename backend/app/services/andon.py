"""Andon (stanok signal ustuni) — jonli holat Redis'da.

Jonli holat jadvalda EMAS: u har necha soniyada yangilanadi va faqat oxirgisi
kerak. Kalit TTL bilan yoziladi: agent xabar bermay qo'ysa holat o'zi yo'qoladi va
sahifa "aloqa yo'q" ko'rsatadi — eskirgan "Ishlov" yolg'on ko'rinib turmaydi.
Xom hodisalar esa `andon_event` jadvalida: tarix va OEE hisobi (`services/availability.py`,
`api/routes/reports.py`).
"""

import json
import logging
from bisect import bisect_left, bisect_right
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError

from app.core.config import TASHKENT_TZ, settings

logger = logging.getLogger(__name__)

ANDON_LIVE_KEY = "mes:andon:live:{}"
#: Agent har bir necha soniyada, bo'sh turganda ham har 30 soniyada yuboradi —
#: 90 soniya ichida kelmasa agent, kompyuter yoki Pico bilan aloqa yo'q.
ANDON_LIVE_TTL = 90


async def save_live(machine_id: int, live: dict[str, Any]) -> bool:
    """Jonli holatni yozadi. Holat yoki uning boshlangan vaqti O'ZGARGAN bo'lsa True.

    Qaytgan qiymat WS xabari uchun: agent har 30 soniyada bir xil holatni qayta
    yuboradi (TTL yangilansin), har safar ekranlarga xabar tarqatish shovqin bo'lardi.

    Redis ishlamasa False: xom hodisalar jadvalga allaqachon yozilgan, jonli holat
    esa yordamchi — uning xatosi agentga 500 qaytarib, navbatni qayta yubortirmasin."""
    try:
        async with AsyncRedis.from_url(settings.REDIS_URL) as redis:
            old_raw = await redis.set(ANDON_LIVE_KEY.format(machine_id), json.dumps(live), ex=ANDON_LIVE_TTL, get=True)
    except (RedisError, OSError) as exc:
        logger.warning("andon jonli holati yozilmadi (machine %s): %r", machine_id, exc)
        return False
    if old_raw is None:
        return True
    try:
        old = json.loads(old_raw)
    except ValueError:
        return True
    return bool(old.get("state") != live.get("state") or old.get("since") != live.get("since"))


async def read_live(machine_ids: Iterable[int]) -> dict[int, dict[str, Any]]:
    """Bir nechta ish markazining jonli holati (andon ulanmagan yoki aloqa yo'q — kalit yo'q).

    Redis ishlamasa bo'sh lug'at: ish markazlari sahifasi andon holatisiz ochilaversin."""
    ids = list(machine_ids)
    if not ids:
        return {}
    try:
        async with AsyncRedis.from_url(settings.REDIS_URL) as redis:
            rows = await redis.mget([ANDON_LIVE_KEY.format(mid) for mid in ids])
    except (RedisError, OSError) as exc:
        logger.warning("andon jonli holati o'qilmadi: %r", exc)
        return {}
    out: dict[int, dict[str, Any]] = {}
    for mid, raw in zip(ids, rows, strict=True):
        if raw is None:
            continue
        try:
            out[mid] = json.loads(raw)
        except ValueError:
            continue
    return out


#: Hisobotga kiradigan chiroq holatlari (Pico firmware `fsm.py`). BOOT — qurilma
#: yuklanishi, stanok vaqti emas: hisobga kirmaydi.
ANDON_STATES = ("PROCESSING", "AWAIT_PART", "IDLE", "STOPPED", "FAULT", "OFF")


@dataclass
class AndonSpan:
    """Bitta holat oralig'i (hisobot oralig'iga kesilmagan). `ended` None — hali davom etmoqda."""

    machine_id: int
    state: str
    began: datetime
    ended: datetime | None


def uskuna_spans(
    events: Iterable[tuple[int, dict[str, Any], datetime]],
    live: set[int],
) -> list[AndonSpan]:
    """KROMKA stansiyasi hodisalaridan holat oraliqlari.

    Prisadka signal ustuni har holat tugaganda uning DAVOMIYLIGINI beradi
    (`prev_duration_s`, Pico o'zi o'lchaydi) — `andon_spans` shuni ishlatadi.
    Kromka Pico'sida chiroq yo'q: u faqat RUN kirishi o'zgarganda `uskuna`
    hodisasini yuboradi (`holat` 0/1). Shuning uchun oraliq SHU YERDA quriladi:
    har hodisa oldingisini yopadi, oxirgisi `now` gacha davom etadi.

    `holat=1` → PROCESSING (lenta yuryapti), `holat=0` → OFF. OFF ataylab: bizda
    u DARHOL to'xtash deb sanaladi, sariq chiroqning mikro-to'xtash chegarasi esa
    kromkada ma'nosiz — u yerda «kutish» degan oraliq holat umuman yo'q.

    `events` — `(machine_id, payload, happened_at)`, VAQT bo'yicha tartiblangan.
    `live` — hozir aloqada turgan ish markazlari: faqat ular uchun OXIRGI oraliq
    ochiq qoldiriladi (hozirgacha davom etadi). Agent jim bo'lsa oxirgi hodisadan
    keyingi vaqt NOMA'LUM — u oraliq umuman qo'shilmaydi va hisobotda «stanok
    o'chiq» bo'lib chiqadi (bizdagi umumiy qoida).
    """
    ochiq: dict[int, AndonSpan] = {}
    spans: list[AndonSpan] = []
    for machine_id, payload, at in events:
        holat = "PROCESSING" if payload.get("holat") else "OFF"
        oldingi = ochiq.get(machine_id)
        if oldingi is not None:
            if oldingi.state == holat:
                continue  # takror hodisa — oraliq bo'linmaydi
            oldingi.ended = at
            spans.append(oldingi)
        ochiq[machine_id] = AndonSpan(machine_id, holat, at, None)
    spans += [span for mid, span in ochiq.items() if mid in live]
    return spans


def split_idle(
    spans: Iterable[AndonSpan],
    measurements: dict[int, list[datetime]],
    gap: timedelta,
    now: datetime,
) -> list[AndonSpan]:
    """Ishlayotgan oraliqni O'LCHOVLAR bo'yicha bo'ladi: uzoq vaqt detal o'tmagan qismi — IDLE.

    Kromkada «kutish» degan signal yo'q: RUN yoqiq bo'lsa lenta yuryapti, detal bor-yo'qligini
    kirish aytmaydi. Lekin stansiya har detalni o'lchaydi — ya'ni ikki o'lchov orasidagi uzoq
    tirqish lenta BO'SH aylanganini bildiradi (material yo'q, buyurtma yo'q, operator ketgan).
    O'sha vaqt «ishladi» ga kirsa Availability yolg'on ko'tarilardi.

    `gap` — bo'sh yurish chegarasi (`kromka_idle_minutes`). Undan qisqa tirqish — detal
    almashtirish, oddiy ish ritmi.

    Faqat PROCESSING bo'linadi: to'xtash (OFF) allaqachon yo'qotish.

    MUHIM: bitta ham o'lchov bo'lmagan stanok TEGILMAYDI. Aks holda datchigi buzuq yoki
    ulanmagan stansiya butun kunni «bo'sh yurish» deb ko'rsatardi — ya'ni apparat nosozligi
    ishlab chiqarish yo'qotishi bo'lib yozilardi va Availability nolga tushardi. O'lchov
    yo'qligi «lenta bo'sh» degani emas, «bilmaymiz» degani; bilmagan narsani ayblamaymiz.
    Datchik nosozligini Pico o'zi alohida aytadi (`ogoh`: javob_yoq, iflos).

    `measurements` ro'yxatlari VAQT BO'YICHA SARALANGAN bo'lishi shart (ikkala chaqiruvchi
    ham shunday beradi): oraliqdagi o'lchovlar ikkilik qidiruv bilan kesib olinadi. Ilgari
    har oraliq butun ro'yxatni aylanardi — (oraliqlar × o'lchovlar), 6 kunlik oynada 1,5 s
    CPU edi (2026-09-26 o'lchovi)."""
    out: list[AndonSpan] = []
    for span in spans:
        belgilar_hammasi = measurements.get(span.machine_id)
        if span.state != "PROCESSING" or not belgilar_hammasi:
            out.append(span)
            continue
        end = span.ended or now
        belgilar = belgilar_hammasi[bisect_left(belgilar_hammasi, span.began) : bisect_right(belgilar_hammasi, end)]
        cur = span.began
        for t in [*belgilar, end]:
            if t - cur >= gap:
                out.append(AndonSpan(span.machine_id, "IDLE", cur, t))
            elif t > cur:
                out.append(AndonSpan(span.machine_id, "PROCESSING", cur, t))
            cur = t
    return out


@dataclass
class MachineTime:
    """`machine_time` natijasi: soniyalar hisobot oralig'iga KESILGAN.

    To'xtashlarning BITTALAB ro'yxati ataylab yo'q (2026-09-19): rahbarga kerakli narsa —
    umumiy to'xtash vaqti va uning sabablari (`services/availability.py`), ketma-ket
    o'nlab qator emas."""

    seconds: dict[int, dict[str, int]] = field(default_factory=dict)
    days: dict[tuple[int, date], dict[str, int]] = field(default_factory=dict)


def andon_spans(
    events: Iterable[tuple[int, str | None, int | None, datetime]],
    ongoing: dict[int, tuple[str, datetime]],
) -> list[AndonSpan]:
    """Hodisalardan holat oraliqlari.

    `events` — `(machine_id, prev_state, prev_duration_s, happened_at)`: har `state` hodisasi
    OLDINGI holat tugaganini aytadi — u `prev_duration_s` soniya davom etib `happened_at` da
    tugagan. Davomiylikni Pico o'zi o'lchaydi, ya'ni agent uzilib hodisa kechikib kelsa ham
    uzunlik to'g'ri qoladi (faqat joylashuvi qabul vaqtiga siljiydi).
    `ongoing` — machine_id -> (joriy holat, boshlangan vaqt): tugamagan oxirgi holat.
    """
    spans = [
        AndonSpan(mid, prev_state, at - timedelta(seconds=dur), at)
        for mid, prev_state, dur, at in events
        if prev_state is not None and prev_state in ANDON_STATES and dur is not None and dur >= 0
    ]
    spans += [AndonSpan(mid, state, began, None) for mid, (state, began) in ongoing.items() if state in ANDON_STATES]
    return spans


def machine_time(spans: Iterable[AndonSpan], start: datetime, end: datetime, now: datetime) -> MachineTime:
    """Oraliqlarni [start, end] ga kesib stanok va kun (Toshkent) bo'yicha soniyalarga yig'adi.

    Tugamagan oraliq `now` gacha hisoblanadi. Kun chegarasidan o'tgan oraliq (tungi OFF)
    ikki kunga bo'linadi — har kun o'z vaqtini oladi."""
    out = MachineTime()
    cut_end = min(end, now)
    for span in spans:
        ended = span.ended or now
        a, b = max(span.began, start), min(ended, cut_end)
        if b <= a:
            continue
        per_machine = out.seconds.setdefault(span.machine_id, dict.fromkeys(ANDON_STATES, 0))
        per_machine[span.state] += int((b - a).total_seconds())
        cur = a
        while cur < b:
            local_day = cur.astimezone(TASHKENT_TZ).date()
            next_midnight = datetime.combine(local_day + timedelta(days=1), time.min, tzinfo=TASHKENT_TZ)
            seg_end = min(b, next_midnight)
            per_day = out.days.setdefault((span.machine_id, local_day), dict.fromkeys(ANDON_STATES, 0))
            per_day[span.state] += int((seg_end - cur).total_seconds())
            cur = seg_end
    return out
