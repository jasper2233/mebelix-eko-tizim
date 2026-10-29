"""Soliq qoidalari (EKO TZ §9).

- Rejim va stavka — `soliq_rejim` tarixidan, hujjat sanasiga ko'ra (QQS to'lovchi yoki aylanmadan soliq).
- Narxlar QQS bilan: QQS = jami × f / (100 + f). Pozitsiya QQS turi `nol` / `ozod` — QQS 0.
- ESF: faqat yuridik mijozga (jismoniy shaxsga — fiskal chek, S5); buyurtmadan (yetkazilganda) yoki ombor sotuv
  hujjatidan; MXIK siz pozitsiya ESF ga kirmaydi. Yuborish — navbat (`navbatda`) orqali fonda, operator
  ishlamasa qayta urinadi; sotuv to'xtamaydi.
- Oylik soliq: aylanma = yetkazilgan buyurtmalar + do'kon sotuvi (storno ayirilgan); QQS rejimida sotuvdagi QQS −
  qabul qilingan kiruvchi ESF dagi QQS; aylanma rejimida aylanma × stavka.

Rad — `SoliqXato` (o'zbekcha).
"""

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import TASHKENT_TZ
from app.models import Client, Order
from app.models.enums import OrderStatus
from app.modules.ombor import service as ombor
from app.modules.soliq.models import SoliqEsf, SoliqKorxona, SoliqMijoz, SoliqRejim
from app.modules.soliq.operator import OperatorXato, SinovOperator, adapter

_0 = Decimal(0)
_Q = Decimal("0.01")
#: Operator ishlamasa qayta urinish oralig'i, daqiqa; tugasa holat `xato` (qo'lda qayta navbatga qo'yiladi)
BACKOFF = (1, 5, 30, 120, 360)
TIRIK = ("qoralama", "navbatda", "yuborildi", "qabul_qilindi", "kutilmoqda", "xato")


class SoliqXato(Exception):
    def __init__(self, xatolar: list[str]) -> None:
        super().__init__(" · ".join(xatolar))
        self.xatolar = xatolar


def _now() -> datetime:
    return datetime.now(UTC)


def bugun() -> date:
    return datetime.now(TASHKENT_TZ).date()


def _mahalliy(dt: datetime) -> date:
    return dt.astimezone(TASHKENT_TZ).date()


def _vaqt(d: date) -> datetime:
    return datetime.combine(d, time(), TASHKENT_TZ)


def keyingi_oy(d: date) -> date:
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def _key(s: str) -> str:
    return " ".join(s.split()).casefold()


# ───────────────────────── sozlama ─────────────────────────
async def korxona(db: AsyncSession) -> SoliqKorxona:
    # Bitta qator: birinchisi (tranzaksiya qulfi — ikki so'rov birdaniga ikkita yaratmasin)
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext("soliq_korxona"))))
    k = (await db.execute(select(SoliqKorxona).order_by(SoliqKorxona.id).limit(1))).scalar_one_or_none()
    if k is None:
        k = SoliqKorxona()
        db.add(k)
        await db.flush()
    return k


async def rejim_on(db: AsyncSession, d: date) -> SoliqRejim | None:
    return (
        await db.execute(
            select(SoliqRejim).where(SoliqRejim.amal_boshi <= d).order_by(SoliqRejim.amal_boshi.desc()).limit(1)
        )
    ).scalar_one_or_none()


async def rejim_qosh(
    db: AsyncSession, amal_boshi: date, rejim: str, qqs_foiz: Decimal, aylanma_foiz: Decimal, user_id: int | None
) -> SoliqRejim:
    """Yangi rejim/stavka shu sanadan. Yopilgan oy yoki yuborilgan ESF bor sanaga orqaga yozilmaydi."""
    xato = []
    if rejim not in ("qqs", "aylanma"):
        xato.append("Rejim: qqs yoki aylanma")
    band = await db.scalar(select(SoliqRejim.id).where(SoliqRejim.amal_boshi == amal_boshi))
    if band is not None:
        xato.append(f"{amal_boshi} dan rejim allaqachon yozilgan")
    esf = await db.scalar(
        select(func.count()).where(SoliqEsf.sana >= amal_boshi, SoliqEsf.holat.in_(("yuborildi", "qabul_qilindi")))
    )
    if esf:
        xato.append(f"{amal_boshi} dan keyin yuborilgan ESF bor ({esf} ta) — rejim keyingi sanadan o'zgaradi")
    if xato:
        raise SoliqXato(xato)
    r = SoliqRejim(amal_boshi=amal_boshi, rejim=rejim, qqs_foiz=qqs_foiz, aylanma_foiz=aylanma_foiz, yozgan_id=user_id)
    db.add(r)
    await db.flush()
    return r


