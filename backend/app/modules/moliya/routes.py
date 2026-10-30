"""Moliya API — `/moliya/...` (EKO TZ §8, 3-daraja): direktor va moliyachi."""

import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.api.deps import SessionDep, client_ip, require_roles
from app.crud import log_action
from app.models import Client, User
from app.models.enums import UserRole
from app.modules.kassa import service as kassa
from app.modules.moliya import services as m
from app.modules.moliya.models import MoliyaDavr, MoliyaReja
from app.modules.moliya.schemas import (
    Akt,
    Balans,
    Bosh,
    BuyurtmaKarta,
    ByudjetQator,
    DavrRead,
    DavrSababIn,
    Debitor,
    HisobSozlama,
    HisobSozlamaIn,
    KalendarQator,
    Kreditor,
    MijozShartIn,
    ModdaIn,
    ModdaRead,
    OchilishIn,
    OchilishNatija,
    OchilishRead,
    PnL,
    PulOqimi,
    RejaIn,
    RejaRead,
    Sozlamalar,
)
from app.services.settings_service import ENG_KAM_AVANS_FOIZ, TOLOV_MUDDAT_KUN, get_setting, set_setting

router = APIRouter(prefix="/moliya", tags=["moliya"])

MoliyaUser = Annotated[User, Depends(require_roles(UserRole.DIRECTOR, UserRole.MOLIYACHI))]
Oy = Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")]


def _bad(xatolar: list[str]) -> HTTPException:
    return HTTPException(status_code=422, detail=" · ".join(xatolar))


def _oy(oy: str | None) -> date:
    return m.oy_parse(oy) if oy else m.oy_boshi(m.bugun())


@router.get("/bosh", response_model=Bosh, operation_id="moliya_bosh")
async def moliya_bosh(db: SessionDep, _: MoliyaUser) -> Bosh:
    return await m.bosh(db)


@router.get("/pnl", response_model=PnL, operation_id="moliya_pnl")
async def moliya_pnl(db: SessionDep, _: MoliyaUser, oy: Oy | None = None) -> PnL:
    """Foyda va zarar. Yopilgan oy — qotgan nusxadan."""
    return await m.pnl(db, _oy(oy))


@router.get("/pul-oqimi", response_model=PulOqimi, operation_id="moliya_pul_oqimi")
async def moliya_pul_oqimi(
    db: SessionDep, _: MoliyaUser, dan: date | None = None, gacha: date | None = None
) -> PulOqimi:
    g = gacha or m.bugun()
    try:
        return await m.pul_oqimi(db, dan or m.oy_boshi(g), g)
    except m.MoliyaXato as e:
        raise _bad(e.xatolar) from e


@router.get("/debitorlar", response_model=list[Debitor], operation_id="moliya_debitorlar")
async def moliya_debitorlar(db: SessionDep, _: MoliyaUser) -> list[Debitor]:
    return await m.debitorlar(db)


@router.put("/mijoz/{client_id}/shart", operation_id="moliya_mijoz_shart")
async def moliya_mijoz_shart(
    db: SessionDep, user: MoliyaUser, client_id: int, body: MijozShartIn, request: Request
) -> dict[str, bool]:
    try:
        await m.mijoz_shart_saqla(db, client_id, body.shartnoma_no, body.muddat_kun, body.kredit_limit)
    except m.MoliyaXato as e:
        raise _bad(e.xatolar) from e
    log_action(
        db,
        module="moliya",
        action="mijoz_shart",
        user_id=user.id,
        message=f"mijoz {client_id}: shartnoma {body.shartnoma_no or '—'}, muddat {body.muddat_kun}, "
        f"limit {body.kredit_limit}",
        ip=client_ip(request),
    )
    await db.commit()
    return {"ok": True}


@router.get("/akt/{client_id}", response_model=Akt, operation_id="moliya_akt")
async def moliya_akt(
    db: SessionDep, _: MoliyaUser, client_id: int, dan: date | None = None, gacha: date | None = None
) -> Akt:
    """Solishtirma dalolatnoma (akt sverki)."""
    g = gacha or m.bugun()
    try:
        return await m.akt(db, client_id, dan or date(g.year, 1, 1), g)
    except m.MoliyaXato as e:
        raise _bad(e.xatolar) from e


