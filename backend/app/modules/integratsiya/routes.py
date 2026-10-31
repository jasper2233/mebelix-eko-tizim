"""MX Kroy webhook (K4): `POST /integ/kroy/webhook` — MX `MES_WEBHOOK_URL` shu manzil, token `KROY_API_TOKEN`.

Voqealar (`MES_INTEGRATSIYA.md` §3.3): `map.done` (karta listi arradan chiqdi → qoldiq bo'laklari omborga),
`project.status`, `project.reopened`, `remnant.move`, `test`. Hammasi inboxga yoziladi; ishlovi bo'lmagani — saqlanadi.
Ishlovda kutilmagan xato — 500 va hech narsa yozilmaydi: MX navbatida qolib qayta yuboradi.

`POST /integ/kroy/parol-tekshir` — MX SSO rejimida muhim sozlamani (stanok standarti) o'zgartirishdan oldin xodimning
MES parolini tekshiradi (MX da parol yo'q). Faqat xizmat tokeni bilan; xato urinishlar login bo'yicha cheklanadi.
"""

import hashlib
import json
from datetime import date, datetime
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select

from app.api.deps import SessionDep, client_ip, require_roles
from app.core.config import settings
from app.core.exceptions import ForbiddenException, NotFoundException, RateLimitException
from app.core.utils.rate_limit import rate_limiter
from app.crud import crud_users, log_action
from app.models import Client, Order, Part, Product, User
from app.models.enums import OrderStatus, UserRole
from app.modules.integratsiya import kroy, paket
from app.modules.integratsiya.models import IntegInbox, KroyLoyiha, KroyVersiya
from app.modules.ombor import service as ombor
from app.services.giblab import mx_paket

#: MX → MES (xizmat tokeni)
router = APIRouter(prefix="/integ/kroy", tags=["integratsiya"], dependencies=[Depends(ombor.kroy_token)])
#: MES foydalanuvchisi → MX (sessiya bilan; `api/router.py` da `_protected`)
user_router = APIRouter(prefix="/integ/kroy", tags=["integratsiya"])

KroyUser = Annotated[
    User, Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.TEXNOLOG, UserRole.MANAGER))
]


class KroyHolat(BaseModel):
    enabled: bool
    #: MX ochiladigan manzil (origin): MX oynasidan kelgan xabar shu bilan tekshiriladi
    mx_origin: str | None = None


class KroyOchish(BaseModel):
    url: str
    project_id: str
    number: str


