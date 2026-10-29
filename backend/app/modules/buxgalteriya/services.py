"""Buxgalteriya (EKO 7): avtomatik provodkalar, aylanma-saldo vedomosti, schyot kartochkasi, nazorat.

AVTOMATIK PROVODKA = manba jurnallaridan hisoblangan «bo'lishi kerak» holat:
  kassa orderi (storno ham)      D hisob (5010/5710/5110)  K 4010 mijoz / 9390 ...   yoki  D 9420/6010/4010 K hisob
  ombor harakati (qiymat ±)      D 1010  K 6010 kirim / 9120 sotuv / 2010 sarf / 2510 sex / 9390–9430 tuzatish
  buyurtma yetkazildi            D 4010  K 9010 summa;  D 9110 K 2010 tannarx (sarf − qaytish)
  do'kon sotuvi                  D 4010  K 9020 summa (storno — teskari)
  oy soliqi                      D 9010 / 9020 K 6410 sotuv QQS;  D 9810 K 6410 aylanma soliq
  boshlang'ich qoldiqlar         D 5010.. / 1010  K 8710;  kassagacha avans  D 8710 K 4010
Sinxron har manba guruhi (va subkonto) bo'yicha «bo'lishi kerak − yozilgan» farqni yozadi: takror ishlasa
hech narsa qo'shilmaydi; manba o'zgarsa (buyurtma summasi, bekor qilish, qoida) tuzatish provodkasi tushadi.
Yopilgan oyga yozilmaydi — tuzatish joriy sanada. Schyotlar — BHMS 21 asosida; qoidalarni buxgalter tahrirlaydi.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import TASHKENT_TZ
from app.models import Order
from app.models.enums import OrderStatus
from app.modules.buxgalteriya.models import BuxQoida, BuxSchyot, BuxYozuv
from app.modules.kassa import service as kassa
from app.modules.moliya import service as moliya
from app.modules.ombor import service as ombor
from app.modules.soliq import service as soliq

_0 = Decimal(0)
_Q = Decimal("0.01")
OCHILISH = "8710"  # boshlang'ich qoldiqlar qarshisi (taqsimlanmagan foyda)
#: Ombor harakati turi → 1010 qarshisidagi schyot
HARAKAT = {"kirim": "6010", "chiqim": "9120", "sex": "2510", "sarf": "2010", "qaytish": "2010", "sex_farq": "2510"}


class BuxXato(Exception):
    def __init__(self, xatolar: list[str]) -> None:
        super().__init__(" · ".join(xatolar))
        self.xatolar = xatolar


def bugun() -> date:
    return datetime.now(TASHKENT_TZ).date()


def _mahalliy(dt: datetime) -> date:
    return dt.astimezone(TASHKENT_TZ).date()


def keyingi_oy(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def _nom(s: str) -> str:
    return " ".join(s.split())[:150]


@dataclass
class Maqsad:
    guruh: str
    sana: date
    debet: str
    kredit: str
    summa: Decimal
    izoh: str
    client_id: int | None = None
    kontragent: str = ""


async def qoidalar(db: AsyncSession) -> dict[str, str]:
    return {q.kalit: q.schyot for q in (await db.execute(select(BuxQoida))).scalars()}


# ───────────────────────── «bo'lishi kerak» ─────────────────────────
async def _kassa(db: AsyncSession, q: dict[str, str], today: date) -> list[Maqsad]:
    def hisob(kod: str) -> str:
        return q.get(f"hisob:{kod}", "5010")

    out: list[Maqsad] = []
    rows = await kassa.orderlar_davr(db)
    birinchi = min((_mahalliy(o.sana) for o in rows), default=today)
    for hs, _qoldiq in await kassa.hisoblar(db):
        if hs.boshlangich:
            izoh = f"{hs.nom}: boshlang'ich"
            out.append(Maqsad(f"hisob:{hs.kod}", birinchi, hisob(hs.kod), OCHILISH, hs.boshlangich, izoh))
    otk: dict[str, dict[str, Any]] = defaultdict(lambda: {"ga": "", "dan": "", "summa": _0, "sana": today})
    chiqim = {"komissiya": "komissiya", "inkassatsiya": "inkassatsiya", "farq": "farq:kamomad"}
    for o in rows:
        s, d, H = o.summa, _mahalliy(o.sana), hisob(o.hisob)
        izoh = f"{o.no} · {o.kontragent or o.maqsad}"
        g = f"ko:{o.id}"
        kontr = _nom(o.kontragent)
        if o.maqsad == "otkazma":
            leg = otk[o.guruh or o.no]
            if o.tur == "kirim":
                leg["ga"], leg["summa"], leg["sana"] = H, leg["summa"] + s, d
            else:
                leg["dan"] = H
        elif o.tur == "kirim" and o.maqsad in ("avans", "tolov", "qarz", "sotuv"):
            out.append(Maqsad(g, d, H, "4010", s, izoh, o.client_id, kontr))
        elif o.tur == "kirim":
            out.append(
                Maqsad(g, d, H, q.get("farq:ortiqcha" if o.maqsad == "farq" else "kirim:boshqa", "9390"), s, izoh)
            )
        elif o.maqsad == "xarajat":
            out.append(Maqsad(g, d, q.get(f"xarajat:{o.turkum}", q.get("xarajat:*", "9420")), H, s, izoh))
        elif o.maqsad == "taminotchi":
            out.append(Maqsad(g, d, "6010", H, s, izoh, None, kontr))
        elif o.maqsad == "qaytarish":
            out.append(Maqsad(g, d, "4010", H, s, izoh, o.client_id, kontr))
        else:
            out.append(Maqsad(g, d, q.get(chiqim.get(o.maqsad, "chiqim:boshqa"), "9430"), H, s, izoh))
    for r in await kassa.ochilishlar(db):
        izoh = f"Ochilish qoldig'i · {r.kontragent}" + (f" · {r.izoh}" if r.izoh else "")
        if r.tur == "mijoz":
            out.append(Maqsad(f"och:{r.id}", r.sana, "4010", OCHILISH, r.summa, izoh, r.client_id, _nom(r.kontragent)))
        else:
            out.append(Maqsad(f"och:{r.id}", r.sana, OCHILISH, "6010", r.summa, izoh, None, _nom(r.kontragent)))
    for guruh, leg in otk.items():
        if leg["ga"] and leg["dan"]:
            out.append(Maqsad(f"otk:{guruh}", leg["sana"], leg["ga"], leg["dan"], leg["summa"], f"O'tkazma {guruh}"))
    return out


async def _buyurtmalar(db: AsyncSession) -> list[Maqsad]:
    out: list[Maqsad] = []
    orders = list(
        (
            await db.execute(
                select(Order).where(
                    Order.status != OrderStatus.CANCELLED,
                    Order.is_deleted == False,  # noqa: E712
                    Order.amount.is_not(None),
                )
            )
        ).scalars()
    )
    tan = await ombor.buyurtma_tannarxi(db, [o.id for o in orders if o.delivered_at is not None])
    for o in orders:
        if o.advance_payment:
            izoh = f"{o.number}: kassagacha to'lov"
            out.append(
                Maqsad(
                    f"order0:{o.id}", _mahalliy(o.created_at), OCHILISH, "4010", o.advance_payment, izoh, o.client_id
                )
            )
        if o.delivered_at is not None:
            d, g = _mahalliy(o.delivered_at), f"order:{o.id}"
            out.append(Maqsad(g, d, "4010", "9010", o.amount or _0, f"{o.number}: yetkazildi", o.client_id))
            if tan.get(o.id):
                out.append(Maqsad(g, d, "9110", "2010", tan[o.id], f"{o.number}: tannarx"))
    return out


async def _ombor(db: AsyncSession, today: date) -> list[Maqsad]:
    out: list[Maqsad] = []
    harakat = await ombor.bux_harakatlar(db)
    bq = await ombor.boshlangich_qiymat(db)
    if bq:
        d0 = min((_mahalliy(h.sana) for h in harakat), default=today)
        out.append(Maqsad("ombor:boshlangich", d0, "1010", OCHILISH, bq, "Ombor: boshlang'ich qoldiq"))
    for h in harakat:
        if h.kind in ("inv", "tuzatish"):
            k = OCHILISH if "Boshlang'ich" in h.note else ("9390" if h.qiymat > 0 else "9430")
        else:
            k = HARAKAT.get((h.doc_kind or "") if h.kind == "storno" else h.kind, "9430")
        izoh = f"Ombor: {h.kind} {h.note}"[:300]
        out.append(
            Maqsad(
                f"sm:{h.id}",
                _mahalliy(h.sana),
                "1010",
                k,
                h.qiymat,
                izoh,
                None,
                _nom(h.kontragent) if k == "6010" else "",
            )
        )
    for hj in await ombor.sotuv_hujjatlari(db):
        izoh = f"{hj.no}: do'kon sotuvi"
        out.append(Maqsad(f"doc:{hj.id}", hj.sana, "4010", "9020", hj.summa, izoh, None, _nom(hj.kontragent)))
    return out


async def _soliqlar(db: AsyncSession, today: date) -> list[Maqsad]:
    out: list[Maqsad] = []
    boshi = await soliq.rejim_boshi(db)
    if boshi is None:
        return out
    oy = boshi.replace(day=1)
    while oy <= today:
        t = await soliq.oy_soliq(db, oy)
        sana = min(keyingi_oy(oy) - timedelta(days=1), today)
        g = f"oy:{oy:%Y-%m}"
        out.append(Maqsad(g, sana, "9010", "6410", t.buyurtma_qqs, f"{oy:%Y-%m}: buyurtmalar QQS i"))
        out.append(Maqsad(g, sana, "9020", "6410", t.dokon_qqs, f"{oy:%Y-%m}: do'kon QQS i"))
        out.append(Maqsad(g, sana, "9810", "6410", t.aylanma_soliq, f"{oy:%Y-%m}: aylanmadan soliq"))
        oy = keyingi_oy(oy)
    return out


async def maqsadlar(db: AsyncSession) -> list[Maqsad]:
    """Manba jurnallaridan «bo'lishi kerak» provodkalar (modul hujjati boshida jadval)."""
    q = await qoidalar(db)
    today = bugun()
    out = await _kassa(db, q, today) + await _buyurtmalar(db) + await _ombor(db, today) + await _soliqlar(db, today)
    return [x for x in out if x.summa != 0]