def qqs_ajrat(jami: Decimal, foiz: Decimal) -> Decimal:
    """Narx ichidagi QQS."""
    return (jami * foiz / (100 + foiz)).quantize(_Q, ROUND_HALF_UP) if foiz > 0 else _0


async def mijoz(db: AsyncSession, client_id: int) -> SoliqMijoz | None:
    return (await db.execute(select(SoliqMijoz).where(SoliqMijoz.client_id == client_id))).scalar_one_or_none()


def mijoz_tekshir(m: SoliqMijoz) -> list[str]:
    xato = []
    if m.yuridik and not re.fullmatch(r"\d{9}", m.stir):
        xato.append("Yuridik mijoz STIR i 9 raqam bo'lishi kerak")
    if not m.yuridik and m.jshshir and not re.fullmatch(r"\d{14}", m.jshshir):
        xato.append("JShShIR 14 raqam bo'lishi kerak")
    if m.mfo and not re.fullmatch(r"\d{5}", m.mfo):
        xato.append("MFO 5 raqam")
    if m.hisob_raqam and not re.fullmatch(r"\d{20}", m.hisob_raqam):
        xato.append("Hisob raqami 20 raqam")
    return xato


async def mijoz_saqla(db: AsyncSession, client_id: int, qiymat: dict[str, Any]) -> SoliqMijoz:
    if await db.get(Client, client_id) is None:
        raise SoliqXato(["Mijoz topilmadi"])
    m = await mijoz(db, client_id)
    if m is None:
        m = SoliqMijoz(client_id=client_id)
        db.add(m)
    for k, v in qiymat.items():
        setattr(m, k, v.strip() if isinstance(v, str) else v)
    if xato := mijoz_tekshir(m):
        raise SoliqXato(xato)
    await db.flush()
    return m


async def mxik_saqla(db: AsyncSession, item_id: int, mxik: str | None, birlik_kod: str | None, qqs_turi: str) -> None:
    xato = []
    if mxik and not re.fullmatch(r"\d{17}", mxik):
        xato.append("MXIK 17 raqam bo'lishi kerak")
    if qqs_turi not in ("standart", "nol", "ozod"):
        xato.append("QQS turi: standart, nol yoki ozod")
    if xato:
        raise SoliqXato(xato)
    if not await ombor.soliq_saqla(db, item_id, mxik or None, (birlik_kod or "").strip() or None, qqs_turi):
        raise SoliqXato(["Pozitsiya topilmadi"])


# ───────────────────────── ESF yasash ─────────────────────────
async def _next_no(db: AsyncSession) -> str:
    p = f"ESF-{bugun().year}-"
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(p))))
    last = await db.scalar(
        select(func.max(cast(func.split_part(SoliqEsf.no, "-", 3), Integer))).where(SoliqEsf.no.like(f"{p}%"))
    )
    return f"{p}{(last or 0) + 1:04d}"


def _qator(
    nom: str, mxik: str, birlik: str, miqdor: Decimal, jami: Decimal, foiz: Decimal | None, ozod: bool = False
) -> dict[str, Any]:
    q = qqs_ajrat(jami, foiz or _0)
    summa = jami - q
    narx = (summa / miqdor).quantize(_Q, ROUND_HALF_UP) if miqdor else summa
    return {
        "nom": nom,
        "mxik": mxik,
        "birlik": birlik,
        "miqdor": str(miqdor),
        "narx": str(narx),
        "summa": str(summa),
        "qqs_foiz": None if foiz is None else str(foiz),
        "ozod": ozod,
        "qqs": str(q),
        "jami": str(jami),
    }


async def _boshla(
    db: AsyncSession, client_id: int, sana: date
) -> tuple[SoliqKorxona, SoliqRejim, SoliqMijoz, list[str]]:
    xato = []
    k = await korxona(db)
    if not re.fullmatch(r"\d{9}", k.stir) or not k.nomi.strip():
        xato.append("Korxona nomi va STIR i sozlanmagan (Soliq → Sozlamalar)")
    r = await rejim_on(db, sana)
    if r is None:
        xato.append(f"{sana} uchun soliq rejimi sozlanmagan")
    m = await mijoz(db, client_id)
    if m is None or not m.yuridik:
        xato.append("ESF faqat yuridik mijozga yoziladi — mijoz rekvizitlarini kiriting (jismoniy shaxsga fiskal chek)")
    elif e := mijoz_tekshir(m):
        xato += e
    return k, r, m, xato  # type: ignore[return-value]