def _xesh(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


async def _qolla(db: SessionDep, event: str, body: dict[str, Any]) -> str:
    if event == "map.done":
        n = await ombor.kroy_map_done(
            db, str(body["project_id"]), str(body.get("op_id") or ""), int(body["map"]), int(body.get("done") or 0)
        )
        return f"ochildi:{n}"
    if event == "project.status":
        return await kroy.holat_webhook(db, body)
    if event == "project.reopened":
        return await kroy.qayta_ochildi_webhook(db, body)
    return "saqlandi"


class ParolTekshir(BaseModel):
    login: str = Field(max_length=150)
    password: str = Field(max_length=200)


class ParolNatija(BaseModel):
    ok: bool


@router.post("/parol-tekshir", operation_id="kroy_parol_tekshir")
async def kroy_parol_tekshir(db: SessionDep, body: ParolTekshir, request: Request) -> ParolNatija:
    """Login — MX tokendagi `sub` (MES foydalanuvchi nomi, telefon emas). Nofaol va texnik hisob — `ok: false`.

    Cheklov IP bo'yicha emas, LOGIN bo'yicha: hamma so'rov bitta MX serveridan keladi — IP bo'yicha bo'lsa bitta
    xodimning xatolari butun korxonani to'sib qo'yardi."""
    kalit = f"ratelimit:mxparol:{body.login.strip().lower()}"
    if await rate_limiter.over_limit(kalit, settings.LOGIN_RATE_LIMIT_ATTEMPTS):
        raise RateLimitException()
    user = await crud_users.authenticate(db=db, username_or_phone=body.login, password=body.password)
    ok = user is not None and user.username == body.login and user.is_active and not user.is_system
    if not ok:
        await rate_limiter.bump(kalit, settings.LOGIN_RATE_LIMIT_PERIOD)
    log_action(
        db,
        module="kroy",
        action="mx_parol" if ok else "mx_parol_xato",
        user_id=user.id if ok and user is not None else None,
        message=f"MX stanok standarti uchun parol: {body.login[:40]}",
        ip=client_ip(request),
    )
    await db.commit()
    return ParolNatija(ok=ok)


@router.post("/webhook", operation_id="kroy_webhook", response_model=None)
async def kroy_webhook(db: SessionDep, body: Annotated[dict[str, Any], Body()], request: Request) -> JSONResponse:
    event = str(body.get("event") or "")[:40]
    if not event:
        return JSONResponse(status_code=400, content={"detail": "event bo'sh"})
    xesh = _xesh(body)
    kalit = str(body.get("event_id") or f"{event}:{xesh}")[:200]
    bor = (
        await db.execute(select(IntegInbox).where(IntegInbox.manba == "kroy", IntegInbox.kalit == kalit))
    ).scalar_one_or_none()
    if bor is not None:
        if bor.xesh != xesh:
            return JSONResponse(status_code=409, content={"status": "conflict", "detail": "kalit boshqa mazmun bilan"})
        return JSONResponse(status_code=200, content={"status": "duplicate"})
    natija = await _qolla(db, event, body)
    db.add(IntegInbox(manba="kroy", kalit=kalit, tur=event, xesh=xesh, payload=body, natija=natija))
    log_action(db, module="kroy", action=f"webhook_{event}", message=natija, ip=client_ip(request))
    await db.commit()
    return JSONResponse(status_code=201, content={"status": "accepted", "natija": natija})


@user_router.get("/holat", response_model=KroyHolat, operation_id="kroy_holat")
async def kroy_holat(_: KroyUser) -> KroyHolat:
    """MX Kroy ulanganmi — buyurtma sahifasidagi «Kroy» tugmasi shunga qarab ko'rinadi."""
    url = urlsplit(settings.MX_PUBLIC_URL or settings.MX_URL or "")
    return KroyHolat(enabled=kroy.enabled(), mx_origin=f"{url.scheme}://{url.netloc}" if url.netloc else None)


@user_router.post("/orders/{order_id}/ochish", response_model=KroyOchish, operation_id="kroy_ochish")
async def kroy_ochish(db: SessionDep, user: KroyUser, order_id: int, request: Request) -> KroyOchish:
    """K1 + K6: MX da buyurtma loyihasini yaratadi yoki yangilaydi va uni foydalanuvchi nomidan ochish manzili."""
    order = await db.get(Order, order_id)
    if order is None or order.is_deleted:
        raise NotFoundException("Buyurtma topilmadi.")
    try:
        link, url = await kroy.ochish(db, order, user)
    except kroy.KroyXato as e:
        await db.rollback()
        raise HTTPException(status_code=502, detail=str(e)) from e
    log_action(
        db,
        module="kroy",
        action="ochish",
        user_id=user.id,
        entity_type="order",
        entity_id=order.id,
        message=f"MX loyiha {link.number} ({link.project_id})",
        ip=client_ip(request),
    )
    await db.commit()
    return KroyOchish(url=url, project_id=link.project_id, number=link.number)


#: Kroyni tozalash — `.project` yuklash bilan bir xil huquq (texnolog), nazorat uchun direktor
KroyTexnolog = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.TEXNOLOG))]


class KroyVersiyaQator(BaseModel):
    versiya: int
    manba: str
    kim: str
    vaqt: datetime
    listlar: int
    nusxalar: int


