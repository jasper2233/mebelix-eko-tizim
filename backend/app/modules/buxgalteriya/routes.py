"""Buxgalteriya API — `/bux/...` (EKO 7): direktor va moliyachi (buxgalter)."""

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import SessionDep, client_ip, require_roles
from app.crud import log_action
from app.models import User
from app.models.enums import UserRole
from app.modules.buxgalteriya import services as b
from app.modules.buxgalteriya.models import BuxQoida, BuxSchyot, BuxYozuv

router = APIRouter(prefix="/bux", tags=["buxgalteriya"])

BuxUser = Annotated[User, Depends(require_roles(UserRole.DIRECTOR, UserRole.MOLIYACHI))]


class SchyotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kod: str
    nom: str
    tur: str
    faol: bool


class SchyotIn(BaseModel):
    kod: Annotated[str, Field(pattern=r"^\d{4}$")]
    nom: Annotated[str, Field(min_length=1, max_length=150)]
    tur: Annotated[str, Field(pattern="^(A|P|AP)$")]
    faol: bool = True


class QoidaIO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kalit: Annotated[str, Field(min_length=1, max_length=80)]
    schyot: Annotated[str, Field(pattern=r"^\d{4}$")]


class YozuvRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sana: date
    debet: str
    kredit: str
    summa: Decimal
    izoh: str
    guruh: str | None
    client_id: int | None
    kontragent: str
    storno_of_id: int | None


class YozuvIn(BaseModel):
    sana: date
    debet: Annotated[str, Field(pattern=r"^\d{4}$")]
    kredit: Annotated[str, Field(pattern=r"^\d{4}$")]
    summa: Annotated[Decimal, Field(gt=0, le=Decimal(10) ** 13)]
    izoh: Annotated[str, Field(min_length=1, max_length=300)]
    kontragent: Annotated[str, Field(max_length=150)] = ""


class StornoIn(BaseModel):
    sabab: Annotated[str, Field(min_length=1, max_length=200)]


class SaldoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kod: str
    nom: str
    tur: str
    bosh_d: Decimal
    bosh_k: Decimal
    ayl_d: Decimal
    ayl_k: Decimal
    yak_d: Decimal
    yak_k: Decimal


class Kartochka(BaseModel):
    kod: str
    nom: str
    boshlangich: Decimal
    yozuvlar: list[YozuvRead]
    yakuniy: Decimal


class NazoratRead(BaseModel):
    nom: str
    buxgalteriya: Decimal
    manba: Decimal
    farq: Decimal
    izoh: str


class SinxronRead(BaseModel):
    yozildi: int
    tuzatish: int


def _bad(e: b.BuxXato) -> HTTPException:
    return HTTPException(status_code=422, detail=" · ".join(e.xatolar))


async def _sinx(db: SessionDep) -> None:
    """Hisobotdan oldin provodkalar manbalarga moslanadi (fon ishi ham har 5 daqiqada)."""
    await b.sinxron(db)
    await db.commit()


@router.post("/sinxron", response_model=SinxronRead, operation_id="bux_sinxron")
async def bux_sinxron(db: SessionDep, _: BuxUser) -> SinxronRead:
    n = await b.sinxron(db)
    await db.commit()
    return SinxronRead(yozildi=n.yozildi, tuzatish=n.tuzatish)


@router.get("/schyotlar", response_model=list[SchyotRead], operation_id="bux_schyotlar")
async def bux_schyotlar(db: SessionDep, _: BuxUser) -> list[SchyotRead]:
    rows = (await db.execute(select(BuxSchyot).order_by(BuxSchyot.kod))).scalars()
    return [SchyotRead.model_validate(s) for s in rows]


@router.put("/schyotlar", response_model=SchyotRead, operation_id="bux_schyot_saqla")
async def bux_schyot_saqla(db: SessionDep, user: BuxUser, body: SchyotIn, request: Request) -> SchyotRead:
    s = (await db.execute(select(BuxSchyot).where(BuxSchyot.kod == body.kod))).scalar_one_or_none()
    if s is None:
        s = BuxSchyot(kod=body.kod, nom=body.nom, tur=body.tur, faol=body.faol)
        db.add(s)
    else:
        s.nom, s.tur, s.faol = body.nom, body.tur, body.faol
    log_action(
        db, module="buxgalteriya", action="schyot", user_id=user.id, message=f"{s.kod} {s.nom}", ip=client_ip(request)
    )
    await db.commit()
    return SchyotRead.model_validate(s)


@router.get("/qoidalar", response_model=list[QoidaIO], operation_id="bux_qoidalar")
async def bux_qoidalar(db: SessionDep, _: BuxUser) -> list[QoidaIO]:
    rows = (await db.execute(select(BuxQoida).order_by(BuxQoida.kalit))).scalars()
    return [QoidaIO.model_validate(q) for q in rows]


@router.put("/qoidalar", response_model=QoidaIO, operation_id="bux_qoida_saqla")
async def bux_qoida_saqla(db: SessionDep, user: BuxUser, body: QoidaIO, request: Request) -> QoidaIO:
    """Qoida o'zgarsa keyingi sinxron eski provodkalarni tuzatish provodkasi bilan qayta tasniflaydi."""
    if (await db.execute(select(BuxSchyot.id).where(BuxSchyot.kod == body.schyot))).scalar_one_or_none() is None:
        raise HTTPException(status_code=422, detail=f"{body.schyot} schyoti yo'q")
    q = (await db.execute(select(BuxQoida).where(BuxQoida.kalit == body.kalit))).scalar_one_or_none()
    if q is None:
        q = BuxQoida(kalit=body.kalit, schyot=body.schyot)
        db.add(q)
    else:
        q.schyot = body.schyot
    log_action(
        db,
        module="buxgalteriya",
        action="qoida",
        user_id=user.id,
        message=f"{q.kalit} → {q.schyot}",
        ip=client_ip(request),
    )
    await db.commit()
    return QoidaIO.model_validate(q)