# ───────────────────────── sinxron ─────────────────────────
Kalit = tuple[str, str, str, int | None, str]


def _kalit(
    guruh: str, debet: str, kredit: str, client_id: int | None, kontr: str, summa: Decimal
) -> tuple[Kalit, Decimal]:
    """Juftlik tartibi bir xil (kichik kod birinchi), summa shu tartibga nisbatan ishorali."""
    if debet <= kredit:
        return (guruh, debet, kredit, client_id, kontr), summa
    return (guruh, kredit, debet, client_id, kontr), -summa


@dataclass
class Sinxron:
    yozildi: int
    tuzatish: int


async def sinxron(db: AsyncSession) -> Sinxron:
    """Avtomatik provodkalarni manbalarga moslaydi. Chaqiruvchi `commit` qiladi."""
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext("bux_sinxron"))))
    kerak: dict[Kalit, Decimal] = defaultdict(lambda: _0)
    meta: dict[Kalit, Maqsad] = {}
    for m in await maqsadlar(db):
        k, s = _kalit(m.guruh, m.debet, m.kredit, m.client_id, m.kontragent, m.summa)
        kerak[k] += s
        meta.setdefault(k, m)
    bor: dict[Kalit, Decimal] = defaultdict(lambda: _0)
    rows = await db.execute(
        select(
            BuxYozuv.guruh,
            BuxYozuv.debet,
            BuxYozuv.kredit,
            BuxYozuv.client_id,
            BuxYozuv.kontragent,
            func.sum(BuxYozuv.summa),
        )
        .where(BuxYozuv.guruh.is_not(None))
        .group_by(BuxYozuv.guruh, BuxYozuv.debet, BuxYozuv.kredit, BuxYozuv.client_id, BuxYozuv.kontragent)
    )
    for g, d, kr, cid, kontr, s in rows.all():
        k, v = _kalit(g, d, kr, cid, kontr, Decimal(s))
        bor[k] += v
    today = bugun()
    yopiq: dict[date, bool] = {}
    n = Sinxron(0, 0)
    for k in set(kerak) | set(bor):
        farq = (kerak.get(k, _0) - bor.get(k, _0)).quantize(_Q)
        if farq == 0:
            continue
        guruh, a, b, cid, kontr = k
        mq = meta.get(k)
        sana = mq.sana if mq is not None else today
        oy = sana.replace(day=1)
        if oy not in yopiq:
            yopiq[oy] = await moliya.davr_yopiq(db, sana)
        if yopiq[oy]:
            sana = today
        tuzatish = k in bor
        db.add(
            BuxYozuv(
                sana=sana,
                debet=a if farq > 0 else b,
                kredit=b if farq > 0 else a,
                summa=abs(farq),
                izoh=(
                    ("Tuzatish: " if tuzatish else "")
                    + (mq.izoh if mq else f"{guruh}: manba o'zgardi — qayta tasniflash")
                )[:300],
                guruh=guruh,
                client_id=cid,
                kontragent=kontr,
            )
        )
        n.tuzatish += tuzatish
        n.yozildi += 1
    await db.flush()
    return n