def _rekvizit(k: SoliqKorxona, m: SoliqMijoz, mijoz_nomi: str) -> dict[str, Any]:
    return {
        "sotuvchi": {
            "nomi": k.nomi,
            "stir": k.stir,
            "manzil": k.manzil,
            "bank": k.bank,
            "mfo": k.mfo,
            "hisob_raqam": k.hisob_raqam,
            "qqs_kod": k.qqs_kod,
            "direktor": k.direktor,
            "buxgalter": k.buxgalter,
        },
        "xaridor": {
            "nomi": m.nomi or mijoz_nomi,
            "stir": m.stir,
            "jshshir": m.jshshir,
            "bank": m.bank,
            "mfo": m.mfo,
            "hisob_raqam": m.hisob_raqam,
            "qqs_kod": m.qqs_kod,
        },
    }


async def _saqla(
    db: AsyncSession,
    *,
    sana: date,
    client: Client,
    k: SoliqKorxona,
    r: SoliqRejim,
    m: SoliqMijoz,
    qatorlar: list[dict[str, Any]],
    user_id: int | None,
    order_id: int | None = None,
    stock_doc_id: int | None = None,
) -> SoliqEsf:
    summa = sum((Decimal(q["summa"]) for q in qatorlar), _0)
    qqs = sum((Decimal(q["qqs"]) for q in qatorlar), _0)
    e = SoliqEsf(
        no=await _next_no(db),
        tur="chiquvchi",
        holat="qoralama",
        sana=sana,
        order_id=order_id,
        stock_doc_id=stock_doc_id,
        client_id=client.id,
        kontragent=m.nomi or client.full_name,
        kontragent_stir=m.stir,
        rekvizit=_rekvizit(k, m, client.full_name),
        qatorlar=qatorlar,
        rejim=r.rejim,
        summa=summa,
        qqs=qqs,
        jami=summa + qqs,
        operator=k.esf_operator,
        yaratgan_id=user_id,
    )
    db.add(e)
    await db.flush()
    return e


async def _tirik(db: AsyncSession, **kw: int) -> SoliqEsf | None:
    q = select(SoliqEsf).where(SoliqEsf.holat.in_(TIRIK), SoliqEsf.tur == "chiquvchi")
    for k, v in kw.items():
        q = q.where(getattr(SoliqEsf, k) == v)
    return (await db.execute(q)).scalars().first()


async def esf_buyurtmadan(db: AsyncSession, order_id: int, user_id: int | None) -> SoliqEsf:
    o = await db.get(Order, order_id, with_for_update=True)
    if o is None or o.is_deleted or o.status == OrderStatus.CANCELLED:
        raise SoliqXato(["Buyurtma topilmadi"])
    xato = []
    if o.amount is None:
        xato.append("Buyurtma summasi yo'q")
    if o.delivered_at is None:
        xato.append("Buyurtma hali yetkazilmagan — ESF jo'natilganda yoziladi")
    if (t := await _tirik(db, order_id=o.id)) is not None:
        xato.append(f"{o.number} uchun {t.no} allaqachon bor")
    sana = _mahalliy(o.delivered_at) if o.delivered_at else bugun()
    k, r, m, x = await _boshla(db, o.client_id, sana)
    xato += x
    if not re.fullmatch(r"\d{17}", k.buyurtma_mxik):
        xato.append("Buyurtma (mebel) uchun MXIK sozlanmagan (Soliq → Sozlamalar)")
    if xato:
        raise SoliqXato(xato)
    foiz = r.qqs_foiz if r.rejim == "qqs" else None
    q = _qator(f"{k.buyurtma_nomi} · {o.number}", k.buyurtma_mxik, k.buyurtma_birlik, Decimal(1), o.amount or _0, foiz)
    client = await db.get(Client, o.client_id)
    assert client is not None
    return await _saqla(db, sana=sana, client=client, k=k, r=r, m=m, qatorlar=[q], user_id=user_id, order_id=o.id)