class KroyVersiyalar(BaseModel):
    versiyalar: list[KroyVersiyaQator]
    #: MX da loyiha oxirgi qabuldan keyin qayta ochilgan
    qayta_ochilgan: bool
    #: Oxirgi versiya oldingisidan nimasi bilan farq qiladi
    farq: list[str]


#: Paketdagi sarf birligi (`consumption[].unit`) → ko'rinadigan nom
BIRLIK = {"sheets": "list", **mx_paket.BIRLIK}


def _son(v: float) -> str:
    return f"{v:g}".replace(".", ",")


def _farq(eski: dict[str, Any], yangi: dict[str, Any]) -> list[str]:
    """Texnolog qayta yuborishda ko'radigan farq: listlar, nusxalar, detallar, material sarfi."""
    out: list[str] = []
    for nom, kalit in (("Listlar", "listlar"), ("Detal nusxalari", "nusxalar")):
        if eski.get(kalit) != yangi.get(kalit):
            out.append(f"{nom}: {eski.get(kalit)} → {yangi.get(kalit)}")
    ed, yd = eski.get("detallar") or {}, yangi.get("detallar") or {}
    qoshilgan, olingan = sorted(set(yd) - set(ed)), sorted(set(ed) - set(yd))
    ozgargan = [k for k in sorted(set(ed) & set(yd)) if ed[k] != yd[k]]
    for nom, q in (("Qo'shilgan detal", qoshilgan), ("Olib tashlangan detal", olingan), ("O'zgargan detal", ozgargan)):
        if q:
            nomlar = ", ".join((yd.get(k) or ed.get(k) or {}).get("nom") or k for k in q[:5])
            out.append(f"{nom}: {len(q)} ta ({nomlar}{' …' if len(q) > 5 else ''})")
    es, ys = eski.get("sarf") or {}, yangi.get("sarf") or {}
    for m in sorted(set(es) | set(ys)):
        a, b = (es.get(m) or [0, ""]), (ys.get(m) or [0, ""])
        if a[0] != b[0]:
            out.append(f"{m}: {_son(a[0])} → {_son(b[0])} {BIRLIK.get(b[1] or a[1], b[1] or a[1])}".rstrip())
    return out


@user_router.get("/orders/{order_id}/versiyalar", response_model=KroyVersiyalar, operation_id="kroy_versiyalar")
async def kroy_versiyalar(db: SessionDep, _: KroyUser, order_id: int) -> KroyVersiyalar:
    """Buyurtmaga qabul qilingan kroy versiyalari (yangisi birinchi) va oxirgi farq."""
    rows = (
        await db.execute(
            select(KroyVersiya, User.name, User.username)
            .join(User, User.id == KroyVersiya.user_id, isouter=True)
            .where(KroyVersiya.order_id == order_id)
            .order_by(KroyVersiya.versiya.desc())
        )
    ).all()
    link = (await db.execute(select(KroyLoyiha).where(KroyLoyiha.order_id == order_id))).scalar_one_or_none()
    # Tozalangan yoki `.project` bilan almashtirilgan kroyda oxirgi MX versiyasi endi amalda emas
    order = await db.get(Order, order_id)
    if order is None or not (order.project_uuid or "").startswith("mx:"):
        rows = []
    return KroyVersiyalar(
        versiyalar=[
            KroyVersiyaQator(
                versiya=v.versiya,
                manba=v.manba,
                kim=name or username or "—",
                vaqt=v.created_at,
                listlar=int(v.xulosa.get("listlar") or 0),
                nusxalar=int(v.xulosa.get("nusxalar") or 0),
            )
            for v, name, username in rows
        ],
        qayta_ochilgan=bool(link and link.qayta_ochilgan),
        farq=_farq(rows[1][0].xulosa, rows[0][0].xulosa) if len(rows) > 1 else [],
    )


class KroyBuyurtma(BaseModel):
    id: int
    number: str
    nom: str
    mijoz: str
    muddat: date | None
    #: Kroyi bor: uzatilmagan buyurtmada u almashadi
    kroy_bor: bool
    versiya: int | None
    #: Buyurtma bog'langan MX loyihasi (ID va raqam): yangisi tanlansa u ajraladi
    mx_loyiha: str | None
    mx_raqam: str | None


