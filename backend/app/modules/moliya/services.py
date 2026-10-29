"""Moliya hisobotlari va davr yopish (EKO TZ §8; prototip `Moliya.dc.html`).

Manbalar — faqat jurnallar: kassa orderlari (pul), ombor hujjatlari va sarf harakatlari (sotuv, FIFO tannarx),
buyurtmalar (summa, yetkazilgan sana). Hech qaysi raqam alohida saqlanmaydi — har safar jurnaldan yig'iladi;
faqat yopilgan oyning foyda-zarari qotgan nusxa bo'lib qoladi (keyingi tuzatish joriy oyga tushadi).

Sana — Toshkent vaqti bo'yicha. Rad — `MoliyaXato` (o'zbekcha).
"""

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import TASHKENT_TZ
from app.models import Client, Order, User
from app.models.enums import OrderStatus
from app.modules.kassa import service as kassa
from app.modules.moliya.models import MoliyaDavr, MoliyaMijozShart, MoliyaReja
from app.modules.moliya.schemas import (
    Akt,
    AktQator,
    Balans,
    Bosh,
    BuyurtmaFoyda,
    ByudjetQator,
    Debitor,
    HisobOqim,
    KalendarQator,
    KassirOqim,
    Kreditor,
    KunOqim,
    OyOqim,
    PnL,
    PulOqimi,
    Qator,
    Vazifa,
)
from app.modules.ombor import service as ombor
from app.modules.soliq import service as soliq
from app.services.settings_service import TOLOV_MUDDAT_KUN, get_setting

#: Kassa order maqsadlari — hisobotdagi nomi
MAQSAD = {
    "avans": "Avans",
    "tolov": "Buyurtma to'lovi",
    "qarz": "Qarz to'lovi",
    "sotuv": "Do'kon sotuvi",
    "boshqa": "Boshqa",
    "taminotchi": "Ta'minotchiga to'lov",
    "qaytarish": "Mijozga qaytarish",
    "inkassatsiya": "Inkassatsiya",
    "farq": "Smena farqi",
    "komissiya": "Bank komissiyasi",
    "xarajat": "Xarajat",
}
_0 = Decimal(0)


class MoliyaXato(Exception):
    def __init__(self, xatolar: list[str]) -> None:
        super().__init__(" · ".join(xatolar))
        self.xatolar = xatolar


# ───────────────────────── sana yordamchilari ─────────────────────────
def bugun() -> date:
    return datetime.now(TASHKENT_TZ).date()


def oy_boshi(d: date) -> date:
    return d.replace(day=1)