async def esf_hujjatdan(db: AsyncSession, stock_doc_id: int, client_id: int, user_id: int | None) -> SoliqEsf:
    doc, qatorlar = await ombor.hujjat_qatorlari(db, stock_doc_id)
    xato = []
    if doc is None or doc.kind != "chiqim" or doc.status != "confirmed":
        raise SoliqXato(["Tasdiqlangan ombor sotuv (chiqim) hujjati kerak"])
    if (t := await _tirik(db, stock_doc_id=stock_doc_id)) is not None:
        xato.append(f"{doc.no} uchun {t.no} allaqachon bor")
    client = await db.get(Client, client_id)
    if client is None:
        raise SoliqXato(["Mijoz topilmadi"])
    k, r, m, x = await _boshla(db, client_id, doc.doc_date)
    xato += x
    poz = await ombor.soliq_pozitsiyalar(db, [q.item_id for q in qatorlar if q.item_id])
    out = []
    for q in qatorlar:
        p = poz.get(q.item_id or 0)
        if p is None or not p.mxik:
            xato.append(f"«{q.nom}» — MXIK yo'q (katalogda kiriting)")
            continue
        if r is not None:
            foiz = None if r.rejim == "aylanma" else (r.qqs_foiz if p.qqs_turi == "standart" else _0)
            out.append(_qator(p.name, p.mxik, p.birlik_kod or p.unit, q.miqdor, q.summa, foiz, p.qqs_turi == "ozod"))
    if xato:
        raise SoliqXato(xato)
    return await _saqla(
        db, sana=doc.doc_date, client=client, k=k, r=r, m=m, qatorlar=out, user_id=user_id, stock_doc_id=stock_doc_id
    )


def operator_hujjati(e: SoliqEsf) -> dict[str, Any]:
    return {
        "raqam": e.no,
        "sana": str(e.sana),
        **e.rekvizit,
        "rejim": e.rejim,
        "qatorlar": e.qatorlar,
        "summa": str(e.summa),
        "qqs": str(e.qqs),
        "jami": str(e.jami),
    }


# ───────────────────────── holat o'zgarishi ─────────────────────────
async def _esf(db: AsyncSession, esf_id: int) -> SoliqEsf:
    e = await db.get(SoliqEsf, esf_id, with_for_update=True)
    if e is None:
        raise SoliqXato(["ESF topilmadi"])
    return e


async def navbatga(db: AsyncSession, esf_id: int) -> SoliqEsf:
    """Qoralama (yoki xato bilan to'xtagan) ESF ni yuborish navbatiga qo'yadi. Imzo — operator adapterida."""
    e = await _esf(db, esf_id)
    if e.tur != "chiquvchi" or e.holat not in ("qoralama", "xato"):
        raise SoliqXato([f"{e.no} ({e.holat}) navbatga qo'yilmaydi"])
    e.holat, e.urinish, e.keyingi_urinish, e.xato = "navbatda", 0, None, ""
    await db.flush()
    return e


async def bekor(db: AsyncSession, esf_id: int) -> SoliqEsf:
    e = await _esf(db, esf_id)
    if e.tur != "chiquvchi" or e.holat in ("bekor", "rad_etildi"):
        raise SoliqXato([f"{e.no} ({e.holat}) bekor qilinmaydi"])
    if e.operator_id:
        try:
            await adapter(e.operator).bekor(db, e.operator_id)
        except OperatorXato as ex:
            raise SoliqXato([f"Operator: {ex}"]) from ex
    e.holat = "bekor"
    await db.flush()
    return e


@dataclass
class Ishlov:
    yuborildi: int = 0
    javob: int = 0
    xato: int = 0
    kiruvchi: int = 0
    xabarlar: list[str] = field(default_factory=list)