class KroyTekshirIn(BaseModel):
    order_id: int | None = None
    customer: str = ""
    #: MES paketi (`files=meta`, stanok fayllarisiz) — solishtirish uchun
    paket: dict[str, Any]


class KroyTekshir(BaseModel):
    buyurtma: KroyBuyurtma
    #: Yuborilayotgan kroy: mahsulotlar kodi, detal turlari, nusxalar, listlar
    mahsulotlar: list[str]
    turlar: int
    nusxalar: int
    listlar: int
    #: Avvalgi kroy qisqacha; yo'q bo'lsa null
    avvalgi: str | None
    ogoh: list[str]


def _bir_xil_mijoz(a: str, b: str) -> bool:
    x, y = " ".join(a.lower().split()), " ".join(b.lower().split())
    return bool(x and y) and (x in y or y in x)


async def _buyurtma_kartasi(db: SessionDep, order: Order, mijoz: str) -> KroyBuyurtma:
    link = (await db.execute(select(KroyLoyiha).where(KroyLoyiha.order_id == order.id))).scalar_one_or_none()
    versiya = None
    if order.project_uuid and order.project_uuid.startswith("mx:"):
        versiya = (
            await db.execute(select(func.max(KroyVersiya.versiya)).where(KroyVersiya.order_id == order.id))
        ).scalar_one()
    return KroyBuyurtma(
        id=order.id,
        number=order.number,
        nom=order.project_name or "",
        mijoz=mijoz,
        muddat=order.deadline,
        kroy_bor=order.project_uuid is not None,
        versiya=versiya,
        mx_loyiha=link.project_id if link else None,
        mx_raqam=link.number if link else None,
    )


@router.get("/buyurtmalar", operation_id="kroy_ochiq_buyurtmalar", response_model=None)
async def kroy_ochiq_buyurtmalar(
    db: SessionDep,
    x_mes_user_token: Annotated[str | None, Header()] = None,
    q: str = Query(default="", max_length=100),
    customer: str = Query(default="", max_length=200),
) -> JSONResponse | list[KroyBuyurtma]:
    """MX da tanlash uchun: ishlab chiqarishga uzatilmagan («Texnologda») buyurtmalar, mijozi mos kelgani birinchi."""
    user = await _yuboruvchi(db, x_mes_user_token)
    if isinstance(user, JSONResponse):
        return user
    so_rov = (
        select(Order, Client.full_name)
        .join(Client, Client.id == Order.client_id)
        .where(Order.status == OrderStatus.TECHNICAL_REVIEW, Order.is_deleted == False)  # noqa: E712
        .order_by(Order.id.desc())
        .limit(100)
    )
    t = q.strip()
    if t:
        naqsh = "%" + t.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        so_rov = so_rov.where(
            or_(
                Order.number.ilike(naqsh, escape="\\"),
                Order.project_name.ilike(naqsh, escape="\\"),
                Client.full_name.ilike(naqsh, escape="\\"),
            )
        )
    qatorlar = [await _buyurtma_kartasi(db, o, nom) for o, nom in (await db.execute(so_rov)).all()]
    # sorted barqaror: bir xil guruh ichida yangisi birinchi qoladi
    return sorted(qatorlar, key=lambda b: not _bir_xil_mijoz(customer, b.mijoz))


