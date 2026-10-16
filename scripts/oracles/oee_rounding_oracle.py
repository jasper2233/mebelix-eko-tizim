"""OEE xom nisbatlardan, bitta yaxlitlash bilan hisoblanadi (docs/12 §4.25).

HAQIQIY `services/performance.oee_pct`. Kutilgan qiymat `fractions.Fraction` bilan ANIQ hisoblanadi
(A × P × Q, suzuvchi nuqtasiz) va `round()` qoidasi (yarmini juftga) bilan yaxlitlanadi. Ilgari 0.1 gacha yaxlitlangan uchta
foiz ko'paytirilardi — tasodifiy holatlarning ~13% ida natija 0.1 ga farq qilardi.

Yurgizish (DB kerak emas):
    cd backend && uv run python ../scripts/oracles/oee_rounding_oracle.py
"""

import random
from fractions import Fraction

from app.services.performance import oee_pct


def aniq(planned: int, run: int, ideal: int, parts: int, defects: int) -> float:
    oee = Fraction(run, planned) * Fraction(ideal, run) * Fraction(max(parts - defects, 0), parts) * 100
    # Loyihadagi hamma foiz `round()` — yarmini juftga; Fraction'da xuddi shu qoida, lekin xatosiz
    return float(round(oee * 10)) / 10


def eski(planned: int, run: int, ideal: int, parts: int, defects: int) -> float:
    a, p, q = (round(x, 1) for x in (run * 100 / planned, ideal * 100 / run, (parts - defects) * 100 / parts))
    return round(a * p * q / 10_000, 1)


natija: list[tuple[str, object, object]] = []
misol = (4600, 2504, 2439, 136, 27)
natija.append(("misol: aniq qiymat (eski kod 42.4 berardi)", oee_pct(*misol), aniq(*misol)))
natija.append(("misol: eski usul haqiqatan farq qilardi", eski(*misol) != aniq(*misol), True))

r = random.Random(7)
farq_yangi = farq_eski = teng = 0
for _ in range(100_000):
    planned = r.randint(3600, 30000)
    run = r.randint(1, planned)
    ideal = r.randint(1, run * 12 // 10)
    parts = r.randint(1, 300)
    d = r.randint(0, parts)
    kut = aniq(planned, run, ideal, parts, d)
    # Aniq .x5 tengligi (masalan 29.95) suzuvchi nuqtada 29.9499… bo'lib saqlanadi — bu har `round()`
    # ning xususiyati, OEE formulasiniki emas: bunday holatlar alohida sanaladi
    if (Fraction(ideal * max(parts - d, 0) * 1000, planned * parts)).denominator == 2:
        teng += 1
        continue
    farq_yangi += oee_pct(planned, run, ideal, parts, d) != kut
    farq_eski += eski(planned, run, ideal, parts, d) != kut
natija.append((f"100 000 tasodifiy holat ({teng} ta aniq .x5 tenglikdan tashqari): yangi usul aniq", farq_yangi, 0))
natija.append(("…eski usul esa ko'p holatda farq qilardi (> 5%)", farq_eski > 5000, True))

natija.append(("ish jadvali yo'q — None", oee_pct(0, 0, 100.0, 10, 0), None))
natija.append(("ishlamagan — None", oee_pct(28800, 0, 0.0, 10, 0), None))
natija.append(("Performance sanalmaydigan ish markazi — None", oee_pct(28800, 3600, None, 10, 0), None))
natija.append(("detal sanalmagan — None", oee_pct(28800, 3600, 100.0, 0, 0), None))
natija.append(("brak detaldan ko'p — 0, manfiy emas", oee_pct(28800, 3600, 1000.0, 5, 9), 0.0))

xato = sum(1 for _, a, b in natija if a != b)
for nom, a, b in natija:
    print(f"  {'OK ' if a == b else 'XATO'} {nom}: olingan={a} kutilgan={b}")
print(f"\nXULOSA: {len(natija) - xato}/{len(natija)} to'g'ri")
