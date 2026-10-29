"""Tannarx va ish haqi API — `/tannarx/...` (EKO 10): direktor va moliyachi."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import SessionDep, client_ip, require_roles
from app.core.config import TASHKENT_TZ
from app.crud import log_action
from app.models import Client, Machine, Order, Post, User
from app.models.enums import UserRole
from app.modules.tannarx import norma
from app.modules.tannarx import services as t
from app.modules.tannarx.models import AsbobStavka, IshHaqiQator, IshHaqiVedomost, IshStavka, StanokNarx

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


# ───────────────────────── 10b–10d: stanok, asbob, to'liq tannarx, OEE yo'qotishi ─────────────────────────
class StanokRead(BaseModel):
    id: int
    nom: str
    post: str


class StanokNarxRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    machine_id: int
    soat_narxi: Decimal
    amal_boshi: date


class StanokNarxIn(BaseModel):
    machine_id: int
    soat_narxi: Annotated[Decimal, Field(ge=0, le=Decimal(10) ** 9)]
    amal_boshi: date


class AsbobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amal: str
    narx: Decimal
    amal_boshi: date


class AsbobIn(BaseModel):
    amal: str
    narx: Annotated[Decimal, Field(ge=0, le=Decimal(10) ** 9)]
    amal_boshi: date


class AmalRead(BaseModel):
    kod: str
    nom: str


class TannarxQator(BaseModel):
    order_id: int
    number: str
    mijoz: str | None
    yetkazilgan: date | None
    summa: Decimal
    material: Decimal
    kromka: Decimal
    kromka_metr: Decimal
    mehnat: Decimal
    mehnat_tasdiqlangan: Decimal
    stanok: Decimal
    stanok_soat: Decimal
    asbob: Decimal
    jami: Decimal
    foyda: Decimal
    #: Narxi yozilmagan narsalar — summa to'liq emas
    kamchilik: list[str]


class YoqotishSabab(BaseModel):
    nom: str
    soniya: int
    pul: Decimal | None


class YoqotishQator(BaseModel):
    machine_id: int
    nom: str
    soat_narxi: Decimal | None
    planned_s: int
    oee_pct: float | None
    to_xtash_s: int
    sekin_s: int
    brak_s: int
    to_xtash: Decimal | None
    sekin: Decimal | None
    brak: Decimal | None
    jami: Decimal | None
    sabablar: list[YoqotishSabab]


@router.get("/stanoklar", response_model=list[StanokRead], operation_id="tannarx_stanoklar")
async def tannarx_stanoklar(db: SessionDep, _: TannarxUser) -> list[StanokRead]:
    posts = await _postlar(db)
    q = select(Machine).where(Machine.is_deleted == False).order_by(Machine.post_id, Machine.name)  # noqa: E712
    return [
        StanokRead(id=m.id, nom=m.name, post=posts[m.post_id].name if m.post_id in posts else "—")
        for m in (await db.execute(q)).scalars()
    ]


@router.get("/stanok-narxlari", response_model=list[StanokNarxRead], operation_id="tannarx_stanok_narxlari")
async def tannarx_stanok_narxlari(db: SessionDep, _: TannarxUser) -> list[StanokNarxRead]:
    q = select(StanokNarx).order_by(StanokNarx.machine_id, StanokNarx.amal_boshi.desc())
    return [StanokNarxRead.model_validate(s) for s in (await db.execute(q)).scalars()]


@router.post("/stanok-narxlari", response_model=StanokNarxRead, operation_id="tannarx_stanok_narx_qosh")
async def tannarx_stanok_narx_qosh(
    db: SessionDep, user: TannarxUser, body: StanokNarxIn, request: Request
) -> StanokNarxRead:
    try:
        s = await norma.stanok_narx_qosh(db, body.machine_id, body.soat_narxi, body.amal_boshi, user.id)
    except t.TannarxXato as e:
        await db.rollback()
        raise _bad(e) from e
    log_action(
        db,
        module="tannarx",
        action="stanok_narx",
        user_id=user.id,
        message=f"stanok {s.machine_id}: {s.soat_narxi} so'm/soat, {s.amal_boshi} dan",
        ip=client_ip(request),
    )
    await db.commit()
    return StanokNarxRead.model_validate(s)


@router.get("/asbob/amallar", response_model=list[AmalRead], operation_id="tannarx_asbob_amallar")
async def tannarx_asbob_amallar(_: TannarxUser) -> list[AmalRead]:
    return [AmalRead(kod=k, nom=v) for k, v in norma.AMALLAR.items()]


@router.get("/asbob", response_model=list[AsbobRead], operation_id="tannarx_asbob")
async def tannarx_asbob(db: SessionDep, _: TannarxUser) -> list[AsbobRead]:
    q = select(AsbobStavka).order_by(AsbobStavka.amal, AsbobStavka.amal_boshi.desc())
    return [AsbobRead.model_validate(s) for s in (await db.execute(q)).scalars()]


@router.post("/asbob", response_model=AsbobRead, operation_id="tannarx_asbob_qosh")
async def tannarx_asbob_qosh(db: SessionDep, user: TannarxUser, body: AsbobIn, request: Request) -> AsbobRead:
    try:
        s = await norma.asbob_stavka_qosh(db, body.amal, body.narx, body.amal_boshi, user.id)
    except t.TannarxXato as e:
        await db.rollback()
        raise _bad(e) from e
    log_action(
        db,
        module="tannarx",
        action="asbob",
        user_id=user.id,
        message=f"{s.amal}: {s.narx} so'm, {s.amal_boshi} dan",
        ip=client_ip(request),
    )
    await db.commit()
    return AsbobRead.model_validate(s)


@router.get("/buyurtmalar", response_model=list[TannarxQator], operation_id="tannarx_buyurtmalar")
async def tannarx_buyurtmalar(
    db: SessionDep, _: TannarxUser, dan: date | None = None, gacha: date | None = None, order_id: int | None = None
) -> list[TannarxQator]:
    """To'liq (boshqaruv) tannarx: davrda yetkazilgan buyurtmalar yoki bitta buyurtma (`order_id`)."""
    if order_id is not None:
        o = await db.get(Order, order_id)
        orders = [o] if o is not None else []
    elif dan and gacha:
        orders = await norma.buyurtmalar(db, dan, gacha)
    else:
        raise HTTPException(status_code=422, detail="Davr yoki buyurtma tanlang")
    tn = await norma.buyurtma_tannarxi(db, [o.id for o in orders])
    mijozlar = select(Client).where(Client.id.in_({o.client_id for o in orders}))
    mijoz = {c.id: c.full_name for c in (await db.execute(mijozlar)).scalars()}
    out = []
    for o in orders:
        x = tn[o.id]
        summa = o.amount or Decimal(0)
        out.append(
            TannarxQator(
                order_id=o.id,
                number=o.number,
                mijoz=mijoz.get(o.client_id),
                yetkazilgan=o.delivered_at.astimezone(TASHKENT_TZ).date() if o.delivered_at else None,
                summa=summa,
                material=x.material,
                kromka=x.kromka,
                kromka_metr=x.kromka_metr,
                mehnat=x.mehnat,
                mehnat_tasdiqlangan=x.mehnat_tasdiqlangan,
                stanok=x.stanok,
                stanok_soat=x.stanok_soat,
                asbob=x.asbob,
                jami=x.jami,
                foyda=summa - x.jami,
                kamchilik=sorted(x.kamchilik),
            )
        )
    return out


