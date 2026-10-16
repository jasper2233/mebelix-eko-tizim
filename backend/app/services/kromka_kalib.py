"""KROMKA stansiyasini kalibrlash hisobi — eng kichik kvadratlar (docs/12 §4.18, 2-qadam).

Stansiya egasining algoritmi (`jasper2233/kromka-stansiya-OYY: server/stansiya.html`, `gauss` …
`kalHisob`) QATORMA-QATOR ko'chirilgan: natija ular brauzerda hisoblagani bilan bir xil bo'lishi
SHART (`scripts/oracles/kromka_kalib_oracle.py` ikkalasini bir xil nuqtalarda solishtiradi).
O'zgartirmang — farq paydo bo'lsa, avval o'sha faylga qarang.

Model:   t_i    = (L + B_i)/v + k_i     B_i — datchikning UZUNLIK siljishi (nur kengligi), mm
                                        k_i — datchikning VAQT kechikishi, ms
         dt_mid = D/v + C               detal markazining D1 dan D2 gacha vaqti
Chiziqli shakl: L_ref·dt_mid = D·t_i − B_i·dt_mid − a_i + C·L_ref,   a_i = D·k_i − B_i·C
Noma'lumlar: D, B1, B2, a1, a2, C. Vaqtlar ms da.

Nuqtalar ODDIY `olchov` hodisalaridan olinadi (`d1`, `d2` — µs, `ish_ms` — D1→D2 old qirralar
orasi, ms; `v_nom` — 10/18): Pico ularni har o'lchovda yuboradi, ya'ni maxsus `KALIB` rejimi
kerak emas. `dt_mid = ish_ms + (t2 − t1)/2` — Pico'ning o'zi shunday hisoblaydi (`yakunla`).
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KromkaKalibSession


@dataclass(eq=False)  # `in` / `not in` — JS dagi kabi obyekt identifikatori bo'yicha
class Nuqta:
    """Bitta o'tish: etalon uzunligi va Pico vaqtlari (ms)."""

    i: int  # andon_event.id
    L_ref: float
    S: int  # nominal tezlik, m/min
    t1: float
    t2: float
    dtm: float
    # kalQoldiq natijalari
    v: float | None = None
    L1: float | None = None
    L2: float | None = None
    Lfit: float | None = None
    err: float | None = None
    dif: float | None = None
    chet: bool = False


@dataclass
class Model:
    D: float
    b1: float
    b2: float
    k1: float
    k2: float
    C: float
    m: int
    tur: dict[str, int] = field(default_factory=dict)


def nuqta(event_id: int, L_ref: float, payload: dict[str, Any]) -> Nuqta | None:
    """`olchov` hodisasidan nuqta (`kalTayyor` qoidasi). Yaroqsiz bo'lsa None."""

    def son(k: str) -> float:
        v = payload.get(k)
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0

    t1, t2, dt = son("d1") / 1000, son("d2") / 1000, son("ish_ms")
    dtm = dt + (t2 - t1) / 2 if (t1 > 0 and t2 > 0) else dt
    S = int(son("v_nom"))
    if not (L_ref > 0 and dtm > 0 and (t1 > 0 or t2 > 0)):
        return None
    return Nuqta(i=event_id, L_ref=L_ref, S=S, t1=t1, t2=t2, dtm=dtm)


def _gauss(A: list[list[float]], b: list[float]) -> list[float] | None:
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    nrm = 0.0
    for qator in A:
        for v in qator:
            nrm = max(nrm, abs(v))
    eps = 1e-12 * (nrm or 1)
    for c in range(n):
        p = c
        for r in range(c + 1, n):
            if abs(M[r][c]) > abs(M[p][c]):
                p = r
        if not math.isfinite(M[p][c]) or abs(M[p][c]) <= eps:
            return None
        M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r == c:
                continue
            f = M[r][c] / M[c][c]
            for k in range(c, n + 1):
                M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