@router.get("/buyurtma/{order_id}", response_model=BuyurtmaKarta, operation_id="moliya_buyurtma_karta")
async def moliya_buyurtma_karta(db: SessionDep, _: MoliyaUser, order_id: int) -> BuyurtmaKarta:
    """Buyurtma kartasi (faqat o'qish): hisobot qatoridan to'lov, ESF va tannarxga o'tish."""
    try:
        return await m.buyurtma_karta(db, order_id)
    except m.MoliyaXato as e:
        raise HTTPException(status_code=404, detail=e.xatolar[0]) from e


@router.get("/kreditorlar", response_model=list[Kreditor], operation_id="moliya_kreditorlar")
async def moliya_kreditorlar(db: SessionDep, _: MoliyaUser) -> list[Kreditor]:
    return await m.kreditorlar(db)


@router.get("/kalendar", response_model=list[KalendarQator], operation_id="moliya_kalendar")
async def moliya_kalendar(db: SessionDep, _: MoliyaUser, kun: int = Query(45, ge=1, le=366)) -> list[KalendarQator]:
    return await m.kalendar(db, kun)


@router.get("/byudjet", response_model=list[ByudjetQator], operation_id="moliya_byudjet")
async def moliya_byudjet(db: SessionDep, _: MoliyaUser, oy: Oy | None = None) -> list[ByudjetQator]:
    return await m.byudjet(db, _oy(oy))


@router.get("/balans", response_model=Balans, operation_id="moliya_balans")
async def moliya_balans(db: SessionDep, _: MoliyaUser) -> Balans:
    return await m.balans(db)


