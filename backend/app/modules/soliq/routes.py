"""Soliq API — `/soliq/...` (EKO TZ §9): direktor va moliyachi (buxgalter)."""

import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import SessionDep, client_ip, require_roles
from app.crud import log_action
from app.models import Client, Order, User
from app.models.enums import OrderStatus, UserRole
from app.modules.ombor import service as ombor
from app.modules.soliq import services as s
from app.modules.soliq.models import SoliqEsf, SoliqMijoz, SoliqRejim
from app.modules.soliq.schemas import (
    EsfBuyurtmaIn,
    EsfHujjatIn,
    EsfRead,
    JavobIn,
    Kitob,
    KorxonaIO,
    MijozIO,
    MxikIn,
    Nomzod,
    OySoliqRead,
    RejimIn,
    RejimRead,
    SinovKiruvchiIn,
)

router = APIRouter(prefix="/soliq", tags=["soliq"])

SoliqUser = Annotated[User, Depends(require_roles(UserRole.DIRECTOR, UserRole.MOLIYACHI))]
Oy = Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")]


def _bad(e: s.SoliqXato) -> HTTPException:
    return HTTPException(status_code=422, detail=" · ".join(e.xatolar))


def _oy(oy: str | None) -> date:
    return date.fromisoformat(f"{oy}-01") if oy else s.bugun().replace(day=1)


async def _esflar(db: SessionDep, rows: list[SoliqEsf]) -> list[EsfRead]:
    nums = dict(
        (await db.execute(select(Order.id, Order.number).where(Order.id.in_({e.order_id for e in rows if e.order_id}))))
        .tuples()
        .all()
    )
    out = []
    for e in rows:
        r = EsfRead.model_validate(e).model_copy(update={"order_number": nums.get(e.order_id or 0)})
        if e.stock_doc_id:
            doc, _ = await ombor.hujjat_qatorlari(db, e.stock_doc_id)
            r.stock_doc_no = doc.no if doc else None
        out.append(r)
    return out


async def _amal(db: SessionDep, user: User, request: Request, action: str, e: SoliqEsf) -> EsfRead:
    log_action(db, module="soliq", action=action, user_id=user.id, message=f"{e.no} {e.holat}", ip=client_ip(request))
    await db.commit()
    return (await _esflar(db, [e]))[0]


# ── sozlamalar ──
@router.get("/korxona", response_model=KorxonaIO, operation_id="soliq_korxona")
async def soliq_korxona(db: SessionDep, _: SoliqUser) -> KorxonaIO:
    k = await s.korxona(db)
    await db.commit()
    return KorxonaIO.model_validate(k)


@router.put("/korxona", response_model=KorxonaIO, operation_id="soliq_korxona_saqla")
async def soliq_korxona_saqla(db: SessionDep, user: SoliqUser, body: KorxonaIO, request: Request) -> KorxonaIO:
    k = await s.korxona(db)
    for key, v in body.model_dump().items():
        setattr(k, key, v.strip() if isinstance(v, str) else v)
    log_action(
        db, module="soliq", action="korxona", user_id=user.id, message=f"{k.nomi} STIR {k.stir}", ip=client_ip(request)
    )
    await db.commit()
    return KorxonaIO.model_validate(k)


@router.get("/rejimlar", response_model=list[RejimRead], operation_id="soliq_rejimlar")
async def soliq_rejimlar(db: SessionDep, _: SoliqUser) -> list[RejimRead]:
    rows = (await db.execute(select(SoliqRejim).order_by(SoliqRejim.amal_boshi.desc()))).scalars()
    return [RejimRead.model_validate(r) for r in rows]