def _lsq(rows: list[tuple[list[float], float]], m: int) -> list[float] | None:
    # Ustunlar kattaligi juda farq qiladi (t ~ 16000 ms, birlik ustun ~ 1) — har ustun o'z
    # o'rtacha kvadratiga bo'linadi, yechim oxirida qaytariladi (normal tenglamalar shartlanishi)
    sc = [0.0] * m
    for x, _y in rows:
        for i in range(m):
            sc[i] += x[i] * x[i]
    for i in range(m):
        sc[i] = math.sqrt(sc[i] / len(rows)) or 1.0
    A = [[0.0] * m for _ in range(m)]
    b = [0.0] * m
    for x, y in rows:
        for i in range(m):
            xi = x[i] / sc[i]
            b[i] += xi * y
            for j in range(m):
                A[i][j] += xi * x[j] / sc[j]
    s = _gauss(A, b)
    return [v / sc[i] for i, v in enumerate(s)] if s else None


def _ortacha(a: list[float]) -> float | None:
    return sum(a) / len(a) if a else None


def _kv_ort(a: list[float], dof: int = 0) -> float | None:
    return math.sqrt(sum(x * x for x in a) / max(1, len(a) - dof)) if a else None


def _fit(pts: list[Nuqta], B: bool = False, K: bool = False, C: bool = False) -> Model | None:
    """`kalFit`: ustunlar 0 D · 1 B1 · 2 B2 · 3 a1 · 4 a2 · 5 C."""
    ust = [0] + ([1, 2] if B else []) + ([3, 4] if K else []) + ([5] if C else [])
    m = len(ust)
    rows: list[tuple[list[float], float]] = []
    for p in pts:
        y = p.L_ref * p.dtm
        if p.t1 > 0:
            x = [p.t1, -p.dtm, 0.0, -1.0, 0.0, p.L_ref]
            rows.append(([x[j] for j in ust], y))
        if p.t2 > 0:
            x = [p.t2, 0.0, -p.dtm, 0.0, -1.0, p.L_ref]
            rows.append(([x[j] for j in ust], y))
    if len(rows) < m + 2:
        return None
    s = _lsq(rows, m)
    if not s or not all(math.isfinite(v) for v in s):
        return None
    q = [0.0] * 6
    for i, j in enumerate(ust):
        q[j] = s[i]
    D, b1, b2, Cc = q[0], q[1], q[2], q[5]
    if not D > 0:
        return None
    k1, k2 = (q[3] + b1 * Cc) / D, (q[4] + b2 * Cc) / D
    if not (math.isfinite(k1) and math.isfinite(k2)):
        return None
    # Fizik chegara: B — nur kengligi, bir necha mm; k va C — javob kechikishi, bir necha ms.
    # Bundan chiqsa — yechim shovqinga moslashib ketgan, soddaroq model ishonchliroq.
    if abs(b1) > 30 or abs(b2) > 30 or abs(k1) > 5 or abs(k2) > 5 or abs(Cc) > 10:
        return None
    tur = {k: 1 for k, on in (("B", B), ("K", K), ("C", C)) if on}
    return Model(D=D, b1=b1, b2=b2, k1=k1, k2=k2, C=Cc, m=m, tur=tur)


def _zaxira(pts: list[Nuqta]) -> Model:
    """`kalZaxira`: 1 xil uzunlik — faqat D."""
    v: list[float] = []
    for p in pts:
        if p.t1 > 0:
            v.append(p.L_ref * p.dtm / p.t1)
        if p.t2 > 0:
            v.append(p.L_ref * p.dtm / p.t2)
    return Model(D=_ortacha(v) or 0.0, b1=0.0, b2=0.0, k1=0.0, k2=0.0, C=0.0, m=1)


