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

from app.schemas.settings import IdealCycle

# ponytail: koeffitsiyentlar POST bo'yicha bitta to'plam — Pico hozir faqat bitta Prisadkada.
# Boshqa tezlikdagi ikkinchi stanok paydo bo'lsa: sozlamani `machine_id -> IdealCycle` lug'atiga aylantirish.


def ideal_seconds(c: IdealCycle, bores: int, edge_bores: int, grooves: int, mills: int) -> float:
    """Bitta detalning ideal sikl vaqti, soniya."""
    return c.load_s + bores * c.bore_s + edge_bores * c.edge_bore_s + grooves * c.groove_s + mills * c.mill_s


def quality_pct(parts: int, defects: int) -> float | None:
    """OEE Quality: yaroqli detallar ulushi, foiz.

    Brak KIRITILMAGAN bo'lsa 100% — ayiriladigan narsa yo'q (egasining qarori, 2026-09-19).
    Detal umuman sanalmagan bo'lsa `None`: 0% «hammasi brak» degan yolg'on baho bo'lardi.
    Brak detaldan ko'p chiqsa (eski skan bugun brak qilinsa) 0 da to'xtaydi — manfiy foiz yo'q.
    """
    return round(max(parts - defects, 0) * 100 / parts, 1) if parts > 0 else None


def oee_pct(availability: float | None, performance: float | None, quality: float | None) -> float | None:
    """OEE = Availability × Performance × Quality (uchalasi ham foiz).

    Biri hisoblanmagan bo'lsa (ish jadvali yo'q, Prisadka emas, detal sanalmagan) — `None`.
    Nolga tenglashtirilmaydi: hisoblanmagan ko'rsatkich «yomon» degani emas.
    """
    if availability is None or performance is None or quality is None:
        return None
    return round(availability * performance * quality / 10_000, 1)