@router.post("/rejimlar", response_model=RejimRead, operation_id="soliq_rejim_qosh")
async def soliq_rejim_qosh(db: SessionDep, user: SoliqUser, body: RejimIn, request: Request) -> RejimRead:
    """Rejim/stavka shu sanadan (tarix). Masalan yil boshidan QQS to'lovchiga o'tish."""
    try:
        r = await s.rejim_qosh(db, body.amal_boshi, body.rejim, body.qqs_foiz, body.aylanma_foiz, user.id)
    except s.SoliqXato as e:
        await db.rollback()
        raise _bad(e) from e
    log_action(
        db,
        module="soliq",
        action="rejim",
        user_id=user.id,
        message=f"{r.amal_boshi}: {r.rejim}, QQS {r.qqs_foiz} %, aylanma {r.aylanma_foiz} %",
        ip=client_ip(request),
    )
    await db.commit()
    return RejimRead.model_validate(r)


@router.get("/mijoz/{client_id}", response_model=MijozIO, operation_id="soliq_mijoz")
async def soliq_mijoz(db: SessionDep, _: SoliqUser, client_id: int) -> MijozIO:
    m = await s.mijoz(db, client_id)
    return MijozIO.model_validate(m) if m else MijozIO()


@router.put("/mijoz/{client_id}", response_model=MijozIO, operation_id="soliq_mijoz_saqla")
async def soliq_mijoz_saqla(
    db: SessionDep, user: SoliqUser, client_id: int, body: MijozIO, request: Request
) -> MijozIO:
    try:
        m = await s.mijoz_saqla(db, client_id, body.model_dump())
    except s.SoliqXato as e:
        await db.rollback()
        raise _bad(e) from e
    log_action(
        db,
        module="soliq",
        action="mijoz",
        user_id=user.id,
        message=f"mijoz {client_id}: STIR {m.stir}",
        ip=client_ip(request),
    )
    await db.commit()
    return MijozIO.model_validate(m)


@router.put("/katalog/{item_id}", operation_id="soliq_mxik_saqla")
async def soliq_mxik_saqla(
    db: SessionDep, user: SoliqUser, item_id: int, body: MxikIn, request: Request
) -> dict[str, bool]:
    try:
        await s.mxik_saqla(db, item_id, body.mxik, body.birlik_kod, body.qqs_turi)
    except s.SoliqXato as e:
        await db.rollback()
        raise _bad(e) from e
    log_action(
        db,
        module="soliq",
        action="mxik",
        user_id=user.id,
        message=f"pozitsiya {item_id}: {body.mxik}",
        ip=client_ip(request),
    )
    await db.commit()
    return {"ok": True}


# ── ESF ──
@router.get("/esf", response_model=list[EsfRead], operation_id="soliq_esflar")
async def soliq_esflar(
    db: SessionDep,
    _: SoliqUser,
    tur: Annotated[str, Query(pattern="^(chiquvchi|kiruvchi)$")] = "chiquvchi",
    limit: int = Query(200, ge=1, le=2000),
) -> list[EsfRead]:
    rows = list(
        (
            await db.execute(select(SoliqEsf).where(SoliqEsf.tur == tur).order_by(SoliqEsf.id.desc()).limit(limit))
        ).scalars()
    )
    return await _esflar(db, rows)