def _qoldiq(pts: list[Nuqta], f: Model) -> None:
    """`kalQoldiq`: har nuqtaning shu model bo'yicha uzunligi va xatosi (joyida yozadi)."""
    for p in pts:
        dv = p.dtm - f.C
        p.v = f.D / dv if dv > 0 else None
        p.L1 = p.v * (p.t1 - f.k1) - f.b1 if (p.t1 > 0 and p.v) else None
        p.L2 = p.v * (p.t2 - f.k2) - f.b2 if (p.t2 > 0 and p.v) else None
        a = [x for x in (p.L1, p.L2) if x is not None]
        p.Lfit = _ortacha(a)
        p.err = p.Lfit - p.L_ref if p.Lfit is not None else None
        p.dif = p.L1 - p.L2 if (p.L1 is not None and p.L2 is not None) else None


def _sd(pts: list[Nuqta], f: Model) -> float:
    _qoldiq(pts, f)
    return _kv_ort([p.err for p in pts if p.err is not None], f.m) or 0.0


def _model(pts: list[Nuqta], n_lens: int, n_tez: int) -> Model:
    """`kalModel`: ma'lumot nimaga yetsa — o'sha model."""
    if n_lens < 2:
        return _zaxira(pts)
    if n_tez < 2:
        return _fit(pts, B=True) or _zaxira(pts)
    asos = _fit(pts, B=True, C=True) or _fit(pts, B=True)
    if not asos:
        return _zaxira(pts)
    # K1/K2 faqat qoldiq tarqoqligini kamida 10% kamaytirsa qo'shiladi
    toliq = _fit(pts, B=True, C=True, K=True)
    if toliq and _sd(pts, toliq) < 0.9 * _sd(pts, asos):
        return toliq
    return asos