@router.get("/oee-yoqotish", response_model=list[YoqotishQator], operation_id="tannarx_oee_yoqotish")
async def tannarx_oee_yoqotish(db: SessionDep, _: TannarxUser, dan: date, gacha: date) -> list[YoqotishQator]:
    """Stanoklar: yo'qotilgan vaqt (to'xtash, sekin ishlash, brak) va uning puli soat narxi bilan."""
    out = []
    for y in await norma.oee_yoqotish(db, dan, gacha):
        qism = [y.pul(y.to_xtash_s), y.pul(y.sekin_s), y.pul(y.brak_s)]
        out.append(
            YoqotishQator(
                machine_id=y.machine_id,
                nom=y.nom,
                soat_narxi=y.soat_narxi,
                planned_s=y.planned_s,
                oee_pct=y.oee_pct,
                to_xtash_s=y.to_xtash_s,
                sekin_s=y.sekin_s,
                brak_s=y.brak_s,
                to_xtash=qism[0],
                sekin=qism[1],
                brak=qism[2],
                jami=None if y.soat_narxi is None else sum((q or Decimal(0) for q in qism), Decimal(0)),
                sabablar=[YoqotishSabab(nom=n, soniya=s, pul=y.pul(s)) for n, s in y.sabablar],
            )
        )
    return out