@router.get("/nomzodlar", response_model=list[Nomzod], operation_id="soliq_nomzodlar")
async def soliq_nomzodlar(db: SessionDep, _: SoliqUser, kun: int = Query(90, ge=1, le=730)) -> list[Nomzod]:
    """ESF yozilmagan sotuvlar: so'nggi `kun` kundagi yetkazilgan buyurtmalar va ombor sotuv hujjatlari."""
    dan = s.bugun() - timedelta(days=kun)
    tirik = select(SoliqEsf).where(SoliqEsf.holat.in_(s.TIRIK), SoliqEsf.tur == "chiquvchi")
    band_o = {e.order_id for e in (await db.execute(tirik)).scalars() if e.order_id}
    band_d = {e.stock_doc_id for e in (await db.execute(tirik)).scalars() if e.stock_doc_id}
    yuridik = {
        m.client_id: not s.mijoz_tekshir(m)
        for m in (await db.execute(select(SoliqMijoz).where(SoliqMijoz.yuridik == True))).scalars()  # noqa: E712
    }
    rows = (
        await db.execute(
            select(Order, Client.full_name)
            .join(Client, Client.id == Order.client_id)
            .where(
                Order.delivered_at >= s._vaqt(dan),
                Order.status != OrderStatus.CANCELLED,
                Order.is_deleted == False,  # noqa: E712
                Order.amount.is_not(None),
            )
            .order_by(Order.delivered_at.desc())
        )
    ).all()
    out = [
        Nomzod(
            tur="buyurtma",
            id=o.id,
            no=o.number,
            sana=s._mahalliy(o.delivered_at),
            mijoz=nom,
            client_id=o.client_id,
            summa=o.amount or Decimal(0),
            tayyor=yuridik.get(o.client_id, False),
        )
        for o, nom in rows
        if o.id not in band_o and o.delivered_at is not None
    ]
    for h in await ombor.sotuv_hujjatlari(db, dan, None):
        if h.summa > 0 and h.id not in band_d:
            out.append(
                Nomzod(
                    tur="hujjat",
                    id=h.id,
                    no=h.no,
                    sana=h.sana,
                    mijoz=h.kontragent,
                    client_id=None,
                    summa=h.summa,
                    tayyor=False,
                )
            )
    return sorted(out, key=lambda n: n.sana, reverse=True)


@router.post("/esf/buyurtma", response_model=EsfRead, operation_id="soliq_esf_buyurtma")
async def soliq_esf_buyurtma(db: SessionDep, user: SoliqUser, body: EsfBuyurtmaIn, request: Request) -> EsfRead:
    try:
        e = await s.esf_buyurtmadan(db, body.order_id, user.id)
    except s.SoliqXato as ex:
        await db.rollback()
        raise _bad(ex) from ex
    return await _amal(db, user, request, "esf_yasaldi", e)


@router.post("/esf/hujjat", response_model=EsfRead, operation_id="soliq_esf_hujjat")
async def soliq_esf_hujjat(db: SessionDep, user: SoliqUser, body: EsfHujjatIn, request: Request) -> EsfRead:
    try:
        e = await s.esf_hujjatdan(db, body.stock_doc_id, body.client_id, user.id)
    except s.SoliqXato as ex:
        await db.rollback()
        raise _bad(ex) from ex
    return await _amal(db, user, request, "esf_yasaldi", e)


@router.post("/esf/{esf_id}/yuborish", response_model=EsfRead, operation_id="soliq_esf_yubor")
async def soliq_esf_yubor(db: SessionDep, user: SoliqUser, esf_id: int, request: Request) -> EsfRead:
    """Navbatga qo'yadi — fon ishi operatorga yuboradi (operator ishlamasa qayta uradi)."""
    try:
        e = await s.navbatga(db, esf_id)
    except s.SoliqXato as ex:
        await db.rollback()
        raise _bad(ex) from ex
    return await _amal(db, user, request, "esf_navbat", e)


@router.post("/esf/{esf_id}/bekor", response_model=EsfRead, operation_id="soliq_esf_bekor")
async def soliq_esf_bekor(db: SessionDep, user: SoliqUser, esf_id: int, request: Request) -> EsfRead:
    try:
        e = await s.bekor(db, esf_id)
    except s.SoliqXato as ex:
        await db.rollback()
        raise _bad(ex) from ex
    return await _amal(db, user, request, "esf_bekor", e)


@router.post("/esf/{esf_id}/javob", response_model=EsfRead, operation_id="soliq_esf_javob")
async def soliq_esf_javob(db: SessionDep, user: SoliqUser, esf_id: int, body: JavobIn, request: Request) -> EsfRead:
    """Kiruvchi ESF: qabul yoki rad (sabab bilan)."""
    try:
        e = await s.kiruvchi_javob(db, esf_id, body.qabul, body.sabab)
    except s.SoliqXato as ex:
        await db.rollback()
        raise _bad(ex) from ex
    return await _amal(db, user, request, "esf_javob", e)