# ───────────────────────── qo'lda provodka ─────────────────────────
async def _schyot(db: AsyncSession, kod: str) -> BuxSchyot:
    s = (await db.execute(select(BuxSchyot).where(BuxSchyot.kod == kod, BuxSchyot.faol == True))).scalar_one_or_none()  # noqa: E712
    if s is None:
        raise BuxXato([f"{kod} schyoti yo'q yoki o'chirilgan"])
    return s


async def qolda(
    db: AsyncSession,
    *,
    sana: date,
    debet: str,
    kredit: str,
    summa: Decimal,
    izoh: str,
    user_id: int | None,
    client_id: int | None = None,
    kontragent: str = "",
) -> BuxYozuv:
    """Qo'lda provodka (ish haqi hisoblash, asosiy vosita, ...)."""
    xato = []
    if debet == kredit:
        xato.append("Debet va kredit bir xil")
    if summa <= 0:
        xato.append("Summa musbat bo'lsin")
    if not izoh.strip():
        xato.append("Mazmunini yozing")
    if await moliya.davr_yopiq(db, sana):
        xato.append(f"{sana:%Y-%m} oyi yopilgan")
    for kod in (debet, kredit):
        try:
            await _schyot(db, kod)
        except BuxXato as e:
            xato += e.xatolar
    if xato:
        raise BuxXato(xato)
    y = BuxYozuv(
        sana=sana,
        debet=debet,
        kredit=kredit,
        summa=summa,
        izoh=izoh.strip()[:300],
        client_id=client_id,
        kontragent=_nom(kontragent),
        yozgan_id=user_id,
    )
    db.add(y)
    await db.flush()
    return y


