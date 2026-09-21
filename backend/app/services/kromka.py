"""Kromka o'lchovini DETALGA bog'lash (`docs/12-oee.md` §4.10).

Model — KIRISH VAQTI: detal birinchi datchikka kirgan lahzaga eng yaqin skan.

2026-09-21 gacha «oxirgi skan» olinardi va bu prodda XATO berdi: detal D1 dan D2
gacha 8–15 soniya yuradi (2553 mm oraliq, 10 yoki 18 m/min), operator esa 4–10
soniyada bir marta skanerlaydi — ya'ni endi kelgan o'lchov 2–4 ta skan OLDINGI
detalniki. Har detal MES da ikki marta chiqardi: avval «mos emas», keyin «mos»
(stansiya egasining o'lchovi, `docs/onlayn_mes_hodisalar.md`).

Endi kirish lahzasi o'lchovdan hisoblanadi: `kirish = o'lchov vaqti − ish_ms`
(`ish_ms` — Pico bergan D1→D2 yurish vaqti). Nomzod skanlar shu lahza atrofidagi
oynadan olinadi (`kromka_bind_window_s`, sukut ±20 s) va ular orasidan O'LCHAMGA
mos keladigani tanlanadi: 289 mm o'lchov 700 mm lik detalga yozilib qolmasin.
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

#: 2026-09-20 gacha `nomos` o'lchov brak qaydini O'ZI ochardi. Tsexda datchik uzunlikka
#: qarab XATO o'lchayotgani aniqlandi — o'sha qaydlar soxta bo'lib chiqdi, shuning uchun
#: avtomatik brak O'CHIRILDI (`d4b8e1f37c92` eski qatorlarni tozalagan). Brak faqat
#: operator skandan keyin BRAK tugmasini bossa yoziladi. O'lchov hozircha KUZATUV:
#: hukmi ekranda ko'rinadi, hech narsani bloklamaydi va hech kimni ayblamaydi.
#: Datchik to'g'rilangach shu qator qaytariladi (docs/12 §4.10).
AUTO_DEFECT_REASON = "O'lcham mos emas"


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


async def _nomzodlar(db: AsyncSession, machine_id: int, kirish: datetime, window: timedelta) -> list[Scan]:
    """Kirish lahzasi atrofidagi bekor qilinmagan skanlar — eng yaqini birinchi.

    Oyna IKKI TOMONLAMA: operator detalni lentaga qo'ygandan KEYIN ham skanerlashi
    mumkin (chek qo'lida qoladi), shuning uchun kirishdan keyingi skan ham nomzod."""
    rows = (
        (
            await db.execute(
                select(Scan)
                .where(
                    Scan.machine_id == machine_id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                    Scan.created_at >= kirish - window,
                    Scan.created_at <= kirish + window,
                )
                .order_by(Scan.created_at)
            )
        )
        .scalars()
        .all()
    )
    return sorted(rows, key=lambda r: abs((r.created_at - kirish).total_seconds()))


def _kirish(at: datetime, payload: dict[str, Any]) -> datetime:
    """Detal BIRINCHI datchikka kirgan lahza: o'lchov vaqtidan yurish vaqti ayiriladi.

    `ish_ms` — Pico o'lchagan D1→D2 vaqti (millisekund). Bo'lmasa (eski proshivka
    yoki FAQAT1/FAQAT2) o'lchov vaqtining o'zi olinadi."""
    ish_ms = payload.get("ish_ms")
    if not isinstance(ish_ms, (int, float)) or isinstance(ish_ms, bool) or ish_ms <= 0:
        return at
    return at - timedelta(milliseconds=min(float(ish_ms), 120_000))


async def bind_measurement(
    db: AsyncSession,
    machine_id: int,
    at: datetime,
    payload: dict[str, Any],
    *,
    tolerance_mm: float,
    window: timedelta,
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
        tanlov = await _tanla(db, machine_id, kirish, window, float(measured), tolerance_mm)
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
    window: timedelta,
    measured: float,
    tol: float,
) -> tuple[Scan, dict[str, dict[str, float]]] | None:
    """Kirish lahzasi atrofidagi skanlardan SHU o'lchovga mos keladiganini tanlaydi.

    Tartib (stansiya egasining tavsiyasi, `docs/onlayn_mes_hodisalar.md` §5):
    1. o'lchamga mos va qirrasi hali yopilmagan skan — vaqt bo'yicha eng yaqini;
    2. o'lchamga mos, lekin kvotasi tugagani (takroriy o'tish);
    3. hech biri mos kelmasa — vaqt bo'yicha eng yaqini (hukmi `nomos` bo'ladi).
    Bo'sh oyna — `None`: bu brak emas, juftlash uchun ma'lumot yo'q."""
    ochiq: tuple[Scan, dict[str, dict[str, float]]] | None = None
    tugagan: tuple[Scan, dict[str, dict[str, float]]] | None = None
    birinchi: tuple[Scan, dict[str, dict[str, float]]] | None = None
    for scan in await _nomzodlar(db, machine_id, kirish, window):
        progress = await _progress(db, scan.instance_id, await db.get(Part, scan.part_id))
        if birinchi is None:
            birinchi = (scan, progress)
        mos = [g for g, sl in progress.items() if abs(measured - sl["expected"]) <= tol]
        if not mos:
            continue
        if ochiq is None and any(progress[g]["done"] < progress[g]["quota"] for g in mos):
            ochiq = (scan, progress)
            break  # eng yaqini va qirrasi ochiq — qidirishning ma'nosi yo'q
        if tugagan is None:
            tugagan = (scan, progress)
    return ochiq or tugagan or birinchi


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
        .where(
            KromkaMeasurement.instance_id == instance_id,
            KromkaMeasurement.verdict == KromkaVerdict.MOS,
            KromkaMeasurement.is_deleted == False,  # noqa: E712
        )
        .group_by(KromkaMeasurement.side_group)
    )
    for group, count in done.all():
        if group in quota:
            quota[group]["done"] = count
    return quota