@router.post("/loyiha/{project_id}/tekshir", operation_id="kroy_tekshir", response_model=None)
async def kroy_tekshir(
    db: SessionDep,
    project_id: str,
    body: KroyTekshirIn,
    x_mes_user_token: Annotated[str | None, Header()] = None,
) -> JSONResponse | KroyTekshir:
    """Yuborishdan oldingi tasdiq oynasi uchun: buyurtma va mos kelmaslik ogohlantirishlari. Hech narsa yozmaydi."""
    user = await _yuboruvchi(db, x_mes_user_token)
    if isinstance(user, JSONResponse):
        return user
    link = (await db.execute(select(KroyLoyiha).where(KroyLoyiha.project_id == project_id))).scalar_one_or_none()
    if body.order_id is not None and link is not None and link.order_id != body.order_id:
        return JSONResponse(status_code=409, content={"detail": "Bu loyiha boshqa buyurtmaga bog'langan."})
    order = await db.get(Order, body.order_id if body.order_id is not None else (link.order_id if link else 0))
    if order is None or order.is_deleted:
        return JSONResponse(status_code=404, content={"detail": "Buyurtma topilmadi."})
    mijoz = await db.get(Client, order.client_id)
    karta = await _buyurtma_kartasi(db, order, mijoz.full_name if mijoz else "")
    x = paket.xulosa(body.paket)
    mahsulotlar = sorted({str(p.get("code") or p.get("name") or "") for p in body.paket.get("products") or []})
    ogoh: list[str] = []
    if body.customer.strip() and karta.mijoz and not _bir_xil_mijoz(body.customer, karta.mijoz):
        ogoh.append(f"MX dagi buyurtmachi «{body.customer.strip()}», MES dagi mijoz «{karta.mijoz}».")
    if karta.mx_loyiha and karta.mx_loyiha != project_id:
        ogoh.append(f"Buyurtma MX {karta.mx_raqam} loyihasiga bog'langan: u ajratiladi.")
    avvalgi = None
    if order.project_uuid is not None:
        eski = (
            await db.execute(
                select(Product.code, func.count(Part.id), func.coalesce(func.sum(Part.count), 0))
                .join(Part, Part.product_id == Product.id)
                .where(Part.order_id == order.id, Part.is_deleted == False, Product.is_deleted == False)  # noqa: E712
                .group_by(Product.code)
            )
        ).all()
        eski_turlar, eski_nusxa = sum(r[1] for r in eski), sum(int(r[2]) for r in eski)
        eski_kodlar = {str(r[0]) for r in eski}
        avvalgi = f"{karta.versiya}-versiya: " if karta.versiya else "Yuklangan fayl: "
        avvalgi += f"{eski_turlar} xil, {eski_nusxa} dona"
        ogoh.append(f"Buyurtmada kroy bor ({avvalgi}): u almashadi.")
        if eski_kodlar and mahsulotlar and not (eski_kodlar & set(mahsulotlar)):
            ogoh.append(
                f"Mahsulot boshqa: avvalgi {', '.join(sorted(eski_kodlar)[:3])}, yangisi {', '.join(mahsulotlar[:3])}."
            )
        katta, kichik = max(eski_nusxa, x["nusxalar"]), min(eski_nusxa, x["nusxalar"])
        if katta >= 5 and kichik * 10 < katta * 7:
            ogoh.append(f"Detal soni keskin farq qiladi: avvalgi {eski_nusxa}, yangisi {x['nusxalar']} dona.")
    return KroyTekshir(
        buyurtma=karta,
        mahsulotlar=mahsulotlar,
        turlar=len(x["detallar"]),
        nusxalar=x["nusxalar"],
        listlar=x["listlar"],
        avvalgi=avvalgi,
        ogoh=ogoh,
    )


@user_router.post("/orders/{order_id}/kroy-tozala", response_model=KroyHolat, operation_id="kroy_tozala")
async def kroy_tozala(db: SessionDep, user: KroyTexnolog, order_id: int, request: Request) -> KroyHolat:
    """Noto'g'ri tanlangan kroyni buyurtmadan olib tashlash: uzatilmagan va skansiz buyurtmada."""
    order = await db.get(Order, order_id)
    if order is None or order.is_deleted:
        raise NotFoundException("Buyurtma topilmadi.")
    if order.project_uuid is None:
        raise ForbiddenException("Bu buyurtmada kroy yo'q.")
    await paket.tozala(db, order, user_id=user.id, ip=client_ip(request))
    return KroyHolat(enabled=kroy.enabled())