def hisobla(hammasi: list[Nuqta]) -> dict[str, Any] | None:
    """`kalHisob`: model, 3σ dan chetdagilarni tashlash (3 marta), statistikalar, guruhlar."""
    if not hammasi:
        return None
    lens = sorted({p.L_ref for p in hammasi})
    tezliklar = sorted({p.S for p in hammasi})
    ish = list(hammasi)
    chet: list[Nuqta] = []
    f = _zaxira(ish)  # mypy uchun; sikl kamida bir marta yuradi
    for it in range(3):
        f = _model(ish, len(lens), len(tezliklar))
        _qoldiq(ish, f)
        e = [p.err for p in ish if p.err is not None]
        if it == 2 or len(e) <= f.m + 3:
            break
        sd = _kv_ort(e, f.m) or 0.0
        cheg = max(3 * sd, 0.5)  # 0.5 mm pastki chegara — yaxshi nuqtani tashlamaslik uchun
        qoldi = [p for p in ish if p.err is None or abs(p.err) <= cheg]
        if len(qoldi) == len(ish) or len(qoldi) < f.m + 3:
            break
        chet += [p for p in ish if p not in qoldi]
        ish = qoldi
    _qoldiq(hammasi, f)  # jadvalda hamma nuqta ko'rinsin
    for p in chet:
        p.chet = True

    e = [p.err for p in ish if p.err is not None]
    sd = _kv_ort(e, f.m) or 0.0
    max_err = max((abs(x) for x in e), default=0.0)
    difs = [p.dif for p in ish if p.dif is not None]
    dif_ort = _ortacha(difs)
    dif_sd = _kv_ort([x - (dif_ort or 0.0) for x in difs], 1) if len(difs) > 1 else None
    sd_dat = dif_sd / 2 if dif_sd is not None else None
    sd_tez = math.sqrt(max(0.0, sd * sd - sd_dat * sd_dat)) if sd_dat is not None else None
    v10 = [p.v * 60 for p in ish if p.S == 10 and p.v]
    v18 = [p.v * 60 for p in ish if p.S == 18 and p.v]

    guruh: dict[tuple[float, int], list[float]] = {}
    for p in ish:
        if p.Lfit is not None:
            guruh.setdefault((p.L_ref, p.S), []).append(p.Lfit)
    grp = []
    for (L_ref, S), v in sorted(guruh.items()):
        mean = _ortacha(v) or 0.0
        grp.append(
            {
                "L_ref": L_ref,
                "S": S,
                "n": len(v),
                "mean": mean,
                "sd": _kv_ort([x - mean for x in v], 1) if len(v) > 1 else None,
            }
        )

    kam = []
    if len(lens) < 2:
        kam.append("B1/B2 uchun kamida 2 xil uzunlik kerak — hozircha faqat D")
    if len(tezliklar) < 2:
        kam.append("C va K uchun ikkala tezlik (10 va 18) kerak")
    if len(ish) < 20:
        kam.append(f"nuqta kam ({len(ish)}) — reja bo'yicha 40 ta")
    # 1 xil uzunlikda D aynan shu nuqtalarga moslanadi — xato o'z-o'zidan kichik chiqadi
    if kam:
        hukm = ("w", f"±{2 * sd:.2f} mm — DASTLABKI, ma'lumot yetarli emas")
    elif 2 * sd <= 0.5:
        hukm = ("ok", "±0.5 mm — MAQSADGA YETILDI")
    elif 2 * sd <= 1:
        hukm = ("w", f"±{2 * sd:.2f} mm — 0.5 mm ga yetmadi")
    else:
        hukm = ("w", f"±{2 * sd:.2f} mm — tarqoqlik katta")
    # Datchik farqi chegarasi L1−L2 ning haqiqiy tarqalishidan: doimiy siljish + 4σ
    td_tavsiya = max(1.0, math.ceil((abs(dif_ort or 0.0) + 4 * dif_sd) * 2) / 2) if dif_sd is not None else None

    return {
        "D": f.D,
        "B1": f.b1,
        "B2": f.b2,
        "K1": f.k1,
        "K2": f.k2,
        "C": f.C,
        "tur": f.tur,
        "V10": _ortacha(v10),
        "V18": _ortacha(v18),
        "n10": len(v10),
        "n18": len(v18),
        "n_lens": len(lens),
        "n_tez": len(tezliklar),
        "n_ish": len(ish),
        "n_chet": len(chet),
        "sd": sd,
        "sd2": 2 * sd,
        "max_err": max_err,
        "sd_dat": sd_dat,
        "sd_tez": sd_tez,
        "dif_ort": dif_ort,
        "dif_sd": dif_sd,
        "grp": grp,
        "kam": kam,
        "hukm": hukm,
        "td_tavsiya": td_tavsiya,
        "dopusk_tavsiya": max(0.5, math.ceil(2 * sd * 2) / 2),
        # 1 uzunlikda faqat D — qo'llash erta (3-qadamdagi tugma shu shartga bo'ysunadi)
        "qollasa_boladi": len(lens) >= 2,
    }


def etalon(segments: list[dict[str, Any]], at: datetime) -> float | None:
    """Hodisa vaqtida qaysi etalon o'tayotgan edi — `at` dan oldin boshlangan OXIRGI bo'lak."""
    L = None
    for s in segments:
        if datetime.fromisoformat(s["dan"]) <= at:
            L = float(s["L_ref"])
    return L


async def kalib_oraliqlar(db: AsyncSession, machine_id: int) -> list[tuple[datetime, datetime | None]]:
    """Stanokning hamma kalibrlash oraliqlari: shu vaqtdagi `olchov` skanga bog'lanmaydi."""
    rows = await db.execute(
        select(KromkaKalibSession.started_at, KromkaKalibSession.ended_at).where(
            KromkaKalibSession.machine_id == machine_id,
            KromkaKalibSession.is_deleted == False,  # noqa: E712
        )
    )
    return [(a, b) for a, b in rows.tuples().all()]


def ichida(oraliqlar: list[tuple[datetime, datetime | None]], at: datetime) -> bool:
    return any(a <= at and (b is None or at <= b) for a, b in oraliqlar)
