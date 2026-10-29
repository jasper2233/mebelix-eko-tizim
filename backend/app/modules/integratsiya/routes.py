"""MX Kroy webhook (K4): `POST /integ/kroy/webhook` — MX `MES_WEBHOOK_URL` shu manzil, token `KROY_API_TOKEN`.

Voqealar (`MES_INTEGRATSIYA.md` §3.3): `map.done` (karta listi arradan chiqdi → qoldiq bo'laklari omborga),
`project.status`, `remnant.move`, `test`. Hammasi inboxga yoziladi; ishlovi bo'lmagani — saqlanadi.
Ishlovda kutilmagan xato — 500 va hech narsa yozilmaydi: MX navbatida qolib qayta yuboradi.
"""

import hashlib
import json
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import SessionDep, client_ip, require_roles
from app.core.exceptions import ForbiddenException, NotFoundException
from app.crud import log_action
from app.models import Order, User
from app.models.enums import UserRole
from app.modules.integratsiya import kroy, paket
from app.modules.integratsiya.models import IntegInbox
from app.modules.ombor import service as ombor
from app.schemas.orders import ProjectUploadResult

#: MX → MES (xizmat tokeni)
router = APIRouter(prefix="/integ/kroy", tags=["integratsiya"], dependencies=[Depends(ombor.kroy_token)])
#: MES foydalanuvchisi → MX (sessiya bilan; `api/router.py` da `_protected`)
user_router = APIRouter(prefix="/integ/kroy", tags=["integratsiya"])

KroyUser = Annotated[
    User, Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.TEXNOLOG, UserRole.MANAGER))
]


class KroyHolat(BaseModel):
    enabled: bool


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
    return "saqlandi"


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
    return KroyHolat(enabled=kroy.enabled())


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


#: Kroy natijasini buyurtmaga yuklash — `.project` yuklash bilan bir xil huquq (texnolog), nazorat uchun direktor
KroyTexnolog = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.DIRECTOR, UserRole.TEXNOLOG))]


@user_router.post("/orders/{order_id}/kroy-olish", response_model=ProjectUploadResult, operation_id="kroy_olish")
async def kroy_olish(db: SessionDep, user: KroyTexnolog, order_id: int, request: Request) -> ProjectUploadResult:
    """K2 (MES oladi): bog'langan MX loyihasidan kroy paketini olib, buyurtmaga yozadi — `.project` o'rnida."""
    order = await db.get(Order, order_id)
    if order is None or order.is_deleted:
        raise NotFoundException("Buyurtma topilmadi.")
    try:
        pkg = await paket.olish(db, order)
        return await paket.qabul(db, order, pkg, user_id=user.id, ip=client_ip(request))
    except kroy.KroyXato as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except paket.ParseError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/orders/{order_id}/kroy-package", operation_id="kroy_package_push", response_model=None)
async def kroy_package_push(
    db: SessionDep, order_id: int, body: Annotated[dict[str, Any], Body()], request: Request
) -> JSONResponse:
    """K2 (MX yuboradi, `MES_PAKET_V1.md` §2): 201 `{order_id, order_number, redirect_url}`; xato — `{detail}`."""
    order = await db.get(Order, order_id)
    if order is None or order.is_deleted:
        return JSONResponse(status_code=404, content={"detail": "Buyurtma topilmadi."})
    try:
        res = await paket.qabul(db, order, body, user_id=None, ip=client_ip(request))
    except paket.ParseError as e:
        return JSONResponse(status_code=422, content={"detail": str(e)})
    except ForbiddenException as e:
        return JSONResponse(status_code=409, content={"detail": e.detail})
    return JSONResponse(
        status_code=201,
        content={
            "order_id": order.id,
            "order_number": order.number,
            "redirect_url": f"/orders/{order.id}",
            "message": res.message,
            "warnings": res.warnings,
        },
    )