async def storno(db: AsyncSession, yozuv_id: int, user_id: int | None, sabab: str) -> BuxYozuv:
    """Qo'lda provodkani teskari provodka bilan bekor qiladi (ikki kalit). Avtomatik provodka manbada tuzatiladi."""
    y = await db.get(BuxYozuv, yozuv_id, with_for_update=True)
    xato = []
    if y is None:
        raise BuxXato(["Provodka topilmadi"])
    if y.guruh is not None:
        xato.append("Avtomatik provodka — manba hujjatida tuzatiladi (sinxron o'zi to'g'rilaydi)")
    if y.storno_of_id is not None:
        xato.append("Bu o'zi storno provodkasi")
    if await db.scalar(select(BuxYozuv.id).where(BuxYozuv.storno_of_id == yozuv_id)) is not None:
        xato.append("Allaqachon storno qilingan")
    if user_id is not None and user_id == y.yozgan_id:
        xato.append("Ikki kalit qoidasi: provodkani yozgan xodim o'zi storno qilolmaydi")
    if not sabab.strip():
        xato.append("Sababini yozing")
    if xato:
        raise BuxXato(xato)
    s = BuxYozuv(
        sana=bugun(),
        debet=y.kredit,
        kredit=y.debet,
        summa=y.summa,
        izoh=f"Storno #{y.id}: {sabab.strip()}"[:300],
        client_id=y.client_id,
        kontragent=y.kontragent,
        yozgan_id=user_id,
        storno_of_id=y.id,
    )
    db.add(s)
    await db.flush()
    return s


