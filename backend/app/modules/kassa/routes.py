"""Kassa API — `/kassa/...` (EKO TZ §7). Kassir va direktor; storno — Moliya (direktor, ikki kalit)."""

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import aliased

from app.api.deps import SessionDep, client_ip, require_roles
from app.crud import log_action
from app.models import Client, Order, User
from app.models.enums import OrderStatus, UserRole
from app.modules.kassa import services as k
from app.modules.kassa.models import KassaHisob, KassaOrder, KassaSmena
from app.modules.kassa.schemas import (
    AmalNatija,
    ChiqimIn,
    HisobRead,
    KassaOrderRead,
    KirimIn,
    NavbatRow,
    OtkazmaIn,
    SmenaHolat,
    SmenaOchIn,
    SmenaRead,
    SmenaYopIn,
    StornoIn,
)
from app.modules.ombor import service as ombor

router = APIRouter(prefix="/kassa", tags=["kassa"])

KassaUser = Annotated[User, Depends(require_roles(UserRole.KASSIR, UserRole.DIRECTOR))]
#: O'qish — kassir, direktor va moliyachi (Moliya jurnali va smenalar shu yo'llardan)
KassaReadUser = Annotated[User, Depends(require_roles(UserRole.KASSIR, UserRole.DIRECTOR, UserRole.MOLIYACHI))]
#: Storno — Moliya: direktor va moliyachi (ikki kalit servisda)
MoliyaUser = Annotated[User, Depends(require_roles(UserRole.DIRECTOR, UserRole.MOLIYACHI))]


def _bad(e: k.KassaXato) -> HTTPException:
    return HTTPException(status_code=422, detail=" · ".join(e.xatolar))


async def _smena_read(db: SessionDep, sm: KassaSmena) -> SmenaRead:
    names = {
        u.id: (u.name or u.username)
        for u in (
            await db.execute(select(User).where(User.id.in_([x for x in (sm.ochgan_id, sm.yopgan_id) if x])))
        ).scalars()
    }
    return SmenaRead.model_validate(sm).model_copy(
        update={"ochgan": names.get(sm.ochgan_id or 0), "yopgan": names.get(sm.yopgan_id or 0)}
    )


async def _orders_read(db: SessionDep, rows: list[KassaOrder]) -> list[KassaOrderRead]:
    ids = [o.id for o in rows]
    if not ids:
        return []
    hisob = {h.id: h.kod for h in (await db.execute(select(KassaHisob))).scalars()}
    nums = dict(
        (await db.execute(select(Order.id, Order.number).where(Order.id.in_({o.order_id for o in rows if o.order_id}))))
        .tuples()
        .all()
    )
    smena = dict(
        (
            await db.execute(
                select(KassaSmena.id, KassaSmena.no).where(KassaSmena.id.in_({o.smena_id for o in rows if o.smena_id}))
            )
        )
        .tuples()
        .all()
    )
    users = {
        u.id: (u.name or u.username)
        for u in (
            await db.execute(select(User).where(User.id.in_({o.kassir_id for o in rows if o.kassir_id})))
        ).scalars()
    }
    st = dict(
        (await db.execute(select(KassaOrder.storno_of_id, KassaOrder.no).where(KassaOrder.storno_of_id.in_(ids))))
        .tuples()
        .all()
    )
    return [
        KassaOrderRead.model_validate(o).model_copy(
            update={
                "hisob": hisob.get(o.hisob_id),
                "order_number": nums.get(o.order_id or 0),
                "smena_no": smena.get(o.smena_id or 0),
                "kassir": users.get(o.kassir_id or 0),
                "storno_no": st.get(o.id),
            }
        )
        for o in rows
    ]


async def _natija(db: SessionDep, n: k.Natija) -> AmalNatija:
    return AmalNatija(orderlar=await _orders_read(db, n.orderlar), xabar=n.xabar, qaytim=n.qaytim, rezerv=n.rezerv)


@router.get("/holat", response_model=SmenaHolat, operation_id="kassa_holat")
async def kassa_holat(db: SessionDep, _: KassaUser) -> SmenaHolat:
    sm = await k.ochiq_smena(db)
    hisoblar = [HisobRead(**h) for h in await k.hisob_qoldiqlari(db)]
    if sm is None:
        return SmenaHolat(smena=None, hisoblar=hisoblar)
    st = await k.smena_hisobi(db, sm)
    return SmenaHolat(
        smena=await _smena_read(db, sm),
        kirim=st["kirim"],
        chiqim=st["chiqim"],
        kutilgan=st["kutilgan"],
        karta=st["karta"],
        ochilish_farq=sm.ochilish_naqd - sm.ochilish_kitob,
        hisoblar=hisoblar,
    )