#: «MES ga yuborish» huquqi — `.project` yuklash bilan bir xil (texnolog), nazorat uchun direktor
YUBORUVCHI = {UserRole.ADMIN, UserRole.DIRECTOR, UserRole.TEXNOLOG}


async def _yuboruvchi(db: SessionDep, token: str | None) -> User | JSONResponse:
    """MX orqali kelgan xodim: MES imzolagan SSO token bo'yicha; huquqi bo'lmasa — tayyor javob."""
    if not token:
        return JSONResponse(status_code=401, content={"detail": "MX ga MES dagi «Kroy (MX)» tugmasi orqali kiring."})
    try:
        login = kroy.token_login(token)
    except kroy.KroyXato as e:
        return JSONResponse(status_code=401, content={"detail": str(e)})
    user = (await db.execute(select(User).where(User.username == login))).scalar_one_or_none()
    if user is None or not user.is_active or user.is_system:
        return JSONResponse(status_code=403, content={"detail": "Foydalanuvchi faol emas."})
    if not user.is_superuser and UserRole(user.role) not in YUBORUVCHI:
        return JSONResponse(status_code=403, content={"detail": "Kroyni MES ga faqat texnolog yoki direktor yuboradi."})
    return user


@router.post("/loyiha/{project_id}/paket", operation_id="kroy_paket_yuborish", response_model=None)
async def kroy_paket_yuborish(
    db: SessionDep,
    project_id: str,
    body: Annotated[dict[str, Any], Body()],
    request: Request,
    x_mes_user_token: Annotated[str | None, Header()] = None,
    order_id: int | None = None,
) -> JSONResponse:
    """K2 (MX yuboradi, `MES_PAKET_V1.md` §2): xodim tokeni bilan: kim yuborgani yoziladi, huquq shu yerda.

    `order_id` — MX da MES siz ochilgan loyiha shu buyurtmaga biriktiriladi (paket qabul qilingach bog'lanish yoziladi).
    201 `{order_id, order_number, mijoz, redirect_url, version, message, warnings}`; xato — `{detail}`."""
    user = await _yuboruvchi(db, x_mes_user_token)
    if isinstance(user, JSONResponse):
        return user
    link = (await db.execute(select(KroyLoyiha).where(KroyLoyiha.project_id == project_id))).scalar_one_or_none()
    if order_id is not None and link is not None and link.order_id != order_id:
        boshqa = await db.get(Order, link.order_id)
        return JSONResponse(
            status_code=409,
            content={
                "detail": f"Bu loyiha {boshqa.number if boshqa else ''} buyurtmasiga bog'langan.".replace("  ", " ")
            },
        )
    order = await db.get(Order, order_id if order_id is not None else (link.order_id if link else 0))
    if order is None or order.is_deleted:
        return JSONResponse(status_code=404, content={"detail": "Bu loyiha MES buyurtmasiga bog'lanmagan."})
    if link is None and order.status != OrderStatus.TECHNICAL_REVIEW:
        return JSONResponse(
            status_code=409,
            content={"detail": f"{order.number}: faqat «Texnologda» holatidagi buyurtmaga biriktiriladi."},
        )
    try:
        res = await paket.qabul(db, order, body, user_id=user.id, ip=client_ip(request))
    except paket.ParseError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    except ForbiddenException as e:
        return JSONResponse(status_code=409, content={"detail": e.detail})
    versiya = (
        await db.execute(select(func.max(KroyVersiya.versiya)).where(KroyVersiya.order_id == order.id))
    ).scalar_one()
    mijoz = await db.get(Client, order.client_id)
    return JSONResponse(
        status_code=201,
        content={
            "order_id": order.id,
            "order_number": order.number,
            "mijoz": mijoz.full_name if mijoz else "",
            "redirect_url": f"/orders/{order.id}",
            "version": versiya,
            "message": res.message,
            "warnings": res.warnings,
        },
    )