def keyingi_oy(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def oy_parse(oy: str) -> date:
    try:
        return date.fromisoformat(f"{oy}-01")
    except ValueError as e:
        raise MoliyaXato([f"Oy noto'g'ri: {oy} (YYYY-MM)"]) from e


def vaqt(d: date) -> datetime:
    """Mahalliy kun boshlanishi (aware)."""
    return datetime.combine(d, time(), TASHKENT_TZ)


def _mahalliy(dt: datetime) -> date:
    return dt.astimezone(TASHKENT_TZ).date()


def _key(nom: str) -> str:
    return " ".join(nom.split()).casefold()


async def ismlar(db: AsyncSession, ids: set[int | None]) -> dict[int, str]:
    ids_ = {i for i in ids if i}
    if not ids_:
        return {}
    return {u.id: (u.name or u.username) for u in (await db.execute(select(User).where(User.id.in_(ids_)))).scalars()}


# ───────────────────────── foyda va zarar ─────────────────────────
async def pnl(db: AsyncSession, oy: date, qotgan: bool = True) -> PnL:
    oy = oy_boshi(oy)
    if qotgan:
        d = (
            await db.execute(select(MoliyaDavr).where(MoliyaDavr.oy == oy, MoliyaDavr.holat == "yopiq"))
        ).scalar_one_or_none()
        if d is not None and d.natija:
            return PnL.model_validate({**d.natija, "yopiq": True})
    dan, gacha = vaqt(oy), vaqt(keyingi_oy(oy))
    orders = list(
        (
            await db.execute(
                select(Order, Client.full_name)
                .join(Client, Client.id == Order.client_id)
                .where(
                    Order.delivered_at >= dan,
                    Order.delivered_at < gacha,
                    Order.status != OrderStatus.CANCELLED,
                    Order.is_deleted == False,  # noqa: E712
                    Order.amount.is_not(None),
                )
                .order_by(Order.delivered_at, Order.id)
            )
        ).all()
    )
    tan = await ombor.buyurtma_tannarxi(db, [o.id for o, _ in orders])
    rent = [
        BuyurtmaFoyda(
            order_id=o.id,
            number=o.number,
            mijoz=m,
            summa=o.amount or _0,
            tannarx=tan.get(o.id, _0),
            foyda=(o.amount or _0) - tan.get(o.id, _0),
        )
        for o, m in orders
    ]
    hujjat = await ombor.sotuv_hujjatlari(db, oy, keyingi_oy(oy))
    xar: dict[str, Decimal] = defaultdict(lambda: _0)
    xar_soni: dict[str, int] = defaultdict(int)
    farq = _0
    for o in await kassa.orderlar_davr(db, dan, gacha):
        if o.maqsad == "farq":
            farq += o.summa if o.tur == "chiqim" else -o.summa
        elif o.tur == "chiqim" and o.maqsad in ("xarajat", "komissiya"):
            nom = o.turkum or MAQSAD[o.maqsad]
            xar[nom] += o.summa
            xar_soni[nom] += 1
    sotuv_b = sum((r.summa for r in rent), _0)
    sotuv_o = sum((h.summa for h in hujjat), _0)
    tan_b = sum((r.tannarx for r in rent), _0)
    tan_o = sum((h.tannarx for h in hujjat), _0)
    xarajatlar = sorted(
        (Qator(nom=k, summa=v, soni=xar_soni[k]) for k, v in xar.items() if v != 0), key=lambda q: -q.summa
    )
    # Soliq (EKO 6): rejim sozlanmagan bo'lsa ikkalasi ham 0
    sol = await soliq.oy_soliq(db, oy)
    xjami = sum((q.summa for q in xarajatlar), _0) + farq + sol.aylanma_soliq
    sof_tushum = sotuv_b + sotuv_o - sol.sotuv_qqs
    yalpi = sof_tushum - tan_b - tan_o
    return PnL(
        oy=f"{oy:%Y-%m}",
        sotuv_buyurtma=sotuv_b,
        sotuv_ombor=sotuv_o,
        sotuv=sotuv_b + sotuv_o,
        sotuv_qqs=sol.sotuv_qqs,
        sof_tushum=sof_tushum,
        tannarx_buyurtma=tan_b,
        tannarx_ombor=tan_o,
        tannarx=tan_b + tan_o,
        yalpi=yalpi,
        xarajatlar=xarajatlar,
        kassa_farqi=farq,
        aylanma_soliq=sol.aylanma_soliq,
        xarajat_jami=xjami,
        sof=yalpi - xjami,
        buyurtmalar=rent,
    )


# ───────────────────────── pul oqimi ─────────────────────────
async def pul_oqimi(db: AsyncSession, dan: date, gacha: date) -> PulOqimi:
    """[dan, gacha] kunlar (ikkalasi ham kiradi); oylar — `gacha` gacha 12 oy."""
    if gacha < dan:
        raise MoliyaXato(["Sana oralig'i noto'g'ri"])
    oxir = gacha + timedelta(days=1)
    rows = [o for o in await kassa.orderlar_davr(db, vaqt(dan), vaqt(oxir)) if o.maqsad != "otkazma"]
    km: dict[str, list[Decimal | int]] = defaultdict(lambda: [_0, 0])
    cm: dict[str, list[Decimal | int]] = defaultdict(lambda: [_0, 0])
    hs: dict[str, list[Decimal]] = defaultdict(lambda: [_0, _0])
    ks: dict[int | None, list[Decimal | int]] = defaultdict(lambda: [0, _0, _0])
    for o in rows:
        nom = (o.turkum or MAQSAD.get(o.maqsad, o.maqsad)) if o.maqsad == "xarajat" else MAQSAD.get(o.maqsad, o.maqsad)
        t = km if o.tur == "kirim" else cm
        t[nom][0] += o.summa  # type: ignore[operator]
        t[nom][1] += 1  # type: ignore[operator]
        hs[o.hisob][0 if o.tur == "kirim" else 1] += o.summa
        k = ks[o.kassir_id]
        k[0] += 1  # type: ignore[operator]
        k[1 if o.tur == "kirim" else 2] += o.summa  # type: ignore[operator]
    qoldiq = {h.kod: (h.nom, q) for h, q in await kassa.hisoblar(db)}
    ism = await ismlar(db, set(ks))
    # 12 oy: gacha oyi va undan oldingi 11 oy
    bosh = oy_boshi(gacha)
    for _ in range(11):
        bosh = oy_boshi(bosh - timedelta(days=1))
    oy_rows = [
        o for o in await kassa.orderlar_davr(db, vaqt(bosh), vaqt(keyingi_oy(oy_boshi(gacha)))) if o.maqsad != "otkazma"
    ]
    oylar: dict[str, list[Decimal]] = {}
    m = bosh
    while m <= oy_boshi(gacha):
        oylar[f"{m:%Y-%m}"] = [_0, _0]
        m = keyingi_oy(m)
    for o in oy_rows:
        key = f"{_mahalliy(o.sana):%Y-%m}"
        if key in oylar:
            oylar[key][0 if o.tur == "kirim" else 1] += o.summa
    kirim = sum((o.summa for o in rows if o.tur == "kirim"), _0)
    chiqim = sum((o.summa for o in rows if o.tur == "chiqim"), _0)

    def qatorlar(t: dict[str, list[Decimal | int]]) -> list[Qator]:
        return sorted(
            (Qator(nom=k, summa=Decimal(v[0]), soni=int(v[1])) for k, v in t.items() if v[0] != 0),
            key=lambda q: -q.summa,
        )

    return PulOqimi(
        dan=dan,
        gacha=gacha,
        kirim=kirim,
        chiqim=chiqim,
        saldo=kirim - chiqim,
        soni=len(rows),
        kirim_moddalar=qatorlar(km),
        chiqim_moddalar=qatorlar(cm),
        hisoblar=[
            HisobOqim(kod=kod, nom=nom, kirim=hs[kod][0], chiqim=hs[kod][1], qoldiq=q)
            for kod, (nom, q) in qoldiq.items()
        ],
        kassirlar=[
            KassirOqim(nom=ism.get(kid or 0, "—"), soni=int(v[0]), kirim=Decimal(v[1]), chiqim=Decimal(v[2]))
            for kid, v in ks.items()
        ],
        oylar=[OyOqim(oy=k, kirim=v[0], chiqim=v[1]) for k, v in oylar.items()],
    )


# ───────────────────────── debitorlik ─────────────────────────
async def _buyurtmalar(db: AsyncSession, client_id: int | None = None) -> list[tuple[Order, Decimal]]:
    """Summasi bor, bekor qilinmagan buyurtmalar va to'langani (kassa + kassagacha)."""
    q = select(Order).where(
        Order.status != OrderStatus.CANCELLED,
        Order.is_deleted == False,  # noqa: E712
        Order.amount.is_not(None),
    )
    if client_id is not None:
        q = q.where(Order.client_id == client_id)
    orders = list((await db.execute(q.order_by(Order.id))).scalars())
    paid = await kassa.tolangan(db, [o.id for o in orders])
    return [(o, (o.advance_payment or _0) + paid.get(o.id, _0)) for o in orders]


async def _muddatlar(db: AsyncSession) -> tuple[int, dict[int, MoliyaMijozShart]]:
    std = int(await get_setting(db, TOLOV_MUDDAT_KUN) or 0)
    return std, {s.client_id: s for s in (await db.execute(select(MoliyaMijozShart))).scalars()}


async def debitorlar(db: AsyncSession) -> list[Debitor]:
    std, shart = await _muddatlar(db)
    by: dict[int, list[tuple[Order, Decimal]]] = defaultdict(list)
    for o, p in await _buyurtmalar(db):
        by[o.client_id].append((o, p))
    clients = {c.id: c for c in (await db.execute(select(Client).where(Client.id.in_(by)))).scalars()}
    today = bugun()
    out = []
    for cid, rows in by.items():
        c = clients.get(cid)
        if c is None:
            continue
        sh = shart.get(cid)
        muddat = sh.muddat_kun if sh is not None and sh.muddat_kun is not None else std
        sotuv = tol = qarz = avans = otgan = _0
        eng_eski: date | None = None
        for o, p in rows:
            tol += p
            if o.delivered_at is not None:
                sotuv += o.amount or _0
                q = (o.amount or _0) - p
                if q > Decimal("0.5"):
                    qarz += q
                    d = _mahalliy(o.delivered_at)
                    eng_eski = d if eng_eski is None or d < eng_eski else eng_eski
                    if (today - d).days > muddat:
                        otgan += q
                elif q < 0:
                    avans += -q
            else:
                avans += p
        if qarz <= 0 and avans <= 0:
            continue
        kun = (today - eng_eski).days if eng_eski else None
        out.append(
            Debitor(
                client_id=cid,
                mijoz=c.full_name,
                telefon=c.phone,
                sotuv=sotuv,
                tolangan=tol,
                qarz=qarz,
                avans=avans,
                kun=kun,
                muddat_kun=muddat,
                muddati_otgan=otgan > 0,
                muddati_otgan_summa=otgan,
                limit=c.kredit_limit,
                limitdan_oshgan=c.kredit_limit is not None and qarz > c.kredit_limit,
                shartnoma_no=sh.shartnoma_no if sh else "",
            )
        )
    return sorted(out, key=lambda d: (not d.muddati_otgan, -d.qarz))


async def mijoz_shart_saqla(
    db: AsyncSession, client_id: int, shartnoma_no: str, muddat_kun: int | None, kredit_limit: Decimal | None
) -> None:
    c = await db.get(Client, client_id)
    if c is None or c.is_deleted:
        raise MoliyaXato(["Mijoz topilmadi"])
    sh = (
        await db.execute(select(MoliyaMijozShart).where(MoliyaMijozShart.client_id == client_id))
    ).scalar_one_or_none()
    if sh is None:
        sh = MoliyaMijozShart(client_id=client_id)
        db.add(sh)
    sh.shartnoma_no, sh.muddat_kun = shartnoma_no.strip(), muddat_kun
    c.kredit_limit = kredit_limit
    await db.flush()


async def akt(db: AsyncSession, client_id: int, dan: date, gacha: date) -> Akt:
    c = await db.get(Client, client_id)
    if c is None:
        raise MoliyaXato(["Mijoz topilmadi"])
    hodisa: list[tuple[date, int, str, str, Decimal, Decimal]] = []
    for o, _ in await _buyurtmalar(db, client_id):
        if o.advance_payment:
            hodisa.append((_mahalliy(o.created_at), 0, o.number, "Kassagacha to'lov", _0, o.advance_payment))
        if o.delivered_at is not None:
            hodisa.append((_mahalliy(o.delivered_at), 1, o.number, "Buyurtma yetkazildi", o.amount or _0, _0))
    for ko in await kassa.orderlar_davr(db, client_id=client_id):
        izoh = MAQSAD.get(ko.maqsad, ko.maqsad) + (" (storno)" if ko.storno_of_id else "")
        if ko.tur == "kirim" and ko.maqsad in ("avans", "tolov", "qarz", "sotuv"):
            hodisa.append((_mahalliy(ko.sana), 2, ko.no, izoh, _0, ko.summa))
        elif ko.tur == "chiqim" and ko.maqsad == "qaytarish":
            hodisa.append((_mahalliy(ko.sana), 2, ko.no, izoh, ko.summa, _0))
    hodisa.sort(key=lambda h: (h[0], h[1]))
    bosh = sum((d - k for s, _, _, _, d, k in hodisa if s < dan), _0)
    saldo = bosh
    qatorlar = []
    for s, _, no, izoh, d, k in hodisa:
        if dan <= s <= gacha:
            saldo += d - k
            qatorlar.append(AktQator(sana=s, hujjat=no, izoh=izoh, debet=d, kredit=k, saldo=saldo))
    return Akt(
        client_id=client_id,
        mijoz=c.full_name,
        dan=dan,
        gacha=gacha,
        boshlangich=bosh,
        qatorlar=qatorlar,
        debet=sum((q.debet for q in qatorlar), _0),
        kredit=sum((q.kredit for q in qatorlar), _0),
        yakuniy=saldo,
    )


# ───────────────────────── kreditorlik ─────────────────────────
async def _taminotchilar(db: AsyncSession) -> dict[str, tuple[str, list[ombor.Hujjat], Decimal]]:
    """{kalit: (nom, hujjatlar, to'langan)}. To'lov — kassa orderi kontragenti bo'yicha, harf farqsiz."""
    hujjat: dict[str, list[ombor.Hujjat]] = defaultdict(list)
    nom: dict[str, str] = {}
    for h in await ombor.kirim_hujjatlari(db):
        k = _key(h.kontragent)
        hujjat[k].append(h)
        nom.setdefault(k, " ".join(h.kontragent.split()))
    tol: dict[str, Decimal] = defaultdict(lambda: _0)
    for o in await kassa.orderlar_davr(db):
        if o.tur == "chiqim" and o.maqsad == "taminotchi":
            k = _key(o.kontragent)
            tol[k] += o.summa
            nom.setdefault(k, " ".join(o.kontragent.split()))
    return {k: (nom[k], hujjat.get(k, []), tol.get(k, _0)) for k in set(hujjat) | set(tol)}


def _tolanmagan(hujjatlar: list[ombor.Hujjat], tolangan: Decimal) -> list[tuple[ombor.Hujjat, Decimal]]:
    """To'lov eng eski hujjatdan yopiladi — qolgan qarzli hujjatlar."""
    rest = tolangan
    out = []
    for h in sorted(hujjatlar, key=lambda x: (x.sana, x.id)):
        if h.summa <= 0:
            rest -= h.summa  # storno — qarzni kamaytiradi
            continue
        x = min(h.summa, max(rest, _0))
        rest -= x
        if h.summa - x > Decimal("0.5"):
            out.append((h, h.summa - x))
    return out


async def kreditorlar(db: AsyncSession) -> list[Kreditor]:
    out = []
    for nom, hj, tol in (await _taminotchilar(db)).values():
        jami = sum((h.summa for h in hj), _0)
        qol = _tolanmagan(hj, tol)
        if jami - tol == 0 and not qol:
            continue
        muddatlar = [h.muddat or h.sana for h, _ in qol]
        out.append(
            Kreditor(
                nom=nom,
                faktura=jami,
                tolangan=tol,
                qarz=max(jami - tol, _0),
                avans=max(tol - jami, _0),
                hujjatlar=sum(1 for h in hj if h.summa > 0),
                muddat=min(muddatlar) if muddatlar else None,
            )
        )
    return sorted(out, key=lambda k: -k.qarz)


# ───────────────────────── to'lov kalendari ─────────────────────────
def _reja_sanalari(r: MoliyaReja, dan: date, gacha: date) -> list[date]:
    if r.takror == "bir":
        return [r.sana] if dan <= r.sana <= gacha else []
    out = []
    m = oy_boshi(max(dan, r.sana))
    while m <= gacha:
        kun = min(r.sana.day, (keyingi_oy(m) - timedelta(days=1)).day)
        d = m.replace(day=kun)
        if r.sana <= d and dan <= d <= gacha:
            out.append(d)
        m = keyingi_oy(m)
    return out


async def kalendar(db: AsyncSession, kun: int = 45) -> list[KalendarQator]:
    """Bugundan `kun` kungacha: mijozdan kutilayotgan (muddati o'tgani ham), ta'minotchiga va rejali to'lovlar."""
    today = bugun()
    oxir = today + timedelta(days=kun)
    std, shart = await _muddatlar(db)
    out: list[KalendarQator] = []
    clients = {c.id: c.full_name for c in (await db.execute(select(Client))).scalars()}
    for o, p in await _buyurtmalar(db):
        q = (o.amount or _0) - p
        if o.delivered_at is None or q <= Decimal("0.5"):
            continue
        sh = shart.get(o.client_id)
        muddat = sh.muddat_kun if sh is not None and sh.muddat_kun is not None else std
        d = _mahalliy(o.delivered_at) + timedelta(days=muddat)
        if d <= oxir:
            out.append(
                KalendarQator(
                    sana=d,
                    tur="kirim",
                    nom=f"{clients.get(o.client_id, '')} · {o.number}",
                    summa=q,
                    manba="mijoz",
                    muddati_otgan=d < today,
                    havola_id=o.client_id,
                )
            )
    for nom, hj, tol in (await _taminotchilar(db)).values():
        for h, q in _tolanmagan(hj, tol):
            d = h.muddat or h.sana
            if d <= oxir:
                out.append(
                    KalendarQator(
                        sana=d,
                        tur="chiqim",
                        nom=f"{nom} · {h.no}",
                        summa=q,
                        manba="taminotchi",
                        muddati_otgan=d < today,
                    )
                )
    for r in (await db.execute(select(MoliyaReja).where(MoliyaReja.faol == True))).scalars():  # noqa: E712
        for d in _reja_sanalari(r, today, oxir):
            out.append(
                KalendarQator(
                    sana=d,
                    tur="kirim" if r.tur == "kirim" else "chiqim",
                    nom=r.nom,
                    summa=r.summa,
                    manba="reja",
                    muddati_otgan=False,
                    havola_id=r.id,
                )
            )
    return sorted(out, key=lambda x: (x.sana, x.tur, x.nom))


# ───────────────────────── byudjet, balans, bosh ─────────────────────────
async def byudjet(db: AsyncSession, oy: date) -> list[ByudjetQator]:
    p = await pnl(db, oy)
    fakt = {q.nom: q.summa for q in p.xarajatlar}
    out = []
    for m in await kassa.moddalar(db, faqat_faol=False):
        f = fakt.pop(m.nom, _0)
        if not m.faol and f == 0:
            continue
        foiz = int(f * 100 / m.oylik_limit) if m.oylik_limit else None
        out.append(ByudjetQator(nom=m.nom, limit=m.oylik_limit, fakt=f, foiz=foiz))
    out += [ByudjetQator(nom=k, limit=None, fakt=v, foiz=None) for k, v in fakt.items()]
    return out


async def balans(db: AsyncSession) -> Balans:
    pul = sum((q for _, q in await kassa.hisoblar(db)), _0)
    deb = await debitorlar(db)
    kre = await kreditorlar(db)
    debitorlik = sum((d.qarz for d in deb), _0)
    olingan = sum((d.avans for d in deb), _0)
    kreditorlik = sum((k.qarz for k in kre), _0)
    berilgan = sum((k.avans for k in kre), _0)
    omb = await ombor.ombor_qiymati(db)
    aktiv = pul + debitorlik + omb + berilgan
    passiv = kreditorlik + olingan
    return Balans(
        pul=pul,
        debitorlik=debitorlik,
        ombor=omb,
        berilgan_avans=berilgan,
        aktiv=aktiv,
        kreditorlik=kreditorlik,
        olingan_avans=olingan,
        passiv=passiv,
        sof=aktiv - passiv,
    )


async def bosh(db: AsyncSession) -> Bosh:
    today = bugun()
    hisoblar = [HisobOqim(kod=h.kod, nom=h.nom, kirim=_0, chiqim=_0, qoldiq=q) for h, q in await kassa.hisoblar(db)]
    deb = await debitorlar(db)
    kal = await kalendar(db, 30)
    vazifa: list[Vazifa] = []
    for sm in await kassa.ochiq_smenalar(db):
        if _mahalliy(sm.ochilgan_at) < today:
            vazifa.append(
                Vazifa(
                    matn=f"{sm.no} yopilmagan",
                    izoh=f"{_mahalliy(sm.ochilgan_at):%d.%m} dan beri ochiq",
                    bolim="smenalar",
                )
            )
    otgan = [d for d in deb if d.muddati_otgan]
    if otgan:
        vazifa.append(
            Vazifa(
                matn=f"{len(otgan)} mijozning qarzi muddatidan o'tgan",
                izoh=", ".join(d.mijoz for d in otgan[:3]) + ("…" if len(otgan) > 3 else ""),
                summa=sum((d.muddati_otgan_summa for d in otgan), _0),
                bolim="debitorlar",
            )
        )
    for r in kal:
        if r.tur == "chiqim" and r.sana <= today + timedelta(days=3):
            vazifa.append(
                Vazifa(
                    matn=r.nom,
                    izoh="muddati o'tgan" if r.muddati_otgan else f"{r.sana:%d.%m} to'lanadi",
                    summa=r.summa,
                    bolim="kalendar",
                )
            )
    for b in await byudjet(db, today):
        if b.foiz is not None and b.foiz > 100:
            vazifa.append(Vazifa(matn=f"«{b.nom}» byudjetdan oshdi", izoh=f"{b.foiz} %", summa=b.fakt, bolim="byudjet"))
    otgan_oy = oy_boshi(oy_boshi(today) - timedelta(days=1))
    if today.day > 5 and not await davr_yopiq(db, otgan_oy):
        vazifa.append(Vazifa(matn=f"{otgan_oy:%Y-%m} oyi yopilmagan", izoh="Hisobotlar → Davr yopish", bolim="davrlar"))
    boshi = today - timedelta(days=29)
    kunlar: dict[date, list[Decimal]] = {boshi + timedelta(days=i): [_0, _0] for i in range(30)}
    for o in await kassa.orderlar_davr(db, vaqt(boshi), vaqt(today + timedelta(days=1))):
        if o.maqsad != "otkazma" and (d := _mahalliy(o.sana)) in kunlar:
            kunlar[d][0 if o.tur == "kirim" else 1] += o.summa
    return Bosh(
        hisoblar=hisoblar,
        pul=sum((h.qoldiq for h in hisoblar), _0),
        debitorlik=sum((d.qarz for d in deb), _0),
        debitor_soni=sum(1 for d in deb if d.qarz > 0),
        muddati_otgan=sum((d.muddati_otgan_summa for d in otgan), _0),
        olingan_avans=sum((d.avans for d in deb), _0),
        kreditorlik=sum((k.qarz for k in await kreditorlar(db)), _0),
        rejali_30=sum((r.summa for r in kal if r.manba == "reja" and r.tur == "chiqim"), _0),
        vazifalar=vazifa,
        kunlar=[KunOqim(sana=d, kirim=v[0], chiqim=v[1]) for d, v in kunlar.items()],
        pnl=await pnl(db, today),
    )


# ───────────────────────── davr yopish ─────────────────────────
async def davr_yopiq(db: AsyncSession, d: date) -> bool:
    return (
        await db.scalar(select(MoliyaDavr.id).where(MoliyaDavr.oy == oy_boshi(d), MoliyaDavr.holat == "yopiq"))
        is not None
    )


async def _davr(db: AsyncSession, oy: date) -> MoliyaDavr | None:
    return (await db.execute(select(MoliyaDavr).where(MoliyaDavr.oy == oy).with_for_update())).scalar_one_or_none()


async def davr_yop(db: AsyncSession, oy: date, user_id: int | None) -> MoliyaDavr:
    """Faqat tugagan oy; o'sha oyda ochilgan smena yopilgan va qoralama hujjat qolmagan bo'lishi kerak."""
    oy = oy_boshi(oy)
    xato = []
    if oy >= oy_boshi(bugun()):
        xato.append("Faqat tugagan oy yopiladi")
    d = await _davr(db, oy)
    if d is not None and d.holat == "yopiq":
        xato.append(f"{oy:%Y-%m} allaqachon yopilgan")
    for sm in await kassa.ochiq_smenalar(db):
        if _mahalliy(sm.ochilgan_at) < keyingi_oy(oy):
            xato.append(f"{sm.no} smenasi yopilmagan")
    if qr := await ombor.qoralamalar(db, oy, keyingi_oy(oy)):
        xato.append(f"Tasdiqlanmagan ombor hujjatlari: {', '.join(qr[:5])}" + ("…" if len(qr) > 5 else ""))
    if xato:
        raise MoliyaXato(xato)
    natija = (await pnl(db, oy, qotgan=False)).model_dump(mode="json")
    if d is None:
        d = MoliyaDavr(oy=oy, holat="yopiq")
        db.add(d)
    d.holat, d.yopgan_id, d.yopilgan_at, d.natija = "yopiq", user_id, datetime.now(UTC), natija
    d.ochish_sorov_id, d.ochish_sabab, d.ochgan_id, d.ochilgan_at = None, "", None, None
    await db.flush()
    return d


async def davr_ochish_sorov(db: AsyncSession, oy: date, user_id: int | None, sabab: str) -> MoliyaDavr:
    d = await _davr(db, oy_boshi(oy))
    if d is None or d.holat != "yopiq":
        raise MoliyaXato(["Bu oy yopilmagan"])
    d.ochish_sorov_id, d.ochish_sabab = user_id, sabab.strip()[:200]
    await db.flush()
    return d


async def davr_ochish_tasdiq(db: AsyncSession, oy: date, user_id: int | None) -> MoliyaDavr:
    """Ikki kalit: so'ragan xodim o'zi tasdiqlay olmaydi."""
    d = await _davr(db, oy_boshi(oy))
    if d is None or d.holat != "yopiq":
        raise MoliyaXato(["Bu oy yopilmagan"])
    if d.ochish_sorov_id is None:
        raise MoliyaXato(["Avval qayta ochish so'rovi yozilsin"])
    if user_id is not None and user_id == d.ochish_sorov_id:
        raise MoliyaXato(["Ikki kalit qoidasi: so'rovni boshqa xodim tasdiqlaydi"])
    d.holat, d.ochgan_id, d.ochilgan_at, d.natija = "ochildi", user_id, datetime.now(UTC), {}
    await db.flush()
    return d