# ───────────────────────── hisobotlar ─────────────────────────
@dataclass
class SaldoQator:
    kod: str
    nom: str
    tur: str
    bosh_d: Decimal
    bosh_k: Decimal
    ayl_d: Decimal
    ayl_k: Decimal
    yak_d: Decimal
    yak_k: Decimal


def _tomon(tur: str, saldo: Decimal, subkonto: list[Decimal] | None) -> tuple[Decimal, Decimal]:
    """Saldo debet/kredit tomoni: subkonto bo'lsa — kengaytirilgan (har mijoz alohida)."""
    if subkonto is not None:
        return sum((x for x in subkonto if x > 0), _0), -sum((x for x in subkonto if x < 0), _0)
    return (saldo, _0) if saldo >= 0 else (_0, -saldo)


async def _subkonto(db: AsyncSession, kod: str, gacha: date) -> list[Decimal]:
    """4010 / 6010 saldolari mijoz (kontragent) bo'yicha `gacha` dan oldin."""
    rows = (
        await db.execute(
            select(BuxYozuv.debet, BuxYozuv.client_id, BuxYozuv.kontragent, func.sum(BuxYozuv.summa))
            .where(BuxYozuv.sana < gacha, (BuxYozuv.debet == kod) | (BuxYozuv.kredit == kod))
            .group_by(BuxYozuv.debet, BuxYozuv.client_id, BuxYozuv.kontragent)
        )
    ).all()
    by: dict[Any, Decimal] = defaultdict(lambda: _0)
    for d, cid, kontr, s in rows:
        key = cid if cid is not None else kontr.casefold()
        by[key] += Decimal(s) if d == kod else -Decimal(s)
    return list(by.values())


async def _qoldiqlar(db: AsyncSession, gacha: date, dan: date | None = None) -> dict[str, tuple[Decimal, Decimal]]:
    """Schyot bo'yicha (debet aylanma, kredit aylanma) [dan, gacha) oralig'ida."""
    out: dict[str, list[Decimal]] = defaultdict(lambda: [_0, _0])
    for col, i in ((BuxYozuv.debet, 0), (BuxYozuv.kredit, 1)):
        q = select(col, func.sum(BuxYozuv.summa)).where(BuxYozuv.sana < gacha).group_by(col)
        if dan is not None:
            q = q.where(BuxYozuv.sana >= dan)
        for kod, s in (await db.execute(q)).all():
            out[kod][i] += Decimal(s)
    return {k: (v[0], v[1]) for k, v in out.items()}


SUBKONTO = ("4010", "6010")


async def aylanma_saldo(db: AsyncSession, dan: date, gacha: date) -> list[SaldoQator]:
    """[dan, gacha] kunlar. Har schyot: boshlang'ich saldo, aylanma, yakuniy saldo (D / K)."""
    oxir = gacha + timedelta(days=1)
    bosh = await _qoldiqlar(db, dan)
    ayl = await _qoldiqlar(db, oxir, dan)
    sch = {s.kod: s for s in (await db.execute(select(BuxSchyot).order_by(BuxSchyot.kod))).scalars()}
    out = []
    for kod in sorted(set(sch) | set(bosh) | set(ayl)):
        b = bosh.get(kod, (_0, _0))
        a = ayl.get(kod, (_0, _0))
        if b == (_0, _0) and a == (_0, _0):
            continue
        s = sch.get(kod)
        bs = b[0] - b[1]
        ys = bs + a[0] - a[1]
        bd, bk = _tomon(s.tur if s else "AP", bs, await _subkonto(db, kod, dan) if kod in SUBKONTO else None)
        yd, yk = _tomon(s.tur if s else "AP", ys, await _subkonto(db, kod, oxir) if kod in SUBKONTO else None)
        out.append(SaldoQator(kod, s.nom if s else "(rejada yo'q)", s.tur if s else "AP", bd, bk, a[0], a[1], yd, yk))
    return out