@router.post("/smena/ochish", response_model=SmenaRead, operation_id="kassa_smena_och")
async def kassa_smena_och(db: SessionDep, user: KassaUser, body: SmenaOchIn, request: Request) -> SmenaRead:
    try:
        sm, farq = await k.smena_och(db, body.kupyura, user.id)
    except k.KassaXato as e:
        await db.rollback()
        raise _bad(e) from e
    log_action(
        db,
        module="kassa",
        action="smena_ochildi",
        user_id=user.id,
        message=f"{sm.no}: sanaldi {sm.ochilish_naqd}, kitob {sm.ochilish_kitob}, farq {farq}",
        ip=client_ip(request),
    )
    await db.commit()
    return await _smena_read(db, sm)


@router.post("/smena/yopish", response_model=SmenaRead, operation_id="kassa_smena_yop")
async def kassa_smena_yop(db: SessionDep, user: KassaUser, body: SmenaYopIn, request: Request) -> SmenaRead:
    try:
        sm = await k.smena_yop(db, body.kupyura, body.terminal_z, user.id)
    except k.KassaXato as e:
        await db.rollback()
        raise _bad(e) from e
    log_action(
        db,
        module="kassa",
        action="smena_yopildi",
        user_id=user.id,
        message=f"{sm.no}: kutilgan {sm.kutilgan}, sanaldi {sm.yopilish_naqd}, farq {sm.farq}",
        ip=client_ip(request),
    )
    await db.commit()
    return await _smena_read(db, sm)


@router.get("/smenalar", response_model=list[SmenaRead], operation_id="kassa_smenalar")
async def kassa_smenalar(db: SessionDep, _: KassaReadUser, limit: int = Query(30, ge=1, le=500)) -> list[SmenaRead]:
    rows = (await db.execute(select(KassaSmena).order_by(KassaSmena.id.desc()).limit(limit))).scalars()
    return [await _smena_read(db, s) for s in rows]


@router.get("/navbat", response_model=list[NavbatRow], operation_id="kassa_navbat")
async def kassa_navbat(db: SessionDep, _: KassaUser, q: Annotated[str, Query(max_length=60)] = "") -> list[NavbatRow]:
    """To'lov kutayotgan buyurtmalar: summasi bor, qolgani > 0. Qidiruv — raqam, mijoz ismi, telefon."""
    cl = aliased(Client)
    stmt = (
        select(Order, cl)
        .join(cl, cl.id == Order.client_id)
        .where(
            Order.is_deleted == False,  # noqa: E712
            Order.amount.is_not(None),
            Order.status.not_in([OrderStatus.CANCELLED, OrderStatus.DRAFT]),
        )
        .order_by(Order.id.desc())
        .limit(200)
    )
    if q.strip():
        t = f"%{q.strip()}%"
        stmt = stmt.where(or_(Order.number.ilike(t), cl.full_name.ilike(t), cl.phone.ilike(t)))
    rows = (await db.execute(stmt)).all()
    paid = await k.tolangan(db, [o.id for o, _ in rows])
    out = []
    # Ochilish qarzi (tizimga o'tishdagi) — «Qarzni to'lash» bilan yopiladi; order_id manfiy = mijoz id
    tol0 = await k.ochilish_tolangan(db)
    jami0: dict[int, Decimal] = {}
    for r in await k.ochilishlar(db):
        if r.tur == "mijoz" and r.client_id is not None:
            jami0[r.client_id] = jami0.get(r.client_id, Decimal(0)) + r.summa
    for c in (await db.execute(select(Client).where(Client.id.in_(jami0)))).scalars():
        qol0 = jami0[c.id] - tol0.get(c.id, Decimal(0))
        t = q.strip().lower()
        if qol0 > Decimal("0.5") and (not t or t in c.full_name.lower() or t in (c.phone or "")):
            out.append(
                NavbatRow(
                    order_id=-c.id,
                    order_number="Ochilish qarzi",
                    client_id=c.id,
                    mijoz=c.full_name,
                    telefon=c.phone,
                    summa=jami0[c.id],
                    tolangan=tol0.get(c.id, Decimal(0)),
                    qolgan=qol0,
                    chegara=None,
                    chegaraga_kerak=None,
                    holat="ochilish",
                )
            )
    for o, c in rows:
        tol = (o.advance_payment or Decimal(0)) + paid.get(o.id, Decimal(0))
        qol = (o.amount or Decimal(0)) - tol
        if qol <= Decimal("0.5"):
            continue
        rh = await ombor.rezerv_holati(db, o)
        out.append(
            NavbatRow(
                order_id=o.id,
                order_number=o.number,
                client_id=c.id,
                mijoz=c.full_name,
                telefon=c.phone,
                summa=o.amount or Decimal(0),
                tolangan=tol,
                qolgan=qol,
                chegara=rh[1] if rh else None,
                chegaraga_kerak=max(rh[1] - rh[0], Decimal(0)) if rh else None,
                holat=o.status.value,
            )
        )
    return out