@router.post("/ishlov", operation_id="soliq_ishlov")
async def soliq_ishlov(db: SessionDep, _: SoliqUser) -> dict[str, int]:
    """Navbatni hozir ishlatish (fon ishi har daqiqada ham ishlaydi)."""
    n = await s.ishlov(db)
    await db.commit()
    return {"yuborildi": n.yuborildi, "javob": n.javob, "xato": n.xato, "kiruvchi": n.kiruvchi}


@router.post("/sinov/kiruvchi", operation_id="soliq_sinov_kiruvchi")
async def soliq_sinov_kiruvchi(db: SessionDep, _: SoliqUser, body: SinovKiruvchiIn) -> dict[str, str]:
    """FAQAT lokal sinov operatori: yetkazib beruvchi bizga ESF yuborganini taqlid qiladi."""
    qqs = s.qqs_ajrat(body.jami, body.qqs_foiz)
    k = await s.korxona(db)
    hujjat = {
        "raqam": body.raqam,
        "sana": str(body.sana),
        "sotuvchi": {"nomi": body.sotuvchi_nomi, "stir": body.sotuvchi_stir},
        "xaridor": {"nomi": k.nomi, "stir": k.stir},
        "qatorlar": [
            {
                "nom": "Material",
                "mxik": "0" * 17,
                "miqdor": "1",
                "summa": str(body.jami - qqs),
                "qqs": str(qqs),
                "jami": str(body.jami),
            }
        ],
        "summa": str(body.jami - qqs),
        "qqs": str(qqs),
        "jami": str(body.jami),
    }
    try:
        oid = await s.sinov_kiruvchi(db, hujjat)
    except s.SoliqXato as ex:
        raise _bad(ex) from ex
    await db.commit()
    return {"operator_id": oid}


# ── hisobot ──
@router.get("/oy", response_model=OySoliqRead, operation_id="soliq_oy")
async def soliq_oy(db: SessionDep, _: SoliqUser, oy: Oy | None = None) -> OySoliqRead:
    return OySoliqRead.model_validate(await s.oy_soliq(db, _oy(oy)))


@router.get("/kitob", response_model=Kitob, operation_id="soliq_kitob")
async def soliq_kitob(db: SessionDep, _: SoliqUser, oy: Oy | None = None) -> Kitob:
    """QQS kitobi: sotuv va xarid kitobi (qabul qilingan ESF lar) + ESF siz sotuvdagi QQS."""
    d = _oy(oy)
    o = OySoliqRead.model_validate(await s.oy_soliq(db, d))
    sotuv = await _esflar(db, await s.kitob(db, d, "chiquvchi"))
    xarid = await _esflar(db, await s.kitob(db, d, "kiruvchi"))
    return Kitob(oy=o, sotuv=sotuv, xarid=xarid, esfsiz_qqs=o.sotuv_qqs - sum((e.qqs for e in sotuv), 0))


@router.get("/kitob.csv", operation_id="soliq_kitob_csv")
async def soliq_kitob_csv(db: SessionDep, _: SoliqUser, oy: Oy) -> StreamingResponse:
    d = _oy(oy)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Kitob", "Sana", "ESF", "Raqam", "Kontragent", "STIR", "Summa (QQSsiz)", "QQS", "Jami"])
    for tur, nom in (("chiquvchi", "Sotuv"), ("kiruvchi", "Xarid")):
        for e in await s.kitob(db, d, tur):
            w.writerow(
                [nom, f"{e.sana:%d.%m.%Y}", e.no, e.raqam, e.kontragent, e.kontragent_stir]
                + [f"{v:.2f}".replace(".", ",") for v in (e.summa, e.qqs, e.jami)]
            )
    return StreamingResponse(
        iter(["﻿" + buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="qqs_kitobi_{oy}.csv"'},
    )