@router.get("/aylanma-saldo", response_model=list[SaldoRead], operation_id="bux_aylanma_saldo")
async def bux_aylanma_saldo(
    db: SessionDep, _: BuxUser, dan: date | None = None, gacha: date | None = None
) -> list[SaldoRead]:
    """Aylanma-saldo vedomosti; 4010 va 6010 saldolari mijoz/kontragent bo'yicha kengaytirilgan."""
    await _sinx(db)
    g = gacha or b.bugun()
    return [SaldoRead.model_validate(r) for r in await b.aylanma_saldo(db, dan or g.replace(day=1), g)]


@router.get("/aylanma-saldo.csv", operation_id="bux_aylanma_saldo_csv")
async def bux_aylanma_saldo_csv(db: SessionDep, _: BuxUser, dan: date, gacha: date) -> StreamingResponse:
    await _sinx(db)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Schyot", "Nomi", "Bosh. D", "Bosh. K", "Aylanma D", "Aylanma K", "Yakun D", "Yakun K"])
    for r in await b.aylanma_saldo(db, dan, gacha):
        nums = (r.bosh_d, r.bosh_k, r.ayl_d, r.ayl_k, r.yak_d, r.yak_k)
        w.writerow([r.kod, r.nom] + [f"{v:.2f}".replace(".", ",") for v in nums])
    return StreamingResponse(
        iter(["﻿" + buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="aylanma_saldo_{dan}_{gacha}.csv"'},
    )


@router.get("/kartochka/{kod}", response_model=Kartochka, operation_id="bux_kartochka")
async def bux_kartochka(
    db: SessionDep, _: BuxUser, kod: str, dan: date | None = None, gacha: date | None = None
) -> Kartochka:
    await _sinx(db)
    g = gacha or b.bugun()
    d = dan or g.replace(day=1)
    bosh, rows = await b.kartochka(db, kod, d, g)
    s = (await db.execute(select(BuxSchyot).where(BuxSchyot.kod == kod))).scalar_one_or_none()
    yak = bosh + sum((y.summa if y.debet == kod else -y.summa for y in rows), Decimal(0))
    return Kartochka(
        kod=kod,
        nom=s.nom if s else "",
        boshlangich=bosh,
        yozuvlar=[YozuvRead.model_validate(y) for y in rows],
        yakuniy=yak,
    )


@router.get("/nazorat", response_model=list[NazoratRead], operation_id="bux_nazorat")
async def bux_nazorat(db: SessionDep, _: BuxUser) -> list[NazoratRead]:
    """Buxgalteriya schyotlari Kassa, Ombor va Moliya raqamlari bilan mosmi."""
    await _sinx(db)
    return [
        NazoratRead(nom=n.nom, buxgalteriya=n.buxgalteriya, manba=n.manba, farq=n.farq, izoh=n.izoh)
        for n in await b.nazorat(db)
    ]


@router.get("/yozuvlar", response_model=list[YozuvRead], operation_id="bux_yozuvlar")
async def bux_yozuvlar(
    db: SessionDep, _: BuxUser, dan: date | None = None, gacha: date | None = None, qolda: bool = False
) -> list[YozuvRead]:
    """Provodkalar jurnali (`qolda=true` — faqat qo'lda yozilganlar)."""
    await _sinx(db)
    g = gacha or b.bugun()
    q = select(BuxYozuv).where(BuxYozuv.sana >= (dan or g.replace(day=1)), BuxYozuv.sana <= g)
    if qolda:
        q = q.where(BuxYozuv.guruh.is_(None))
    rows = (await db.execute(q.order_by(BuxYozuv.sana.desc(), BuxYozuv.id.desc()).limit(2000))).scalars()
    return [YozuvRead.model_validate(y) for y in rows]


@router.post("/yozuvlar", response_model=YozuvRead, operation_id="bux_yozuv_qosh")
async def bux_yozuv_qosh(db: SessionDep, user: BuxUser, body: YozuvIn, request: Request) -> YozuvRead:
    """Qo'lda provodka (ish haqi hisoblash, asosiy vosita va h.k.)."""
    try:
        y = await b.qolda(
            db,
            sana=body.sana,
            debet=body.debet,
            kredit=body.kredit,
            summa=body.summa,
            izoh=body.izoh,
            user_id=user.id,
            kontragent=body.kontragent,
        )
    except b.BuxXato as e:
        await db.rollback()
        raise _bad(e) from e
    log_action(
        db,
        module="buxgalteriya",
        action="provodka",
        user_id=user.id,
        message=f"D{y.debet} K{y.kredit} {y.summa}: {y.izoh}"[:500],
        ip=client_ip(request),
    )
    await db.commit()
    return YozuvRead.model_validate(y)


@router.post("/yozuvlar/{yozuv_id}/storno", response_model=YozuvRead, operation_id="bux_yozuv_storno")
async def bux_yozuv_storno(db: SessionDep, user: BuxUser, yozuv_id: int, body: StornoIn, request: Request) -> YozuvRead:
    try:
        y = await b.storno(db, yozuv_id, user.id, body.sabab)
    except b.BuxXato as e:
        await db.rollback()
        raise _bad(e) from e
    log_action(
        db,
        module="buxgalteriya",
        action="storno",
        user_id=user.id,
        message=f"#{yozuv_id}: {body.sabab}",
        ip=client_ip(request),
    )
    await db.commit()
    return YozuvRead.model_validate(y)