@router.get("/jurnal.csv", operation_id="moliya_jurnal_csv")
async def moliya_jurnal_csv(db: SessionDep, _: MoliyaUser, dan: date, gacha: date) -> StreamingResponse:
    """Orderlar jurnali CSV (Excel uchun `;` ajratgich va BOM)."""
    rows = await kassa.orderlar_davr(db, m.vaqt(dan), m.vaqt(gacha + timedelta(days=1)))
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Sana", "Order", "Tur", "Modda", "Hisob", "Kontragent", "Turkum", "Summa", "Izoh"])
    for o in rows:
        summa = o.summa if o.tur == "kirim" else -o.summa
        w.writerow(
            [
                f"{o.sana.astimezone(m.TASHKENT_TZ):%d.%m.%Y %H:%M}",
                o.no,
                "Kirim" if o.tur == "kirim" else "Chiqim",
                m.MAQSAD.get(o.maqsad, o.maqsad),
                o.hisob,
                o.kontragent,
                o.turkum,
                f"{summa:.2f}".replace(".", ","),
                o.izoh,
            ]
        )
    return StreamingResponse(
        iter(["﻿" + buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="orderlar_{dan}_{gacha}.csv"'},
    )


# ── rejali to'lovlar ──
def _reja(r: MoliyaReja) -> RejaRead:
    return RejaRead.model_validate(
        {
            "id": r.id,
            "nom": r.nom,
            "tur": r.tur,
            "summa": r.summa,
            "turkum": r.turkum,
            "takror": r.takror,
            "sana": r.sana,
            "faol": r.faol,
        }
    )


@router.get("/rejalar", response_model=list[RejaRead], operation_id="moliya_rejalar")
async def moliya_rejalar(db: SessionDep, _: MoliyaUser) -> list[RejaRead]:
    rows = (await db.execute(select(MoliyaReja).order_by(MoliyaReja.sana, MoliyaReja.id))).scalars()
    return [_reja(r) for r in rows]


@router.post("/rejalar", response_model=RejaRead, operation_id="moliya_reja_qosh")
async def moliya_reja_qosh(db: SessionDep, user: MoliyaUser, body: RejaIn, request: Request) -> RejaRead:
    r = MoliyaReja(**body.model_dump(), yaratgan_id=user.id)
    db.add(r)
    await db.flush()
    log_action(
        db, module="moliya", action="reja", user_id=user.id, message=f"+ {r.nom}: {r.summa}", ip=client_ip(request)
    )
    await db.commit()
    return _reja(r)


@router.put("/rejalar/{reja_id}", response_model=RejaRead, operation_id="moliya_reja_saqla")
async def moliya_reja_saqla(db: SessionDep, user: MoliyaUser, reja_id: int, body: RejaIn, request: Request) -> RejaRead:
    r = await db.get(MoliyaReja, reja_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Reja topilmadi")
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    log_action(
        db,
        module="moliya",
        action="reja",
        user_id=user.id,
        message=f"{r.nom}: {r.summa}, faol={r.faol}",
        ip=client_ip(request),
    )
    await db.commit()
    return _reja(r)


# ── sozlamalar: moddalar, hisoblar, umumiy ──
@router.get("/moddalar", response_model=list[ModdaRead], operation_id="moliya_moddalar")
async def moliya_moddalar(db: SessionDep, _: MoliyaUser) -> list[ModdaRead]:
    return [
        ModdaRead(id=x.id, nom=x.nom, oylik_limit=x.oylik_limit, faol=x.faol)
        for x in await kassa.moddalar(db, faqat_faol=False)
    ]


async def _modda(db: SessionDep, user: User, body: ModdaIn, request: Request, modda_id: int | None) -> ModdaRead:
    try:
        x = await kassa.modda_saqla(db, body.nom, body.oylik_limit, body.faol, modda_id)
    except kassa.KassaXato as e:
        await db.rollback()
        raise _bad(e.xatolar) from e
    log_action(
        db,
        module="moliya",
        action="modda",
        user_id=user.id,
        message=f"{x.nom}: limit {x.oylik_limit}, faol={x.faol}",
        ip=client_ip(request),
    )
    await db.commit()
    return ModdaRead(id=x.id, nom=x.nom, oylik_limit=x.oylik_limit, faol=x.faol)


@router.post("/moddalar", response_model=ModdaRead, operation_id="moliya_modda_qosh")
async def moliya_modda_qosh(db: SessionDep, user: MoliyaUser, body: ModdaIn, request: Request) -> ModdaRead:
    return await _modda(db, user, body, request, None)


@router.put("/moddalar/{modda_id}", response_model=ModdaRead, operation_id="moliya_modda_saqla")
async def moliya_modda_saqla(
    db: SessionDep, user: MoliyaUser, modda_id: int, body: ModdaIn, request: Request
) -> ModdaRead:
    return await _modda(db, user, body, request, modda_id)


@router.get("/hisoblar", response_model=list[HisobSozlama], operation_id="moliya_hisoblar")
async def moliya_hisoblar(db: SessionDep, _: MoliyaUser) -> list[HisobSozlama]:
    return [
        HisobSozlama(
            kod=h.kod, nom=h.nom, tur=h.tur, boshlangich=h.boshlangich, komissiya_foiz=h.komissiya_foiz, qoldiq=q
        )
        for h, q in await kassa.hisoblar(db)
    ]


@router.put("/hisoblar/{kod}", response_model=list[HisobSozlama], operation_id="moliya_hisob_saqla")
async def moliya_hisob_saqla(
    db: SessionDep, user: MoliyaUser, kod: str, body: HisobSozlamaIn, request: Request
) -> list[HisobSozlama]:
    try:
        h = await kassa.hisob_sozla(db, kod, body.boshlangich, body.komissiya_foiz)
    except kassa.KassaXato as e:
        await db.rollback()
        raise _bad(e.xatolar) from e
    log_action(
        db,
        module="moliya",
        action="hisob",
        user_id=user.id,
        message=f"{h.nom}: boshlang'ich {h.boshlangich}, komissiya {h.komissiya_foiz} %",
        ip=client_ip(request),
    )
    await db.commit()
    return await moliya_hisoblar(db, user)


@router.get("/sozlamalar", response_model=Sozlamalar, operation_id="moliya_sozlamalar")
async def moliya_sozlamalar(db: SessionDep, _: MoliyaUser) -> Sozlamalar:
    return Sozlamalar(
        eng_kam_avans_foiz=int(await get_setting(db, ENG_KAM_AVANS_FOIZ)),
        tolov_muddat_kun=int(await get_setting(db, TOLOV_MUDDAT_KUN)),
    )


@router.put("/sozlamalar", response_model=Sozlamalar, operation_id="moliya_sozlamalar_saqla")
async def moliya_sozlamalar_saqla(db: SessionDep, user: MoliyaUser, body: Sozlamalar, request: Request) -> Sozlamalar:
    await set_setting(db, ENG_KAM_AVANS_FOIZ, str(body.eng_kam_avans_foiz), user.id)
    await set_setting(db, TOLOV_MUDDAT_KUN, str(body.tolov_muddat_kun), user.id)
    log_action(
        db,
        module="moliya",
        action="sozlama",
        user_id=user.id,
        message=f"eng kam avans {body.eng_kam_avans_foiz} %, to'lov muddati {body.tolov_muddat_kun} kun",
        ip=client_ip(request),
    )
    await db.commit()
    return body


# ── davr yopish ──
async def _davr_read(db: SessionDep, rows: list[MoliyaDavr]) -> list[DavrRead]:
    ism = await m.ismlar(db, {x for d in rows for x in (d.yopgan_id, d.ochish_sorov_id, d.ochgan_id)})
    return [
        DavrRead(
            oy=f"{d.oy:%Y-%m}",
            holat=d.holat,
            yopgan=ism.get(d.yopgan_id or 0),
            yopilgan_at=d.yopilgan_at,
            ochish_sorov=ism.get(d.ochish_sorov_id or 0),
            ochish_sabab=d.ochish_sabab,
            ochgan=ism.get(d.ochgan_id or 0),
            ochilgan_at=d.ochilgan_at,
            sof=d.natija.get("sof") if d.natija else None,
        )
        for d in rows
    ]


@router.get("/davrlar", response_model=list[DavrRead], operation_id="moliya_davrlar")
async def moliya_davrlar(db: SessionDep, _: MoliyaUser) -> list[DavrRead]:
    rows = list((await db.execute(select(MoliyaDavr).order_by(MoliyaDavr.oy.desc()))).scalars())
    return await _davr_read(db, rows)


async def _davr_amal(db: SessionDep, user: User, request: Request, amal: str, oy: str, sabab: str = "") -> DavrRead:
    try:
        d0 = m.oy_parse(oy)
        if amal == "yopish":
            d = await m.davr_yop(db, d0, user.id)
        elif amal == "sorov":
            d = await m.davr_ochish_sorov(db, d0, user.id, sabab)
        else:
            d = await m.davr_ochish_tasdiq(db, d0, user.id)
    except m.MoliyaXato as e:
        await db.rollback()
        raise _bad(e.xatolar) from e
    log_action(
        db,
        module="moliya",
        action=f"davr_{amal}",
        user_id=user.id,
        message=f"{oy} {sabab}"[:500],
        ip=client_ip(request),
    )
    await db.commit()
    return (await _davr_read(db, [d]))[0]


@router.post("/davrlar/{oy}/yopish", response_model=DavrRead, operation_id="moliya_davr_yop")
async def moliya_davr_yop(db: SessionDep, user: MoliyaUser, oy: str, request: Request) -> DavrRead:
    return await _davr_amal(db, user, request, "yopish", oy)


@router.post("/davrlar/{oy}/ochish-sorov", response_model=DavrRead, operation_id="moliya_davr_ochish_sorov")
async def moliya_davr_ochish_sorov(
    db: SessionDep, user: MoliyaUser, oy: str, body: DavrSababIn, request: Request
) -> DavrRead:
    return await _davr_amal(db, user, request, "sorov", oy, body.sabab)


@router.post("/davrlar/{oy}/ochish-tasdiq", response_model=DavrRead, operation_id="moliya_davr_ochish_tasdiq")
async def moliya_davr_ochish_tasdiq(db: SessionDep, user: MoliyaUser, oy: str, request: Request) -> DavrRead:
    """Ikki kalit: so'rovni yozgan xodim emas, boshqasi tasdiqlaydi."""
    return await _davr_amal(db, user, request, "tasdiq", oy)


# ── ochilish qoldiqlari (tizimga o'tish, TZ §11 7-bosqich) ──
async def _ochilish_read(db: SessionDep) -> list[OchilishRead]:
    tol = await kassa.ochilish_tolangan(db)
    rows = await kassa.ochilishlar(db)
    jami: dict[int, Decimal] = {}
    for r in rows:
        if r.client_id is not None:
            jami[r.client_id] = jami.get(r.client_id, Decimal(0)) + r.summa
    return [
        OchilishRead(
            id=r.id,
            tur=r.tur,
            client_id=r.client_id,
            kontragent=r.kontragent,
            summa=r.summa,
            sana=r.sana,
            izoh=r.izoh,
            qolgan=jami[r.client_id] - tol.get(r.client_id, Decimal(0)) if r.client_id is not None else None,
        )
        for r in rows
    ]


@router.get("/ochilish", response_model=list[OchilishRead], operation_id="moliya_ochilish")
async def moliya_ochilish(db: SessionDep, _: MoliyaUser) -> list[OchilishRead]:
    return await _ochilish_read(db)


async def _mijoz_top(db: SessionDep, q: OchilishIn) -> int | None:
    if q.client_id is not None:
        return q.client_id
    if q.telefon.strip():
        tel = "".join(ch for ch in q.telefon if ch.isdigit())
        tel = "+998" + tel[-9:] if len(tel) >= 9 else tel
        jonli = Client.is_deleted.is_(False)
        found = (await db.execute(select(Client.id).where(Client.phone == tel, jonli))).scalars().all()
        return found[0] if len(found) == 1 else None
    if q.nomi.strip():
        found = (
            (
                await db.execute(
                    select(Client.id).where(
                        func.lower(Client.full_name) == " ".join(q.nomi.split()).lower(),
                        Client.is_deleted == False,  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        )
        return found[0] if len(found) == 1 else None
    return None


@router.post("/ochilish", response_model=OchilishNatija, operation_id="moliya_ochilish_qosh")
async def moliya_ochilish_qosh(
    db: SessionDep, user: MoliyaUser, body: list[OchilishIn], request: Request
) -> OchilishNatija:
    """Ochilish qoldiqlari (bitta yoki CSV dan ko'p). Bitta qator xato bo'lsa — hech biri yozilmaydi.
    Tuzatish — teskari ishorali yangi qator (jurnal)."""
    if not body or len(body) > 5000:
        raise HTTPException(status_code=422, detail="1 dan 5000 tagacha qator")
    xatolar = []
    for i, q in enumerate(body, 1):
        try:
            cid = await _mijoz_top(db, q) if q.tur == "mijoz" else None
            if q.tur == "mijoz" and cid is None:
                raise kassa.KassaXato([f"mijoz topilmadi yoki bir nechta ({q.telefon or q.nomi or q.client_id})"])
            await kassa.ochilish_qosh(
                db, q.tur, q.summa, q.sana, user.id, client_id=cid, kontragent=q.nomi, izoh=q.izoh
            )
        except kassa.KassaXato as e:
            xatolar.append(f"{i}-qator: {' · '.join(e.xatolar)}")
    if xatolar:
        await db.rollback()
        raise HTTPException(status_code=422, detail=" | ".join(xatolar[:20]) + (" | …" if len(xatolar) > 20 else ""))
    log_action(
        db,
        module="moliya",
        action="ochilish",
        user_id=user.id,
        message=f"{len(body)} qator, jami {sum((q.summa for q in body), Decimal(0))}",
        ip=client_ip(request),
    )
    await db.commit()
    return OchilishNatija(yozildi=len(body), qatorlar=await _ochilish_read(db))
