"""Kassa qoidalari (EKO TZ §7; prototip `kassa-core.js`: validate, makeOp, transfer, voidOp, shiftOpen/Close).

- Hisob qoldig'i = boshlang'ich + orderlar (kirim +, chiqim −; storno orderi manfiy summa bilan o'zini qaytaradi).
- Naqd — faqat ochiq smenada; naqd chiqim kassadagi naqddan oshmaydi; bank/karta chiqimi qoldiqdan (komissiya bilan).
- Buyurtma to'lovi buyurtmaning qolgan summasidan oshmaydi; qarz to'lovi — mijozning qarzidan, eng eski buyurtmadan.
- To'lovdan keyin shu tranzaksiyada rezerv qoidasi (EKO TZ §4.3 B2) — kassirga natija aytiladi.
- Storno — faqat boshqa xodim (ikki kalit), o'tkazma va komissiya guruhi bilan birga.

Funksiyalar chaqiruvchining sessiyasida ishlaydi va `commit` qilmaydi. Rad — `KassaXato` (o'zbekcha).
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import Integer, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client, Order
from app.models.enums import OrderStatus
from app.modules.kassa.models import KassaHisob, KassaModda, KassaOrder, KassaSmena, KassaTaqsimot
from app.modules.ombor import service as ombor

KIRIM_MAQSAD = ("avans", "tolov", "qarz", "sotuv", "boshqa")
CHIQIM_MAQSAD = ("taminotchi", "xarajat", "qaytarish", "inkassatsiya", "boshqa")
_Q = Decimal("0.01")


class KassaXato(Exception):
    def __init__(self, xatolar: list[str]) -> None:
        super().__init__(" · ".join(xatolar))
        self.xatolar = xatolar


@dataclass
class Natija:
    orderlar: list[KassaOrder]
    xabar: str = ""
    qaytim: Decimal | None = None
    #: Rezerv natijasi kassirga: «Material biriktirildi» / «Chegaraga yana N so'm kerak»
    rezerv: list[str] = field(default_factory=list)


def _som(x: Decimal) -> str:
    return f"{x:,.0f}".replace(",", " ")


def _now() -> datetime:
    return datetime.now(UTC)


async def _next_no(db: AsyncSession, prefix: str) -> str:
    """`PKO-2026-0001` — parallel orderlar bir raqam olmasin (tranzaksiya qulfi), raqam son sifatida."""
    p = f"{prefix}-{_now().year}-"
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(p))))
    col = KassaSmena.no if prefix == "SM" else KassaOrder.guruh if prefix == "GR" else KassaOrder.no
    last = await db.scalar(select(func.max(cast(func.split_part(col, "-", 3), Integer))).where(col.like(f"{p}%")))
    return f"{p}{(last or 0) + 1:04d}"


async def hisob(db: AsyncSession, kod: str, lock: bool = False) -> KassaHisob:
    q = select(KassaHisob).where(KassaHisob.kod == kod, KassaHisob.faol == True)  # noqa: E712
    h = (await db.execute(q.with_for_update() if lock else q)).scalar_one_or_none()
    if h is None:
        raise KassaXato([f"«{kod}» hisobi yo'q"])
    return h


async def qoldiq(db: AsyncSession, h: KassaHisob) -> Decimal:
    s = await db.scalar(
        select(
            func.coalesce(func.sum(case((KassaOrder.tur == "kirim", KassaOrder.summa), else_=-KassaOrder.summa)), 0)
        ).where(KassaOrder.hisob_id == h.id)
    )
    return h.boshlangich + Decimal(s or 0)


async def ochiq_smena(db: AsyncSession, lock: bool = False) -> KassaSmena | None:
    naqd = await hisob(db, "naqd")
    q = select(KassaSmena).where(KassaSmena.hisob_id == naqd.id, KassaSmena.yopilgan_at.is_(None))
    return (await db.execute(q.with_for_update() if lock else q)).scalar_one_or_none()


def kupyura_jami(kupyura: dict[str, int]) -> Decimal:
    return sum((Decimal(nom) * int(n) for nom, n in kupyura.items() if int(n) > 0), Decimal(0))


# ───────────────────────── smena ─────────────────────────
async def smena_och(db: AsyncSession, kupyura: dict[str, int], user_id: int | None) -> tuple[KassaSmena, Decimal]:
    """Smenani ochadi. Birinchi smenada sanalgan naqd — kassaning boshlang'ich qoldig'i; keyingilarida kitob bilan
    farq qaytariladi (kassirga ko'rsatiladi, yopishda farq orderi yoziladi)."""
    naqd = await hisob(db, "naqd", lock=True)
    if await ochiq_smena(db) is not None:
        raise KassaXato(["Smena allaqachon ochiq"])
    sanaldi = kupyura_jami(kupyura)
    birinchi = (
        await db.scalar(select(KassaSmena.id).limit(1)) is None
        and await db.scalar(select(KassaOrder.id).where(KassaOrder.hisob_id == naqd.id).limit(1)) is None
    )
    if birinchi:
        naqd.boshlangich = sanaldi
    kitob = await qoldiq(db, naqd)
    sm = KassaSmena(
        no=await _next_no(db, "SM"),
        hisob_id=naqd.id,
        ochgan_id=user_id,
        ochilgan_at=_now(),
        ochilish_naqd=sanaldi,
        ochilish_kitob=kitob,
        ochilish_kupyura=kupyura,
    )
    db.add(sm)
    await db.flush()
    return sm, sanaldi - kitob


async def smena_hisobi(db: AsyncSession, sm: KassaSmena) -> dict[str, Decimal]:
    """Smenadagi naqd kirim/chiqim (storno ham) va kutilgan qoldiq; karta tushumi."""
    naqd = await hisob(db, "naqd")
    rows = (
        await db.execute(
            select(KassaOrder.hisob_id, KassaOrder.tur, func.sum(KassaOrder.summa))
            .where(KassaOrder.smena_id == sm.id)
            .group_by(KassaOrder.hisob_id, KassaOrder.tur)
        )
    ).all()
    karta = await hisob(db, "karta")
    kirim = sum((Decimal(s) for h, t, s in rows if h == naqd.id and t == "kirim"), Decimal(0))
    chiqim = sum((Decimal(s) for h, t, s in rows if h == naqd.id and t == "chiqim"), Decimal(0))
    karta_kirim = sum((Decimal(s) for h, t, s in rows if h == karta.id and t == "kirim"), Decimal(0))
    return {"kirim": kirim, "chiqim": chiqim, "kutilgan": sm.ochilish_naqd + kirim - chiqim, "karta": karta_kirim}


async def smena_yop(
    db: AsyncSession, kupyura: dict[str, int], terminal_z: Decimal | None, user_id: int | None
) -> KassaSmena:
    sm = await ochiq_smena(db, lock=True)
    if sm is None:
        raise KassaXato(["Ochiq smena yo'q"])
    st = await smena_hisobi(db, sm)
    sanaldi = kupyura_jami(kupyura)
    farq = sanaldi - st["kutilgan"]
    if abs(farq) >= 1:
        naqd = await hisob(db, "naqd")
        tur = "kirim" if farq > 0 else "chiqim"
        db.add(
            KassaOrder(
                no=await _next_no(db, "PKO" if tur == "kirim" else "RKO"),
                tur=tur,
                maqsad="farq",
                hisob_id=naqd.id,
                summa=abs(farq),
                smena_id=sm.id,
                kontragent="",
                izoh="Smena yopilishida ortiqcha" if farq > 0 else "Smena yopilishida kamomad",
                kassir_id=user_id,
            )
        )
    sm.yopgan_id, sm.yopilgan_at = user_id, _now()
    sm.yopilish_naqd, sm.yopilish_kupyura = sanaldi, kupyura
    sm.kirim, sm.chiqim, sm.kutilgan, sm.farq = st["kirim"], st["chiqim"], st["kutilgan"], farq
    sm.terminal_z, sm.karta_tushum = terminal_z, st["karta"]
    await db.flush()
    return sm


# ───────────────────────── buyurtma to'lovlari ─────────────────────────
async def tolangan(db: AsyncSession, order_ids: list[int]) -> dict[int, Decimal]:
    """Buyurtmalar bo'yicha kassadan to'langan (qaytarish va storno ayirilgan)."""
    if not order_ids:
        return {}
    rows = (
        await db.execute(
            select(KassaTaqsimot.order_id, func.sum(KassaTaqsimot.summa))
            .where(KassaTaqsimot.order_id.in_(order_ids))
            .group_by(KassaTaqsimot.order_id)
        )
    ).all()
    return {oid: Decimal(s) for oid, s in rows}


async def jami_tolangan(db: AsyncSession, order: Order) -> Decimal:
    """Kassagacha qo'lda yozilgan (`advance_payment`, o'tish davri) + kassa."""
    return (order.advance_payment or Decimal(0)) + (await tolangan(db, [order.id])).get(order.id, Decimal(0))


async def qolgan(db: AsyncSession, order: Order) -> Decimal | None:
    if order.amount is None:
        return None
    return max(order.amount - await jami_tolangan(db, order), Decimal(0))


async def mijoz_qarzlari(db: AsyncSession, client_id: int) -> list[tuple[Order, Decimal]]:
    """Mijozning to'lanmagan buyurtmalari, eng eskisi birinchi: [(buyurtma, qolgan)]."""
    orders = list(
        (
            await db.execute(
                select(Order)
                .where(
                    Order.client_id == client_id,
                    Order.status != OrderStatus.CANCELLED,
                    Order.is_deleted == False,  # noqa: E712
                    Order.amount.is_not(None),
                )
                .order_by(Order.created_at, Order.id)
            )
        ).scalars()
    )
    paid = await tolangan(db, [o.id for o in orders])
    out = []
    for o in orders:
        q = (o.amount or Decimal(0)) - (o.advance_payment or Decimal(0)) - paid.get(o.id, Decimal(0))
        if q > Decimal("0.5"):
            out.append((o, q))
    return out


async def _rezerv_xabar(db: AsyncSession, order: Order) -> str:
    """To'lovdan keyin rezerv qoidasi (B2) va kassirga xabar."""
    await ombor.on_payment_changed(db, order)
    holat = await ombor.rezerv_holati(db, order)
    if holat is None:
        return ""
    paid, chegara, yechildi = holat
    if yechildi:
        return f"{order.number}: material biriktirildi"
    return f"{order.number}: chegaraga yana {_som(max(chegara - paid, Decimal(0)))} so'm kerak"


# ───────────────────────── orderlar ─────────────────────────
@dataclass
class Tolov:
    hisob_kod: str
    summa: Decimal
    valyuta_summa: Decimal | None = None
    kurs: Decimal | None = None


async def _hisob_tekshir(db: AsyncSession, tolovlar: list[Tolov], xato: list[str]) -> dict[str, KassaHisob]:
    hisoblar: dict[str, KassaHisob] = {}
    for t in tolovlar:
        if t.summa <= 0:
            xato.append("Summani kiriting")
        try:
            hisoblar[t.hisob_kod] = await hisob(db, t.hisob_kod, lock=True)
        except KassaXato as e:
            xato += e.xatolar
    return hisoblar


async def kirim(
    db: AsyncSession,
    *,
    maqsad: str,
    tolovlar: list[Tolov],
    user_id: int | None,
    order_id: int | None = None,
    client_id: int | None = None,
    stock_doc_id: int | None = None,
    kontragent: str = "",
    izoh: str = "",
    mijoz_berdi: Decimal | None = None,
) -> Natija:
    xato: list[str] = []
    if maqsad not in KIRIM_MAQSAD:
        raise KassaXato([f"Noma'lum kirim turi: {maqsad}"])
    hisoblar = await _hisob_tekshir(db, tolovlar, xato)
    jami = sum((t.summa for t in tolovlar), Decimal(0))
    naqd = sum((t.summa for t in tolovlar if t.hisob_kod == "naqd"), Decimal(0))
    sm = await ochiq_smena(db)
    if naqd > 0 and sm is None:
        xato.append("Naqd pul uchun avval smenani oching")
    order: Order | None = None
    taqsim: list[tuple[Order, Decimal]] = []
    if maqsad in ("avans", "tolov"):
        order = await db.get(Order, order_id, with_for_update=True) if order_id else None
        if order is None or order.is_deleted:
            xato.append("Buyurtmani tanlang")
        else:
            qol = await qolgan(db, order)
            if qol is not None and jami > qol + Decimal("0.5"):
                xato.append(f"{order.number} bo'yicha qolgan {_som(qol)} so'm — undan ko'p olib bo'lmaydi")
            taqsim = [(order, jami)]
            client_id = order.client_id
    elif maqsad == "qarz":
        if client_id is None:
            xato.append("Mijozni tanlang")
        else:
            qarzlar = await mijoz_qarzlari(db, client_id)
            qarz = sum((q for _, q in qarzlar), Decimal(0))
            if qarz <= Decimal("0.5"):
                xato.append("Mijozning qarzi yo'q")
            elif jami > qarz + Decimal("0.5"):
                xato.append(f"Mijoz qarzi {_som(qarz)} so'm — undan ko'p olib bo'lmaydi")
            rest = jami
            for qo, q in qarzlar:  # eng eskisidan yopiladi
                if rest <= 0:
                    break
                x = min(q, rest)
                taqsim.append((qo, x))
                rest -= x
    qaytim = None
    if mijoz_berdi is not None:
        if mijoz_berdi < naqd:
            xato.append("Mijoz bergan pul naqd summadan kam")
        qaytim = mijoz_berdi - naqd
    if not kontragent.strip():
        cid = client_id or (order.client_id if order else None)
        cl = await db.get(Client, cid) if cid else None
        kontragent = cl.full_name if cl else ""
    if not kontragent.strip() and maqsad != "boshqa":
        xato.append("Kimdan olinayotganini yozing")
    if xato:
        raise KassaXato(xato)

    guruh = await _next_no(db, "GR") if len(tolovlar) > 1 else None
    orderlar = []
    rest_taqsim = list(taqsim)
    for t in tolovlar:
        o = KassaOrder(
            no=await _next_no(db, "PKO"),
            tur="kirim",
            maqsad=maqsad,
            hisob_id=hisoblar[t.hisob_kod].id,
            summa=t.summa.quantize(_Q, ROUND_HALF_UP),
            valyuta_summa=t.valyuta_summa,
            kurs=t.kurs,
            smena_id=sm.id if sm else None,
            order_id=order.id if order else None,
            client_id=client_id,
            stock_doc_id=stock_doc_id,
            kontragent=kontragent.strip()[:150],
            izoh=izoh.strip()[:300],
            guruh=guruh,
            mijoz_berdi=mijoz_berdi if t.hisob_kod == "naqd" else None,
            qaytim=qaytim if t.hisob_kod == "naqd" else None,
            kassir_id=user_id,
        )
        db.add(o)
        await db.flush()
        orderlar.append(o)
        # Taqsimot: shu qismning summasi buyurtmalarga ketma-ket (eng eskisidan)
        qism = o.summa
        while qism > 0 and rest_taqsim:
            bo, x = rest_taqsim[0]
            y = min(x, qism)
            db.add(KassaTaqsimot(kassa_order_id=o.id, order_id=bo.id, summa=y))
            qism -= y
            rest_taqsim[0] = (bo, x - y)
            if rest_taqsim[0][1] <= 0:
                rest_taqsim.pop(0)
    await db.flush()
    rezerv = [m for bo, _ in taqsim if (m := await _rezerv_xabar(db, bo))]
    return Natija(
        orderlar=orderlar, qaytim=qaytim, rezerv=rezerv, xabar=f"{orderlar[0].no}: {_som(jami)} so'm qabul qilindi"
    )


async def chiqim(
    db: AsyncSession,
    *,
    maqsad: str,
    hisob_kod: str,
    summa: Decimal,
    user_id: int | None,
    kontragent: str = "",
    turkum: str = "",
    izoh: str = "",
    order_id: int | None = None,
) -> Natija:
    xato: list[str] = []
    if maqsad not in CHIQIM_MAQSAD:
        raise KassaXato([f"Noma'lum chiqim turi: {maqsad}"])
    h = await hisob(db, hisob_kod, lock=True)
    if summa <= 0:
        xato.append("Summani kiriting")
    sm = await ochiq_smena(db)
    komissiya = (summa * h.komissiya_foiz / 100).quantize(Decimal(1), ROUND_HALF_UP) if h.tur != "naqd" else Decimal(0)
    bor = await qoldiq(db, h)
    if h.tur == "naqd" and sm is None:
        xato.append("Naqd pul uchun avval smenani oching")
    if bor - summa - komissiya < Decimal("-0.5"):
        kerak = f" (komissiya bilan {_som(summa + komissiya)} kerak)" if komissiya else ""
        xato.append(f"{h.nom} da yetarli mablag' yo'q — bor: {_som(bor)} so'm{kerak}")
    order: Order | None = None
    if maqsad == "qaytarish":
        order = await db.get(Order, order_id, with_for_update=True) if order_id else None
        if order is None:
            xato.append("Qaytariladigan buyurtmani tanlang")
        else:
            tol = (await tolangan(db, [order.id])).get(order.id, Decimal(0))
            if summa > tol + Decimal("0.5"):
                xato.append(f"{order.number} bo'yicha kassadan {_som(tol)} so'm to'langan — undan ko'p qaytmaydi")
            if not kontragent.strip():
                cl = await db.get(Client, order.client_id)
                kontragent = cl.full_name if cl else ""
    if maqsad == "xarajat" and not turkum.strip():
        xato.append("Xarajat turkumini tanlang")
    elif maqsad == "xarajat" and turkum.strip() not in {m.nom for m in await moddalar(db)}:
        xato.append(f"«{turkum.strip()}» moddasi yo'q yoki o'chirilgan")
    if not kontragent.strip() and maqsad not in ("xarajat", "boshqa"):
        xato.append("Kimga berilayotganini yozing")
    if xato:
        raise KassaXato(xato)
    guruh = await _next_no(db, "GR") if komissiya > 0 else None
    o = KassaOrder(
        no=await _next_no(db, "RKO"),
        tur="chiqim",
        maqsad=maqsad,
        hisob_id=h.id,
        summa=summa.quantize(_Q, ROUND_HALF_UP),
        smena_id=sm.id if sm else None,
        order_id=order.id if order else None,
        client_id=order.client_id if order else None,
        kontragent=kontragent.strip()[:150],
        turkum=turkum.strip()[:60],
        izoh=izoh.strip()[:300],
        guruh=guruh,
        kassir_id=user_id,
    )
    db.add(o)
    await db.flush()
    orderlar = [o]
    if komissiya > 0:
        k = KassaOrder(
            no=await _next_no(db, "RKO"),
            tur="chiqim",
            maqsad="komissiya",
            hisob_id=h.id,
            summa=komissiya,
            smena_id=sm.id if sm else None,
            kontragent=h.nom,
            turkum="Bank komissiyasi",
            izoh=f"{o.no} uchun komissiya",
            guruh=guruh,
            kassir_id=user_id,
        )
        db.add(k)
        orderlar.append(k)
    rezerv = []
    if order is not None:
        db.add(KassaTaqsimot(kassa_order_id=o.id, order_id=order.id, summa=-o.summa))
        await db.flush()
        if m := await _rezerv_xabar(db, order):
            rezerv.append(m)
    await db.flush()
    return Natija(orderlar=orderlar, rezerv=rezerv, xabar=f"{o.no}: {_som(summa)} so'm berildi")


async def otkazma(db: AsyncSession, dan: str, ga: str, summa: Decimal, user_id: int | None, izoh: str = "") -> Natija:
    """Hisobdan hisobga (inkassatsiya, kassadan bankka): ikki order bitta guruhda."""
    if dan == ga:
        raise KassaXato(["Bir hisobning o'ziga o'tkazib bo'lmaydi"])
    a, b = await hisob(db, dan, lock=True), await hisob(db, ga, lock=True)
    sm = await ochiq_smena(db)
    xato = []
    if summa <= 0:
        xato.append("Summani kiriting")
    if "naqd" in (a.tur, b.tur) and sm is None:
        xato.append("Naqd pul uchun avval smenani oching")
    if await qoldiq(db, a) - summa < Decimal("-0.5"):
        xato.append(f"{a.nom} da yetarli mablag' yo'q")
    if xato:
        raise KassaXato(xato)
    guruh = await _next_no(db, "GR")
    orderlar = []
    for tur, h in (("chiqim", a), ("kirim", b)):
        o = KassaOrder(
            no=await _next_no(db, "RKO" if tur == "chiqim" else "PKO"),
            tur=tur,
            maqsad="otkazma",
            hisob_id=h.id,
            summa=summa.quantize(_Q, ROUND_HALF_UP),
            smena_id=sm.id if sm else None,
            kontragent=f"{a.nom} → {b.nom}",
            izoh=izoh.strip()[:300],
            guruh=guruh,
            kassir_id=user_id,
        )
        db.add(o)
        orderlar.append(o)
    await db.flush()
    return Natija(orderlar=orderlar, xabar=f"{a.nom} → {b.nom}: {_som(summa)} so'm")


async def storno(db: AsyncSession, kassa_order_id: int, user_id: int | None, sabab: str) -> Natija:
    """Xato orderni teskari order bilan bekor qiladi (Moliya). Ikki kalit: orderni yozgan xodim o'zi storno
    qilolmaydi. O'tkazma va komissiya — guruhi bilan birga."""
    asl = await db.get(KassaOrder, kassa_order_id, with_for_update=True)
    if asl is None:
        raise KassaXato(["Order topilmadi"])
    xato = []
    if asl.storno_of_id is not None:
        xato.append(f"{asl.no} — o'zi storno orderi")
    if not sabab.strip():
        xato.append("Storno sababini yozing")
    if user_id is not None and user_id == asl.kassir_id:
        xato.append("Ikki kalit qoidasi: orderni yozgan xodim uni o'zi storno qilolmaydi")
    # O'tkazma ikki oyog'i va chiqim komissiyasi ajralmas — birga; aralash to'lov qismlari esa alohida
    guruh = [asl]
    if asl.guruh:
        butun = list((await db.execute(select(KassaOrder).where(KassaOrder.guruh == asl.guruh))).scalars())
        if any(g.maqsad in ("otkazma", "komissiya") for g in butun):
            guruh = butun
    bor = set(
        (
            await db.execute(select(KassaOrder.storno_of_id).where(KassaOrder.storno_of_id.in_([g.id for g in guruh])))
        ).scalars()
    )
    if asl.id in bor:
        xato.append(f"{asl.no} allaqachon storno qilingan")
    if xato:
        raise KassaXato(xato)
    sm = await ochiq_smena(db)
    orderlar = []
    tegishli: set[int] = set()
    for g in guruh:
        if g.id in bor or g.storno_of_id is not None:
            continue
        s = KassaOrder(
            no=await _next_no(db, "PKO" if g.tur == "kirim" else "RKO"),
            tur=g.tur,
            maqsad=g.maqsad,
            hisob_id=g.hisob_id,
            summa=-g.summa,
            smena_id=sm.id if sm else None,
            order_id=g.order_id,
            client_id=g.client_id,
            kontragent=g.kontragent,
            turkum=g.turkum,
            izoh=f"Storno {g.no}: {sabab.strip()}"[:300],
            guruh=g.guruh,
            kassir_id=user_id,
            storno_of_id=g.id,
        )
        db.add(s)
        await db.flush()
        orderlar.append(s)
        for t in (await db.execute(select(KassaTaqsimot).where(KassaTaqsimot.kassa_order_id == g.id))).scalars():
            db.add(KassaTaqsimot(kassa_order_id=s.id, order_id=t.order_id, summa=-t.summa))
            tegishli.add(t.order_id)
    await db.flush()
    rezerv = []
    for oid in tegishli:
        o = await db.get(Order, oid)
        if o is not None and (m := await _rezerv_xabar(db, o)):
            rezerv.append(m)
    return Natija(orderlar=orderlar, rezerv=rezerv, xabar=f"{asl.no} storno qilindi")


async def hisob_qoldiqlari(db: AsyncSession) -> list[dict[str, Any]]:
    out = []
    for h in (await db.execute(select(KassaHisob).where(KassaHisob.faol == True).order_by(KassaHisob.id))).scalars():  # noqa: E712
        out.append({"kod": h.kod, "nom": h.nom, "tur": h.tur, "qoldiq": await qoldiq(db, h)})
    return out


# ───────────────────────── moddalar va sozlama (Moliya) ─────────────────────────
async def moddalar(db: AsyncSession, faqat_faol: bool = True) -> list[KassaModda]:
    q = select(KassaModda).order_by(KassaModda.tartib, KassaModda.id)
    if faqat_faol:
        q = q.where(KassaModda.faol == True)  # noqa: E712
    return list((await db.execute(q)).scalars())


async def modda_saqla(
    db: AsyncSession, nom: str, oylik_limit: Decimal | None, faol: bool, modda_id: int | None = None
) -> KassaModda:
    nom = " ".join(nom.split())
    if not nom:
        raise KassaXato(["Modda nomini yozing"])
    band = await db.scalar(select(KassaModda.id).where(func.lower(KassaModda.nom) == nom.lower()))
    if band is not None and band != modda_id:
        raise KassaXato([f"«{nom}» moddasi allaqachon bor"])
    if modda_id is None:
        tartib = await db.scalar(select(func.coalesce(func.max(KassaModda.tartib), 0)))
        m = KassaModda(nom=nom, oylik_limit=oylik_limit, faol=faol, tartib=int(tartib or 0) + 1)
        db.add(m)
    else:
        found = await db.get(KassaModda, modda_id)
        if found is None:
            raise KassaXato(["Modda topilmadi"])
        m = found
        m.nom, m.oylik_limit, m.faol = nom, oylik_limit, faol
    await db.flush()
    return m


async def hisob_sozla(
    db: AsyncSession, kod: str, boshlangich: Decimal | None, komissiya_foiz: Decimal | None
) -> KassaHisob:
    """Boshlang'ich qoldiq — faqat karta/bank va faqat hali order yo'q paytda (naqd — birinchi smenadan)."""
    h = await hisob(db, kod, lock=True)
    if boshlangich is not None and boshlangich != h.boshlangich:
        if h.tur == "naqd":
            raise KassaXato(["Naqd kassa boshlang'ichi birinchi smenada sanalgan puldan olinadi"])
        if await db.scalar(select(KassaOrder.id).where(KassaOrder.hisob_id == h.id).limit(1)) is not None:
            raise KassaXato([f"{h.nom} da orderlar bor — boshlang'ich qoldiq endi o'zgarmaydi"])
        h.boshlangich = boshlangich
    if komissiya_foiz is not None:
        h.komissiya_foiz = komissiya_foiz
    await db.flush()
    return h


@dataclass
class OrderQator:
    """Moliya hisobotlari uchun order (mahalliy sana bilan)."""

    id: int
    no: str
    sana: datetime
    tur: str
    maqsad: str
    hisob: str
    summa: Decimal
    turkum: str
    kontragent: str
    client_id: int | None
    order_id: int | None
    kassir_id: int | None
    smena_id: int | None
    storno_of_id: int | None
    izoh: str


async def orderlar_davr(
    db: AsyncSession, dan: datetime | None = None, gacha: datetime | None = None, client_id: int | None = None
) -> list[OrderQator]:
    """[dan, gacha) oralig'idagi orderlar (storno ham), eskisi birinchi."""
    kod = {h.id: h.kod for h in (await db.execute(select(KassaHisob))).scalars()}
    q = select(KassaOrder).order_by(KassaOrder.id)
    if dan is not None:
        q = q.where(KassaOrder.created_at >= dan)
    if gacha is not None:
        q = q.where(KassaOrder.created_at < gacha)
    if client_id is not None:
        q = q.where(KassaOrder.client_id == client_id)
    return [
        OrderQator(
            o.id,
            o.no,
            o.created_at,
            o.tur,
            o.maqsad,
            kod.get(o.hisob_id, ""),
            o.summa,
            o.turkum,
            o.kontragent,
            o.client_id,
            o.order_id,
            o.kassir_id,
            o.smena_id,
            o.storno_of_id,
            o.izoh,
        )
        for o in (await db.execute(q)).scalars()
    ]


async def ochiq_smenalar(db: AsyncSession) -> list[KassaSmena]:
    return list((await db.execute(select(KassaSmena).where(KassaSmena.yopilgan_at.is_(None)))).scalars())