@router.post("/kirim", response_model=AmalNatija, operation_id="kassa_kirim")
async def kassa_kirim(db: SessionDep, user: KassaUser, body: KirimIn, request: Request) -> AmalNatija:
    try:
        n = await k.kirim(
            db,
            maqsad=body.maqsad,
            tolovlar=[k.Tolov(t.hisob, t.summa, t.valyuta_summa, t.kurs) for t in body.tolovlar],
            user_id=user.id,
            order_id=body.order_id,
            client_id=body.client_id,
            stock_doc_id=body.stock_doc_id,
            kontragent=body.kontragent,
            izoh=body.izoh,
            mijoz_berdi=body.mijoz_berdi,
        )
    except k.KassaXato as e:
        await db.rollback()
        raise _bad(e) from e
    log_action(db, module="kassa", action="kirim", user_id=user.id, message=n.xabar[:500], ip=client_ip(request))
    await db.commit()
    return await _natija(db, n)


@router.post("/chiqim", response_model=AmalNatija, operation_id="kassa_chiqim")
async def kassa_chiqim(db: SessionDep, user: KassaUser, body: ChiqimIn, request: Request) -> AmalNatija:
    try:
        n = await k.chiqim(
            db,
            maqsad=body.maqsad,
            hisob_kod=body.hisob,
            summa=body.summa,
            user_id=user.id,
            kontragent=body.kontragent,
            turkum=body.turkum,
            izoh=body.izoh,
            order_id=body.order_id,
        )
    except k.KassaXato as e:
        await db.rollback()
        raise _bad(e) from e
    log_action(db, module="kassa", action="chiqim", user_id=user.id, message=n.xabar[:500], ip=client_ip(request))
    await db.commit()
    return await _natija(db, n)


@router.post("/otkazma", response_model=AmalNatija, operation_id="kassa_otkazma")
async def kassa_otkazma(db: SessionDep, user: KassaUser, body: OtkazmaIn, request: Request) -> AmalNatija:
    try:
        n = await k.otkazma(db, body.dan, body.ga, body.summa, user.id, body.izoh)
    except k.KassaXato as e:
        await db.rollback()
        raise _bad(e) from e
    log_action(db, module="kassa", action="otkazma", user_id=user.id, message=n.xabar[:500], ip=client_ip(request))
    await db.commit()
    return await _natija(db, n)


@router.get("/orderlar", response_model=list[KassaOrderRead], operation_id="kassa_orderlar")
async def kassa_orderlar(
    db: SessionDep,
    _: KassaReadUser,
    smena_id: int | None = None,
    order_id: int | None = None,
    q: Annotated[str, Query(max_length=60)] = "",
    limit: int = Query(200, ge=1, le=2000),
) -> list[KassaOrderRead]:
    """Orderlar jurnali: smena, buyurtma yoki qidiruv (order №, kontragent) bo'yicha."""
    stmt: Any = select(KassaOrder).order_by(KassaOrder.id.desc()).limit(limit)
    if smena_id is not None:
        stmt = stmt.where(KassaOrder.smena_id == smena_id)
    if order_id is not None:
        stmt = stmt.where(KassaOrder.order_id == order_id)
    if q.strip():
        t = f"%{q.strip()}%"
        stmt = stmt.where(or_(KassaOrder.no.ilike(t), KassaOrder.kontragent.ilike(t)))
    return await _orders_read(db, list((await db.execute(stmt)).scalars()))


@router.post("/orderlar/{kassa_order_id}/storno", response_model=AmalNatija, operation_id="kassa_storno")
async def kassa_storno(
    db: SessionDep, user: MoliyaUser, kassa_order_id: int, body: StornoIn, request: Request
) -> AmalNatija:
    """Xato orderni teskari order bilan bekor qilish (Moliya: direktor yoki moliyachi, ikki kalit)."""
    try:
        n = await k.storno(db, kassa_order_id, user.id, body.sabab)
    except k.KassaXato as e:
        await db.rollback()
        raise _bad(e) from e
    log_action(
        db,
        module="kassa",
        action="storno",
        user_id=user.id,
        message=f"{n.xabar}: {body.sabab}"[:500],
        ip=client_ip(request),
    )
    await db.commit()
    return await _natija(db, n)


@router.get("/turkumlar", response_model=list[str], operation_id="kassa_turkumlar")
async def kassa_turkumlar(db: SessionDep, _: KassaUser) -> list[str]:
    """Faol xarajat moddalari (Moliya sozlamasida yuritiladi)."""
    return [m.nom for m in await k.moddalar(db)]
