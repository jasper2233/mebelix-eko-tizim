"""Kromka o'lchovini DETALGA bog'lash (`docs/12-oee.md` §4.10).

Model — OXIRGI SKAN: operator detalni skanerlaydi, so'ng uni lentaga qo'yadi.
O'lchov kelganda shu ish markazidagi oxirgi skan (`kromka_bind_minutes` oynasi
ichida) o'sha detalni bildiradi. «Joriy detal» degan alohida holat saqlanmaydi:
terminal qulasa ham, agent qayta ulansa ham skan bazada turaveradi.

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


async def _last_scan(db: AsyncSession, machine_id: int, at: datetime, window: timedelta) -> Scan | None:
    """Shu stanokdagi oxirgi bekor qilinmagan skan — o'lchovdan oldingi oyna ichida."""
    return (
        await db.execute(
            select(Scan)
            .where(
                Scan.machine_id == machine_id,
                Scan.is_cancelled == False,  # noqa: E712
                Scan.is_deleted == False,  # noqa: E712
                Scan.created_at <= at,
                Scan.created_at >= at - window,
            )
            .order_by(Scan.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


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
        scan = await _last_scan(db, machine_id, at, window)
        if scan is None:
            row.verdict = KromkaVerdict.SKANERSIZ
        else:
            row.scan_id, row.instance_id, row.order_id = scan.id, scan.instance_id, scan.order_id
            part = await db.get(Part, scan.part_id)
            instance = await db.get(PartInstance, scan.instance_id)
            part_name, qr_text = (part.name if part else None), (instance.qr_text if instance else None)
            progress = await _progress(db, scan.instance_id, part)
            _judge(row, progress, float(measured), tolerance_mm)
            if row.verdict == KromkaVerdict.MOS and row.side_group:
                # Yangi qator hali yozilmagan — terminal ko'radigan hisobga qo'lda qo'shiladi
                progress[row.side_group]["done"] += 1

    db.add(row)
    return BindResult(row=row, progress=progress, scan_id=row.scan_id, part_name=part_name, qr_text=qr_text)


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
