"""MX Kroy qoldiq ombori API (K3, `MES_QOLDIQ_V1.md`) — `/ombor/kroy/...`.

MX sozlamasi: «Правила остатков → Источник склада: База MES», `mes_url` = `{MES}/api/v1/ombor/kroy`.
Kirish — xizmat tokeni (`KROY_API_TOKEN`, MX da `MES_API_TOKEN`), foydalanuvchi emas.
"""

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import SessionDep, client_ip
from app.crud import log_action
from app.modules.ombor.services import kroy
from app.modules.ombor.services.kroy_auth import kroy_token

router = APIRouter(prefix="/ombor/kroy", tags=["kroy"], dependencies=[Depends(kroy_token)])

Json = Annotated[dict[str, Any], Body()]


@router.get("/remnants", operation_id="kroy_remnants")
async def kroy_remnants(
    db: SessionDep,
    ids: str | None = None,
    material: str | None = Query(None, max_length=200),
    code: str | None = Query(None, max_length=60),
    type: str | None = Query(None, max_length=20),  # noqa: A002 — shartnomadagi nom
    thickness: Decimal | None = None,
    status: str | None = Query(None, pattern=r"^(available|reserved|pending|empty)$"),
    linear: bool | None = None,
) -> dict[str, Any]:
    """Qoldiqlarni qidirish (§1): material kod bo'yicha, kod bo'lmasa nom bo'yicha (harf/bo'shliqsiz)."""
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()] if ids else None
    items = await kroy.search(
        db,
        ids=id_list,
        material=material,
        code=code,
        type_=type,
        thickness=thickness,
        status_=status,
        linear=linear,
    )
    return {"items": items}


@router.post("/remnants/reservations", operation_id="kroy_reservations", response_model=None)
async def kroy_reservations(db: SessionDep, body: Json, request: Request) -> dict[str, Any] | JSONResponse:
    """Band qilish (§2): `add` | `remove` | `set`. Boshqa loyiha bandi — 409 `conflicts`."""
    mode = str(body.get("mode") or "add")
    if mode not in ("add", "remove", "set"):
        raise HTTPException(status_code=400, detail="mode: add | remove | set")
    ids = [int(i) for i in body.get("ids") or []]
    try:
        conflicts = await kroy.reserve(db, body.get("order") or {}, ids, mode)
    except kroy.KroyError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if conflicts:
        await db.rollback()
        return JSONResponse(
            status_code=409,
            content={"conflicts": [{"id": c.id, "order_number": c.order_number} for c in conflicts]},
        )
    log_action(
        db,
        module="kroy",
        action=f"rezerv_{mode}",
        message=f"MX {(body.get('order') or {}).get('number')}: {mode} {ids}"[:500],
        ip=client_ip(request),
    )
    await db.commit()
    return {"ok": True}


@router.post("/remnants/intake", operation_id="kroy_intake")
async def kroy_intake(db: SessionDep, body: Json, request: Request) -> dict[str, Any]:
    """Kroydan keyingi kirim/chiqim (§3): `pieces` — kutish holatida, `consumed` — ombordan chiqadi."""
    try:
        no, ids = await kroy.intake(db, body)
    except kroy.KroyError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e)) from e
    log_action(
        db,
        module="kroy",
        action="kirim",
        message=f"{no}: MX {(body.get('order') or {}).get('number')} · {len(ids)} bo'lak, "
        f"{len(body.get('consumed') or [])} ishlatilgan"[:500],
        ip=client_ip(request),
    )
    await db.commit()
    return {"intake_id": no, "ids": ids}


@router.post("/remnants/intake/{intake_id}/cancel", operation_id="kroy_intake_cancel")
async def kroy_intake_cancel(db: SessionDep, intake_id: str, request: Request) -> dict[str, Any]:
    """Kirimni bekor qilish (§4): ishlatilmagan bo'laklar o'chadi, ishlatilganlar omborga qaytadi."""
    try:
        doc = await kroy.cancel(db, intake_id)
    except kroy.KroyError as e:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(e)) from e
    log_action(db, module="kroy", action="kirim_bekor", message=f"{doc.no} bekor qilindi", ip=client_ip(request))
    await db.commit()
    return {"ok": True, "intake_id": doc.no}
