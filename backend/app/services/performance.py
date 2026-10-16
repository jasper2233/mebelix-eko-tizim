"""OEE Performance — Prisadka uchun ideal sikl. Sof funksiya, DB yo'q.

    ideal vaqt (detal) = yuklash + yuza teshik × s + qirra teshik × s + paz × s + freza × s
    Performance        = Σ ideal vaqt (kuzatilgan ish vaqtida skanerlangan detallar) ÷ ishlagan vaqt

Bitta raqam EMAS, formula: prodda skanerlangan detalda teshiklar soni p10 = 2, p50 = 6, p90 = 15,
eng ko'pi 40 (2026-09-16 auditi) — bitta raqam bilan Performance operator tezligini emas, o'sha
kungi mahsulot aralashmasini o'lchardi. Ishlov soni `part.xnc_summary` dan (`giblab/ingest.py`).

Koeffitsiyentlarni admin Tizim sozlamalarida yuritadi (`schemas/settings.IdealCycle`, sukut
qiymatlar TAXMINIY — docs/12 §4.6). Skan↔sikl bog'lash kerak emas: yig'indi darajasida skanlar
(MES) va ishlagan vaqt (`services/availability.py`) yetadi.
"""

from app.schemas.settings import IdealCycle, IdealCycleKromka, IdealCycleRover

# ponytail: koeffitsiyentlar POST bo'yicha bitta to'plam — Pico hozir faqat bitta Prisadkada.
# Boshqa tezlikdagi ikkinchi stanok paydo bo'lsa: sozlamani `machine_id -> IdealCycle` lug'atiga aylantirish.


def ideal_seconds(c: IdealCycle, bores: int, edge_bores: int, grooves: int, mills: int) -> float:
    """Bitta detalning ideal sikl vaqti, soniya."""
    return c.load_s + bores * c.bore_s + edge_bores * c.edge_bore_s + grooves * c.groove_s + mills * c.mill_s


def kromka_ideal_seconds(c: IdealCycleKromka, length_mm: float | None, speed_m_min: float | None) -> float | None:
    """Kromkada bitta O'TISHNING ideal vaqti, soniya. O'lcham yoki tezlik yo'q bo'lsa `None`.

        ideal = L / v + oraliq        (v m/min dan mm/s ga: v * 1000 / 60)

    Detal necha qirrasi bo'lsa shuncha marta o'tadi — har o'tish alohida sanaladi, chunki
    stanok rostdan ham shuncha ish qilgan (Prisadkadagi «bitta detal = bitta sikl» emas).

    Nega Prisadkadagi kabi taxminiy koeffitsiyent kerak emas: kromkada mahsuldorlikni
    lenta tezligi belgilaydi, uzunlikni esa stansiya O'LCHAYDI — ya'ni ideal vaqt
    o'lchovdan chiqadi, taxmindan emas."""
    if not length_mm or not speed_m_min or length_mm <= 0 or speed_m_min <= 0:
        return None
    return length_mm / (speed_m_min * 1000.0 / 60.0) + c.gap_s


def rover_ideal_seconds(c: IdealCycleRover, length_mm: float | None, width_mm: float | None) -> float:
    """ROVER: bitta detalning ideal vaqti, soniya — `har detalga + perimetr (m) × metrga soniya`.

    Ish hajmi — kontur uzunligi; to'g'ri to'rtburchak perimetri uning pastki bahosi (egri
    kontur uzunroq — koeffitsiyent kalibrlashda buni o'ziga oladi). O'lcham yo'q bo'lsa
    faqat `load_s`: detal baribir ishlangan, uni Performance'dan tushirib qoldirmaymiz."""
    perimetr_m = 2 * ((length_mm or 0) + (width_mm or 0)) / 1000
    return c.load_s + perimetr_m * c.cut_s_per_m


def quality_pct(parts: int, defects: int) -> float | None:
    """OEE Quality: yaroqli detallar ulushi, foiz.

    Brak KIRITILMAGAN bo'lsa 100% — ayiriladigan narsa yo'q (egasining qarori, 2026-09-19).
    Detal umuman sanalmagan bo'lsa `None`: 0% «hammasi brak» degan yolg'on baho bo'lardi.
    Brak detaldan ko'p chiqsa (eski skan bugun brak qilinsa) 0 da to'xtaydi — manfiy foiz yo'q.
    """
    return round(max(parts - defects, 0) * 100 / parts, 1) if parts > 0 else None


def oee_pct(availability: float | None, performance: float | None, quality: float | None) -> float | None:
    """OEE = Availability × Performance × Quality (uchalasi ham foiz).

    Biri hisoblanmagan bo'lsa (ish jadvali yo'q, Prisadka ham, Kromka ham emas, detal sanalmagan) — `None`.
    Nolga tenglashtirilmaydi: hisoblanmagan ko'rsatkich «yomon» degani emas.
    """
    if availability is None or performance is None or quality is None:
        return None
    return round(availability * performance * quality / 10_000, 1)
