"""Tannarx va ish haqi API — `/tannarx/...` (EKO 10): direktor va moliyachi."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import SessionDep, client_ip, require_roles
from app.crud import log_action
from app.models import Post, User
from app.models.enums import UserRole
from app.modules.tannarx import services as t
from app.modules.tannarx.models import IshHaqiQator, IshHaqiVedomost, IshStavka

router = APIRouter(prefix="/tannarx", tags=["tannarx"])

TannarxUser = Annotated[User, Depends(require_roles(UserRole.DIRECTOR, UserRole.MOLIYACHI))]


class TannarxPost(BaseModel):
    id: int
    nom: str
    birlik: str


class StavkaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    process_code: int | None
    narx: Decimal
    amal_boshi: date


class StavkaIn(BaseModel):
    post_id: int
    process_code: Annotated[int, Field(ge=1, le=99)] | None = None
    narx: Annotated[Decimal, Field(ge=0, le=Decimal(10) ** 9)]
    amal_boshi: date


class HaqQator(BaseModel):
    employee_id: int
    hodim: str
    post_id: int
    post: str
    birlik: str
    hajm: Decimal
    skanlar: int
    summa: Decimal
    #: Stavkasi topilmagan skanlar (vedomost yaratilmaydi)
    stavkasiz: int = 0


class VedomostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    no: str
    dan: date
    gacha: date
    holat: str
    jami: Decimal
    skanlar: int
    tasdiqlangan_at: datetime | None
    yaratgan: str | None = None
    tasdiqlagan: str | None = None
    qatorlar: list[HaqQator] = []


class VedomostIn(BaseModel):
    dan: date
    gacha: date


def _bad(e: t.TannarxXato) -> HTTPException:
    return HTTPException(status_code=422, detail=" · ".join(e.xatolar))


async def _postlar(db: SessionDep) -> dict[int, Post]:
    return {p.id: p for p in (await db.execute(select(Post).order_by(Post.order_index))).scalars()}


@router.get("/postlar", response_model=list[TannarxPost], operation_id="tannarx_postlar")
async def tannarx_postlar(db: SessionDep, _: TannarxUser) -> list[TannarxPost]:
    return [TannarxPost(id=p.id, nom=p.name, birlik=p.unit.value) for p in (await _postlar(db)).values()]


@router.get("/stavkalar", response_model=list[StavkaRead], operation_id="tannarx_stavkalar")
async def tannarx_stavkalar(db: SessionDep, _: TannarxUser) -> list[StavkaRead]:
    rows = (await db.execute(select(IshStavka).order_by(IshStavka.post_id, IshStavka.amal_boshi.desc()))).scalars()
    return [StavkaRead.model_validate(s) for s in rows]


@router.post("/stavkalar", response_model=StavkaRead, operation_id="tannarx_stavka_qosh")
async def tannarx_stavka_qosh(db: SessionDep, user: TannarxUser, body: StavkaIn, request: Request) -> StavkaRead:
    """Stavka shu sanadan (tarix). Tasdiqlangan vedomost davriga orqaga yozilmaydi."""
    try:
        s = await t.stavka_qosh(db, body.post_id, body.process_code, body.narx, body.amal_boshi, user.id)
    except t.TannarxXato as e:
        await db.rollback()
        raise _bad(e) from e
    log_action(
        db,
        module="tannarx",
        action="stavka",
        user_id=user.id,
        message=f"post {s.post_id}/{s.process_code or '*'}: {s.narx} so'm, {s.amal_boshi} dan",
        ip=client_ip(request),
    )
    await db.commit()
    return StavkaRead.model_validate(s)


async def _qatorlar(db: SessionDep, haqlar: list[t.SkanHaq] | list[IshHaqiQator]) -> list[HaqQator]:
    posts = await _postlar(db)
    nom = await t.hodim_nomlari(db, {h.employee_id for h in haqlar})
    out = []
    for h in haqlar:
        p = posts.get(h.post_id)
        out.append(
            HaqQator(
                employee_id=h.employee_id,
                hodim=nom.get(h.employee_id, "—"),
                post_id=h.post_id,
                post=p.name if p else "—",
                birlik=p.unit.value if p else "",
                hajm=h.hajm,
                skanlar=h.skanlar,
                summa=h.summa,
                stavkasiz=getattr(h, "stavkasiz", 0),
            )
        )
    return sorted(out, key=lambda q: (q.hodim, q.post))


@router.get("/hisob", response_model=list[HaqQator], operation_id="tannarx_hisob")
async def tannarx_hisob(db: SessionDep, _: TannarxUser, dan: date, gacha: date) -> list[HaqQator]:
    """Davr bo'yicha ish haqi hisobi (oldindan ko'rish) — hodim × post."""
    jam: dict[tuple[int, int], t.SkanHaq] = {}
    for h in await t.skan_haqlari(db, dan, gacha):
        k = (h.employee_id, h.post_id)
        if k in jam:
            a = jam[k]
            jam[k] = t.SkanHaq(
                a.employee_id,
                a.post_id,
                0,
                a.hajm + h.hajm,
                a.skanlar + h.skanlar,
                a.summa + h.summa,
                a.stavkasiz + h.stavkasiz,
            )
        else:
            jam[k] = h
    return await _qatorlar(db, list(jam.values()))


async def _vedomost_read(db: SessionDep, v: IshHaqiVedomost, qatorlar: bool = False) -> VedomostRead:
    ism = {
        u.id: (u.name or u.username)
        for u in (
            await db.execute(select(User).where(User.id.in_([x for x in (v.yaratgan_id, v.tasdiqlagan_id) if x])))
        ).scalars()
    }
    r = VedomostRead.model_validate(v).model_copy(
        update={"yaratgan": ism.get(v.yaratgan_id or 0), "tasdiqlagan": ism.get(v.tasdiqlagan_id or 0)}
    )
    if qatorlar:
        rows = list((await db.execute(select(IshHaqiQator).where(IshHaqiQator.vedomost_id == v.id))).scalars())
        r.qatorlar = await _qatorlar(db, rows)
    return r


@router.get("/vedomostlar", response_model=list[VedomostRead], operation_id="tannarx_vedomostlar")
async def tannarx_vedomostlar(db: SessionDep, _: TannarxUser) -> list[VedomostRead]:
    rows = (await db.execute(select(IshHaqiVedomost).order_by(IshHaqiVedomost.dan.desc()))).scalars()
    return [await _vedomost_read(db, v) for v in rows]


@router.get("/vedomostlar/{vedomost_id}", response_model=VedomostRead, operation_id="tannarx_vedomost")
async def tannarx_vedomost(db: SessionDep, _: TannarxUser, vedomost_id: int) -> VedomostRead:
    v = await db.get(IshHaqiVedomost, vedomost_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Vedomost topilmadi")
    return await _vedomost_read(db, v, qatorlar=True)


async def _amal(db: SessionDep, user: User, request: Request, action: str, v: IshHaqiVedomost) -> VedomostRead:
    log_action(
        db,
        module="tannarx",
        action=action,
        user_id=user.id,
        message=f"{v.no} {v.dan}–{v.gacha}: {v.jami}",
        ip=client_ip(request),
    )
    await db.commit()
    return await _vedomost_read(db, v, qatorlar=True)


@router.post("/vedomostlar", response_model=VedomostRead, operation_id="tannarx_vedomost_yarat")
async def tannarx_vedomost_yarat(db: SessionDep, user: TannarxUser, body: VedomostIn, request: Request) -> VedomostRead:
    try:
        v = await t.vedomost_yarat(db, body.dan, body.gacha, user.id)
    except t.TannarxXato as e:
        await db.rollback()
        raise _bad(e) from e
    return await _amal(db, user, request, "vedomost", v)


@router.post("/vedomostlar/{vedomost_id}/tasdiq", response_model=VedomostRead, operation_id="tannarx_vedomost_tasdiq")
async def tannarx_vedomost_tasdiq(
    db: SessionDep, user: TannarxUser, vedomost_id: int, request: Request
) -> VedomostRead:
    """Ikki kalit: vedomostni yozgan xodim emas, boshqasi tasdiqlaydi."""
    try:
        v = await t.vedomost_tasdiq(db, vedomost_id, user.id)
    except t.TannarxXato as e:
        await db.rollback()
        raise _bad(e) from e
    return await _amal(db, user, request, "vedomost_tasdiq", v)


@router.post("/vedomostlar/{vedomost_id}/bekor", response_model=VedomostRead, operation_id="tannarx_vedomost_bekor")
async def tannarx_vedomost_bekor(db: SessionDep, user: TannarxUser, vedomost_id: int, request: Request) -> VedomostRead:
    try:
        v = await t.vedomost_bekor(db, vedomost_id)
    except t.TannarxXato as e:
        await db.rollback()
        raise _bad(e) from e
    return await _amal(db, user, request, "vedomost_bekor", v)