async def saldo(db: AsyncSession, kod: str, gacha: date | None = None) -> Decimal:
    """Schyot saldosi (debet − kredit) `gacha` kuni oxirigacha."""
    oxir = (gacha or bugun()) + timedelta(days=1)
    d, k = (await _qoldiqlar(db, oxir)).get(kod, (_0, _0))
    return d - k


async def kartochka(db: AsyncSession, kod: str, dan: date, gacha: date) -> tuple[Decimal, list[BuxYozuv]]:
    bosh = (await _qoldiqlar(db, dan)).get(kod, (_0, _0))
    rows = list(
        (
            await db.execute(
                select(BuxYozuv)
                .where((BuxYozuv.debet == kod) | (BuxYozuv.kredit == kod), BuxYozuv.sana >= dan, BuxYozuv.sana <= gacha)
                # Bir kun ichida boshlang'ich qoldiq (… — 8710) birinchi: oraliq saldo manfiyga tushib ko'rinmasin
                .order_by(
                    BuxYozuv.sana,
                    case((literal(OCHILISH).in_((BuxYozuv.debet, BuxYozuv.kredit)), 0), else_=1),
                    BuxYozuv.id,
                )
            )
        ).scalars()
    )
    return bosh[0] - bosh[1], rows


@dataclass
class Nazorat:
    nom: str
    buxgalteriya: Decimal
    manba: Decimal
    izoh: str

    @property
    def farq(self) -> Decimal:
        return self.buxgalteriya - self.manba


async def nazorat(db: AsyncSession) -> list[Nazorat]:
    """Buxgalteriya schyotlari modullardagi raqamlar bilan mosmi (bugun holatiga)."""
    q = await qoidalar(db)
    hisob = {h.kod: qol for h, qol in await kassa.hisoblar(db)}
    out = [
        Nazorat(
            f"{q.get(f'hisob:{k}', '?')} — {nom}",
            await saldo(db, q.get(f"hisob:{k}", "")),
            hisob.get(k, _0),
            f"Kassa: {nom}",
        )
        for k, nom in (("naqd", "naqd kassa"), ("karta", "karta terminali"), ("bank", "bank hisobi"))
    ]
    out.append(Nazorat("1010 — ombor", await saldo(db, "1010"), await ombor.ombor_qiymati(db), "Ombor qiymati (FIFO)"))
    out.append(
        Nazorat(
            "4010 — mijozlar (qarz − avans)",
            await saldo(db, "4010"),
            await moliya.debitorlik_net(db),
            "Moliya: debitorlar",
        )
    )
    out.append(
        Nazorat(
            "6010 — ta'minotchilar (qarz − avans)",
            -await saldo(db, "6010"),
            await moliya.kreditorlik_net(db),
            "Moliya: kreditorlar",
        )
    )
    jami = Decimal(await db.scalar(select(func.coalesce(func.sum(BuxYozuv.summa), 0))) or 0)
    out.append(Nazorat("Debet aylanmasi = Kredit aylanmasi", jami, jami, "har provodka ikki tomonli"))
    return out


async def oy_natija(db: AsyncSession, oy: date) -> Decimal:
    """Oyning moliyaviy natijasi buxgalteriyada: 9xxx schyotlar (daromad kredit − xarajat debet)."""
    oy = oy.replace(day=1)
    a = await _qoldiqlar(db, keyingi_oy(oy), oy)
    return sum((v[1] - v[0] for k, v in a.items() if k.startswith("9")), _0)
