"""Kromka o'lchovini DETALGA bog'lash (`docs/12-oee.md` §4.10).

Model — KIRISH VAQTI: detal birinchi datchikka kirgan lahzaga eng yaqin skan.

2026-09-21 gacha «oxirgi skan» olinardi va bu prodda XATO berdi: detal D1 dan D2
gacha 8–15 soniya yuradi (2553 mm oraliq, 10 yoki 18 m/min), operator esa 4–10
soniyada bir marta skanerlaydi — ya'ni endi kelgan o'lchov 2–4 ta skan OLDINGI
detalniki. Har detal MES da ikki marta chiqardi: avval «mos emas», keyin «mos»
(stansiya egasining o'lchovi, `docs/onlayn_mes_hodisalar.md`).

Endi kirish lahzasi o'lchovdan hisoblanadi: `kirish = o'lchov vaqti − (ish_ms + d2)`
(`ish_ms` — Pico bergan D1→D2 old qirralar orasidagi vaqt, `d2` — detal D2 ostidan o'tgan
vaqt; o'lchov D2 dan CHIQQANDA tayyor bo'ladi). Nomzod skanlar shu lahzadan
`kromka_bind_before_s` (sukut 60 s) OLDIN va `kromka_bind_window_s` (sukut 20 s) KEYIN
oralig'idan olinadi — operator detalni odatda lentaga qo'yishdan oldin skanerlaydi,
ba'zan bir necha detal oldindan. Ular orasidan O'LCHAMGA mos keladigani tanlanadi:
289 mm o'lchov 700 mm lik detalga yozilib qolmasin.
«Joriy detal» degan alohida holat saqlanmaydi: terminal qulasa ham, agent qayta
ulansa ham skan bazada turaveradi.

Tomonlar GURUH bo'yicha sanaladi, nom bo'yicha emas: 430x520 detalning t/b qirrasi
520 mm, l/r qirrasi 430 mm — bir xil uzunlikdagi ikki qirrani o'lchov ajrata
olmaydi va ajratishi SHART EMAS, ikkalasi ham lentalanadi. Shuning uchun tartib
ham ahamiyatsiz: operator qaysi tomonni oldin qo'ysa — o'sha guruhdan bitta joy
yopiladi.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KromkaMeasurement, Part, PartInstance, Scan
from app.models.enums import KromkaVerdict

#: `Part.edges` kalitlari qaysi o'lchamga tegishli: yuqori/past qirra detal
#: UZUNLIGI bo'ylab ketadi, chap/o'ng qirra ENI bo'ylab.
_SIDE_GROUP = {"t": "length", "b": "length", "l": "width", "r": "width"}

# 2026-09-20 gacha `nomos` o'lchov brak qaydini O'ZI ochardi. Tsexda datchik uzunlikka
# qarab XATO o'lchayotgani aniqlandi — o'sha qaydlar soxta bo'lib chiqdi, shuning uchun
# avtomatik brak O'CHIRILDI (`d4b8e1f37c92` eski qatorlarni tozalagan). Brak faqat
# operator skandan keyin BRAK tugmasini bossa yoziladi. O'lchov hozircha KUZATUV:
# hukmi ekranda ko'rinadi, hech narsani bloklamaydi va hech kimni ayblamaydi.
# Datchik to'g'rilangach avtomatik brak qaytariladi (docs/12 §4.10; eski sabab matni —
# «O'lcham mos emas»).


@dataclass(slots=True)
class BindResult:
    """Bitta o'lchovning hukmi va shu nusxa bo'yicha guruh hisobi (terminal ko'rsatadi)."""

    row: KromkaMeasurement
    #: {"length": {"expected": 520.0, "done": 2, "quota": 2}, ...} — hukm YOZILGANDAN keyingi holat
    progress: dict[str, dict[str, float]]
    scan_id: int | None
    #: Ekranlarda ko'rinadigan detal — «qaysi detal o'tdi» degan savolga javob
    part_name: str | None = None
    qr_text: str | None = None


def edge_quota(part: Part) -> dict[str, dict[str, float]]:
    """Detalda qaysi guruhdan nechta qirra lentalanishi va ularning kutilgan uzunligi.

    Lentalanmaydigan tomon bu yerga umuman tushmaydi — uni o'lchash ham kerak emas."""
    dims = {"length": part.length, "width": part.width}
    quota: dict[str, dict[str, float]] = {}
    for side, spec in (part.edges or {}).items():
        group = _SIDE_GROUP.get(side)
        if group is None or not spec:
            continue
        expected = dims.get(group)
        if not expected:
            # O'lchamsiz detal — kutilgan uzunlik yo'q, hukm ham chiqmaydi
            continue
        slot = quota.setdefault(group, {"expected": float(expected), "quota": 0, "done": 0})
        slot["quota"] += 1
    return quota


async def _nomzodlar(
    db: AsyncSession, machine_id: int, kirish: datetime, before: timedelta, after: timedelta
) -> list[Scan]:
    """Kirish lahzasi atrofidagi bekor qilinmagan skanlar — ENG ESKISI birinchi (FIFO).

    Oyna ASIMMETRIK (stansiya egasining tavsiyasi): operator odatda detalni lentaga
    qo'yishdan OLDIN skanerlaydi, ba'zan bir necha detal oldindan (`before`, sukut 60 s);
    lekin keyin ham skanerlashi mumkin — chek qo'lida qoladi (`after`, sukut 20 s)."""
    rows = (
        (
            await db.execute(
                select(Scan)
                .where(
                    Scan.machine_id == machine_id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                    Scan.created_at >= kirish - before,
                    Scan.created_at <= kirish + after,
                )
                .order_by(Scan.created_at)
            )
        )
        .scalars()
        .all()
    )
    # FIFO (so'rov tartibi): «eng yaqini» qoidasida bir xil o'lchamli ikki detal oldindan
    # skanerlansa, birinchi kirgan detalning o'lchovi KEYINGI skanga yopishardi
    return list(rows)


def _son(value: Any) -> float:
    """Pico bergan musbat son, aks holda 0."""
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else 0.0


def _kirish(at: datetime, payload: dict[str, Any]) -> datetime:
    """Detal BIRINCHI datchikka kirgan lahza: `o'lchov vaqti − (ish_ms + d2)`.

    O'lchov detal D2 dan CHIQQANDA tayyor bo'ladi. `ish_ms` — D1 va D2 old qirralari
    orasidagi vaqt (ms), `d2` — detal D2 nurini to'sib turgan vaqt (µs), ya'ni uzunlik ÷
    tezlik. Stansiya egasining formulasi (`docs/onlayn_mes_hodisalar.md` §5, `stansiya.html:
    kirishVaqti`). 2026-10-16 gacha `d2` ayirilmasdi — kirish detal uzunligicha KECH
    hisoblanardi (stansiya bazasida median 2.5 s, 10% da 7 s dan ko'p, eng ko'pi 30 s) va
    uzun detalning oldindan qilingan skani oynadan chiqib qolardi.

    `ish_ms` bo'lmasa (eski proshivka yoki FAQAT1/FAQAT2) o'lchov vaqtining o'zi olinadi."""
    ish_ms = _son(payload.get("ish_ms"))
    if not ish_ms:
        return at
    d2_ms = _son(payload.get("d2")) / 1000.0
    return at - timedelta(milliseconds=min(ish_ms + d2_ms, 180_000))


async def bind_measurement(
    db: AsyncSession,
    machine_id: int,
    at: datetime,
    payload: dict[str, Any],
    *,
    tolerance_mm: float,
    before: timedelta,
    after: timedelta,
) -> BindResult:
    """Bitta `olchov` hodisasini detalga bog'laydi va hukm yozadi. `flush` chaqiruvchida.

    Hukmlar:
    * `shubhali` — Pico kodi OK emas (bitta datchik ishlagan yoki farq katta): o'lcham
      ishonchsiz, DETALNI ayblash mumkin emas.
    * `skanersiz` — oyna ichida skan yo'q: detal kim ekani noma'lum, faqat tarix.
      Juftlash XATOSI ham shu yerga tushadi (stansiya egasining tavsiyasi): nomzod
      topilmasa brak deb belgilanmaydi.
    * `mos` — guruhdan bo'sh joy bor va o'lcham dopusk ichida: qirra yopildi.
    * `ortiqcha` — o'lcham to'g'ri, lekin o'sha guruh kvotasi tugagan: OGOHLANTIRISH.
      Brak emas — ikki marta o'tkazish (qayta lentalash) normal hodisa.
    * `nomos` — hech bir guruhga to'g'ri kelmadi. HOZIRCHA hech narsa qilmaydi:
      faqat ekranda ko'rinadi (datchik ishonchsiz — yuqoridagi izoh).
    """
    measured = payload.get("L")
    code = str(payload.get("kod") or "?")[:10]
    row = KromkaMeasurement(
        machine_id=machine_id,
        measured_at=at,
        code=code,
        verdict=KromkaVerdict.SHUBHALI,
        measured_mm=float(measured) if measured else None,
    )

    progress: dict[str, dict[str, float]] = {}
    part_name: str | None = None
    qr_text: str | None = None
    if code == "OK" and measured:
        kirish = _kirish(at, payload)
        tanlov = await _tanla(db, machine_id, kirish, before, after, float(measured), tolerance_mm)
        if tanlov is None:
            row.verdict = KromkaVerdict.SKANERSIZ
        else:
            scan, progress = tanlov
            row.scan_id, row.instance_id, row.order_id = scan.id, scan.instance_id, scan.order_id
            part = await db.get(Part, scan.part_id)
            instance = await db.get(PartInstance, scan.instance_id)
            part_name, qr_text = (part.name if part else None), (instance.qr_text if instance else None)
            _judge(row, progress, float(measured), tolerance_mm)
            if row.verdict == KromkaVerdict.MOS and row.side_group:
                # Yangi qator hali yozilmagan — terminal ko'radigan hisobga qo'lda qo'shiladi
                progress[row.side_group]["done"] += 1

    db.add(row)
    return BindResult(row=row, progress=progress, scan_id=row.scan_id, part_name=part_name, qr_text=qr_text)


async def _tanla(
    db: AsyncSession,
    machine_id: int,
    kirish: datetime,
    before: timedelta,
    after: timedelta,
    measured: float,
    tol: float,
) -> tuple[Scan, dict[str, dict[str, float]]] | None:
    """Kirish lahzasi atrofidagi skanlardan SHU o'lchovga mos keladiganini tanlaydi.

    Kromka'da BITTA SKAN = BITTA QIRRA O'TISHI (`per_instance` = qirralar soni): operator har
    qirrani alohida skanerlaydi. Shuning uchun tanlov SKAN darajasida, FIFO bilan (stansiya
    egasining tavsiyasi, `docs/onlayn_mes_hodisalar.md` §5 — lentada detallar bir-birini
    quvib o'tmaydi, oldindan skanerlangani oldin kiradi):
    1. hali o'lchov bog'lanmagan, o'lchamga mos va nusxaning o'sha guruhi ochiq skan — ENG ESKISI;
    2. o'lchamga mos, guruhi ochiq, lekin skani allaqachon band — operator bitta skan bilan bir
       necha qirra o'tkazgan;
    3. o'lchamga mos, lekin kvotasi tugagan (takroriy o'tish — `ortiqcha`);
    4. hech biri mos kelmasa — kirishga vaqt bo'yicha eng yaqini (hukmi `nomos`).
    Bo'sh oyna — `None`: bu brak emas, juftlash uchun ma'lumot yo'q."""
    nomzodlar = await _nomzodlar(db, machine_id, kirish, before, after)
    if not nomzodlar:
        return None
    band = set(
        (
            await db.execute(
                select(KromkaMeasurement.scan_id).where(
                    KromkaMeasurement.scan_id.in_([s.id for s in nomzodlar]),
                    KromkaMeasurement.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    bosh: tuple[Scan, dict[str, dict[str, float]]] | None = None
    ochiq: tuple[Scan, dict[str, dict[str, float]]] | None = None
    tugagan: tuple[Scan, dict[str, dict[str, float]]] | None = None
    for scan in nomzodlar:
        progress = await _progress(db, scan.instance_id, await db.get(Part, scan.part_id))
        mos = [g for g, sl in progress.items() if abs(measured - sl["expected"]) <= tol]
        if not mos:
            continue
        if any(progress[g]["done"] < progress[g]["quota"] for g in mos):
            if scan.id not in band:
                bosh = (scan, progress)
                break  # eng eski bo'sh skan — qidirishning ma'nosi yo'q
            ochiq = ochiq or (scan, progress)
        else:
            tugagan = tugagan or (scan, progress)
    tanlov = bosh or ochiq or tugagan
    if tanlov is not None:
        return tanlov
    yaqin = min(nomzodlar, key=lambda s: abs((s.created_at - kirish).total_seconds()))
    return yaqin, await _progress(db, yaqin.instance_id, await db.get(Part, yaqin.part_id))


def _judge(row: KromkaMeasurement, progress: dict[str, dict[str, float]], measured: float, tol: float) -> None:
    """Kvota va dopuskka qarab hukm qo'yadi. Ikki guruh ham mos kelsa (kvadratga yaqin
    detal) — bo'sh joyi bori tanlanadi: operator o'lchov ajrata olmagan joyda ishni
    to'xtatib turishdan ko'ra qirrani yopgani to'g'riroq."""
    if not progress:
        # Detalning o'lchami yoki qirra ro'yxati yo'q — solishtiradigan narsa yo'q
        row.verdict = KromkaVerdict.SHUBHALI
        return
    mos = sorted(
        (g for g, s in progress.items() if abs(measured - s["expected"]) <= tol),
        key=lambda g: abs(measured - progress[g]["expected"]),
    )
    bosh = [g for g in mos if progress[g]["done"] < progress[g]["quota"]]
    group = bosh[0] if bosh else (mos[0] if mos else None)
    if group is None:
        yaqin = min(progress, key=lambda g: abs(measured - progress[g]["expected"]))
        row.verdict = KromkaVerdict.NOMOS
        row.expected_mm = progress[yaqin]["expected"]
        row.delta_mm = round(measured - progress[yaqin]["expected"], 1)
        return
    row.verdict = KromkaVerdict.MOS if bosh else KromkaVerdict.ORTIQCHA
    row.side_group = group
    row.expected_mm = progress[group]["expected"]
    row.delta_mm = round(measured - progress[group]["expected"], 1)


async def _progress(db: AsyncSession, instance_id: int | None, part: Part | None) -> dict[str, dict[str, float]]:
    """Nusxaning guruh hisobi: kvota `Part.edges` dan, bajarilgani yopilgan o'lchovlardan."""
    if part is None or instance_id is None:
        return {}
    quota = edge_quota(part)
    if not quota:
        return {}
    done = await db.execute(
        select(KromkaMeasurement.side_group, func.count())
        .join(Scan, Scan.id == KromkaMeasurement.scan_id)
        .where(
            KromkaMeasurement.instance_id == instance_id,
            KromkaMeasurement.verdict == KromkaVerdict.MOS,
            KromkaMeasurement.is_deleted == False,  # noqa: E712
            # Skani BEKOR qilingan o'lchov kvotani band qilmaydi: brak tasdig'idan keyin
            # qayta lentalangan detalning yangi o'tishlari «ortiqcha» emas, «mos» bo'lsin
            Scan.is_cancelled == False,  # noqa: E712
        )
        .group_by(KromkaMeasurement.side_group)
    )
    for group, count in done.all():
        if group in quota:
            quota[group]["done"] = count
    return quota