async def ishlov(db: AsyncSession, limit: int = 20) -> Ishlov:
    """Fon ishi (cron): navbatdagini yuborish, yuborilganning holatini so'rash, kiruvchilarni olish."""
    n = Ishlov()
    now = _now()
    navbat = (
        await db.execute(
            select(SoliqEsf)
            .where(SoliqEsf.holat == "navbatda")
            .where((SoliqEsf.keyingi_urinish.is_(None)) | (SoliqEsf.keyingi_urinish <= now))
            .order_by(SoliqEsf.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).scalars()
    for e in list(navbat):
        try:
            e.operator_id = await adapter(e.operator).yubor(db, operator_hujjati(e))
            e.holat, e.yuborilgan_at, e.xato = "yuborildi", now, ""
            n.yuborildi += 1
        except OperatorXato as ex:
            e.urinish += 1
            e.xato = str(ex)[:500]
            if e.urinish > len(BACKOFF):
                e.holat = "xato"
            else:
                e.keyingi_urinish = now + timedelta(minutes=BACKOFF[e.urinish - 1])
            n.xato += 1
            n.xabarlar.append(f"{e.no}: {ex}")
    yuborilgan = (
        await db.execute(
            select(SoliqEsf).where(SoliqEsf.holat == "yuborildi").limit(limit).with_for_update(skip_locked=True)
        )
    ).scalars()
    for e in list(yuborilgan):
        try:
            j = await adapter(e.operator).holat(db, e.operator_id or "")
        except OperatorXato as ex:
            n.xabarlar.append(f"{e.no}: {ex}")
            continue
        if j.holat in ("qabul_qilindi", "rad_etildi", "bekor"):
            e.holat, e.xato, e.javob_at = j.holat, j.xabar, now
            n.javob += 1
    n.kiruvchi = await kiruvchi_ol(db)
    await db.flush()
    return n


# ───────────────────────── kiruvchi ESF ─────────────────────────
async def kiruvchi_ol(db: AsyncSession) -> int:
    """Operatordan yangi kiruvchi ESF lar; ombor kirimi bilan solishtiriladi (sotuvchi nomi + summa ±1)."""
    k = await korxona(db)
    try:
        kel = await adapter(k.esf_operator).kiruvchilar(db)
    except OperatorXato:
        return 0
    bor = set(
        (await db.execute(select(SoliqEsf.operator_id).where(SoliqEsf.operator_id.in_([o for o, _ in kel])))).scalars()
    )
    kirimlar = await ombor.kirim_hujjatlari(db) if kel else []
    band = set((await db.execute(select(SoliqEsf.stock_doc_id).where(SoliqEsf.tur == "kiruvchi"))).scalars())
    n = 0
    for oid, h in kel:
        if oid in bor:
            continue
        s = h.get("sotuvchi", {})
        jami = Decimal(str(h.get("jami", 0)))
        mos = next(
            (
                d
                for d in kirimlar
                if d.summa > 0
                and d.id not in band
                and _key(d.kontragent) == _key(str(s.get("nomi", "")))
                and abs(d.summa - jami) <= 1
            ),
            None,
        )
        if mos is not None:
            band.add(mos.id)
        db.add(
            SoliqEsf(
                no=await _next_no(db),
                tur="kiruvchi",
                holat="kutilmoqda",
                sana=date.fromisoformat(str(h.get("sana"))[:10]),
                raqam=str(h.get("raqam", ""))[:40],
                stock_doc_id=mos.id if mos else None,
                kontragent=str(s.get("nomi", ""))[:200],
                kontragent_stir=str(s.get("stir", ""))[:14],
                rekvizit={k2: h.get(k2) for k2 in ("sotuvchi", "xaridor")},
                qatorlar=list(h.get("qatorlar", [])),
                rejim="qqs" if Decimal(str(h.get("qqs", 0))) > 0 else "aylanma",
                summa=Decimal(str(h.get("summa", 0))),
                qqs=Decimal(str(h.get("qqs", 0))),
                jami=jami,
                operator=k.esf_operator,
                operator_id=oid,
            )
        )
        await db.flush()
        n += 1
    return n


async def kiruvchi_javob(db: AsyncSession, esf_id: int, qabul: bool, sabab: str) -> SoliqEsf:
    e = await _esf(db, esf_id)
    if e.tur != "kiruvchi" or e.holat != "kutilmoqda":
        raise SoliqXato([f"{e.no} ({e.holat}) — javob berib bo'lmaydi"])
    if not qabul and not sabab.strip():
        raise SoliqXato(["Rad etish sababini yozing"])
    try:
        await adapter(e.operator).javob(db, e.operator_id or "", qabul, sabab)
    except OperatorXato as ex:
        raise SoliqXato([f"Operator: {ex}"]) from ex
    e.holat, e.xato, e.javob_at = (
        ("qabul_qilindi", "", _now()) if qabul else ("rad_etildi", sabab.strip()[:500], _now())
    )
    await db.flush()
    return e


async def sinov_kiruvchi(db: AsyncSession, hujjat: dict[str, Any]) -> str:
    """Faqat lokal sinov operatorida: «yetkazib beruvchi ESF yubordi»."""
    k = await korxona(db)
    if k.esf_operator != "sinov":
        raise SoliqXato(["Faqat sinov operatorida"])
    return await SinovOperator().kiruvchi_qosh(db, hujjat)


# ───────────────────────── oylik soliq ─────────────────────────
@dataclass
class OySoliq:
    oy: str
    rejim: str | None
    qqs_foiz: Decimal
    aylanma_foiz: Decimal
    #: QQS bilan sotuv (aylanma): yetkazilgan buyurtmalar + do'kon sotuvi
    aylanma: Decimal
    buyurtma: Decimal
    dokon: Decimal
    #: QQS rejimida: sotuvdagi QQS, qabul qilingan kiruvchi ESF dagi QQS (hisobga olinadi), to'lanadigan
    sotuv_qqs: Decimal
    #: Sotuv QQS ining qismlari: buyurtmalar va do'kon (buxgalteriya 9010 / 9020 dan 6410 ga)
    buyurtma_qqs: Decimal
    dokon_qqs: Decimal
    xarid_qqs: Decimal
    tolanadigan_qqs: Decimal
    #: Aylanma rejimida: aylanma × stavka
    aylanma_soliq: Decimal
    jami_soliq: Decimal


async def oy_soliq(db: AsyncSession, oy: date) -> OySoliq:
    oy = oy.replace(day=1)
    r = await rejim_on(db, oy)
    dan, gacha = _vaqt(oy), _vaqt(keyingi_oy(oy))
    buyurtma = Decimal(
        await db.scalar(
            select(func.coalesce(func.sum(Order.amount), 0)).where(
                Order.delivered_at >= dan,
                Order.delivered_at < gacha,
                Order.status != OrderStatus.CANCELLED,
                Order.is_deleted == False,  # noqa: E712
            )
        )
        or 0
    )
    qatorlar = await ombor.sotuv_qatorlari(db, oy, keyingi_oy(oy))
    dokon = sum((s for s, _ in qatorlar), _0)
    sotuv_qqs = xarid_qqs = aylanma_soliq = buyurtma_qqs = dokon_qqs = _0
    qf = r.qqs_foiz if r else _0
    af = r.aylanma_foiz if r else _0
    if r is not None and r.rejim == "qqs":
        buyurtma_qqs = qqs_ajrat(buyurtma, qf)
        dokon_qqs = sum((qqs_ajrat(s, qf) for s, t in qatorlar if t == "standart"), _0)
        sotuv_qqs = buyurtma_qqs + dokon_qqs
        xarid_qqs = Decimal(
            await db.scalar(
                select(func.coalesce(func.sum(SoliqEsf.qqs), 0)).where(
                    SoliqEsf.tur == "kiruvchi",
                    SoliqEsf.holat == "qabul_qilindi",
                    SoliqEsf.sana >= oy,
                    SoliqEsf.sana < keyingi_oy(oy),
                )
            )
            or 0
        )
    elif r is not None:
        aylanma_soliq = ((buyurtma + dokon) * af / 100).quantize(_Q, ROUND_HALF_UP)
    tolanadigan = sotuv_qqs - xarid_qqs
    return OySoliq(
        oy=f"{oy:%Y-%m}",
        rejim=r.rejim if r else None,
        qqs_foiz=qf,
        aylanma_foiz=af,
        aylanma=buyurtma + dokon,
        buyurtma=buyurtma,
        dokon=dokon,
        sotuv_qqs=sotuv_qqs,
        buyurtma_qqs=buyurtma_qqs,
        dokon_qqs=dokon_qqs,
        xarid_qqs=xarid_qqs,
        tolanadigan_qqs=tolanadigan,
        aylanma_soliq=aylanma_soliq,
        jami_soliq=tolanadigan + aylanma_soliq,
    )


async def kitob(db: AsyncSession, oy: date, tur: str) -> list[SoliqEsf]:
    """QQS kitobi: oy ichidagi qabul qilingan ESF lar (`chiquvchi` — sotuv kitobi, `kiruvchi` — xarid kitobi)."""
    oy = oy.replace(day=1)
    return list(
        (
            await db.execute(
                select(SoliqEsf)
                .where(
                    SoliqEsf.tur == tur,
                    SoliqEsf.holat == "qabul_qilindi",
                    SoliqEsf.sana >= oy,
                    SoliqEsf.sana < keyingi_oy(oy),
                )
                .order_by(SoliqEsf.sana, SoliqEsf.id)
            )
        ).scalars()
    )


async def rejim_boshi(db: AsyncSession) -> date | None:
    return await db.scalar(select(func.min(SoliqRejim.amal_boshi)))
