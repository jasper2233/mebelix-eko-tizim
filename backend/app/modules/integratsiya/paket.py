"""MX Kroy paketini buyurtmaga qabul qilish (K2) — `MES_PAKET_V1.md` §2.

Ikki yo'l, bitta ishlov:
- MX yuboradi (`POST /integ/kroy/orders/{id}/kroy-package`, xizmat tokeni) — MX dagi «MES» tugmasi;
- MES o'zi oladi («Kroyni olish» — `GET {MX}/api/projects/{pid}/mes-package`), bog'langan loyihadan.

Paket `.project` yuklash bilan AYNAN bir yo'ldan o'tadi (`orders/files.py: load_project`): qayta yuklash qoidasi
(postda skan bo'lsa rad), qo'lda marshrutlar saqlanadi, rezerv quriladi. Stanok fayllari shu tranzaksiyada saqlanadi.
"""

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.orders._common import _require_editable
from app.api.routes.orders.files import load_project
from app.core.exceptions import ForbiddenException
from app.models import Order, OrderFile
from app.models.enums import FileKind, OrderStatus
from app.modules.integratsiya import kroy
from app.modules.integratsiya.models import KroyLoyiha
from app.schemas.orders import ProjectUploadResult
from app.services.giblab.models import ParseError
from app.services.giblab.mx_paket import MxPaket, parse_package


async def qabul(
    db: AsyncSession, order: Order, pkg: dict[str, Any], *, user_id: int | None, ip: str | None
) -> ProjectUploadResult:
    """Paketni buyurtmaga yozadi va commit qiladi. Xato — `ParseError` (422) yoki `ForbiddenException`."""
    if order.status == OrderStatus.DRAFT:
        raise ForbiddenException("Kroy faqat tasdiqlangan buyurtmaga yuklanadi.")
    await _require_editable(db, order, "Kroyni qayta yuklab bo'lmaydi")
    mp = parse_package(pkg, order.number)
    raw = json.dumps(pkg, ensure_ascii=False).encode()

    async def fayllar(root: Path) -> None:
        await _stanok_fayllari(db, order, mp, root)
        await _bogla(db, order, mp)

    qayta = order.project_uuid is not None
    return await load_project(
        db,
        order,
        mp.project,
        raw,
        f"{mp.project_name or order.number}.json",
        user_id=user_id,
        ip=ip,
        message=f"MX Kroy paketi {'qayta ' if qayta else ''}qabul qilindi: loyiha {mp.project_number} "
        f"({len(mp.files)} stanok fayli)",
        after_ingest=fayllar,
        raw_kind=FileKind.KROY_PAKET,
        cutmap=mp.cutmap,
        waste_items=mp.waste_items,
        write_scx=False,
    )


async def _stanok_fayllari(db: AsyncSession, order: Order, mp: MxPaket, root: Path) -> None:
    for f in mp.files:
        # Bir xil fayl nomi bir nechta stanokda bo'lishi mumkin (`*.zip`) — har stanok o'z papkasida
        d = root / "projects" / str(order.id) / "stanok" / (Path(f.machine_key).name or "stanok")
        d.mkdir(parents=True, exist_ok=True)
        path = d / (Path(f.file_name).name or "fayl")
        path.write_bytes(f.content)
        db.add(
            OrderFile(
                order_id=order.id,
                kind=FileKind.STANOK,
                path=str(path.relative_to(root)),
                filename=path.name,
                size=len(f.content),
                meta={
                    "format_id": f.format_id,
                    "stanok": f.machine_name,
                    "guruh": f.group,
                    "sha256": f.sha256,
                    "detallar": f.part_keys,
                },
            )
        )


async def _bogla(db: AsyncSession, order: Order, mp: MxPaket) -> None:
    """MX yuborgan bo'lsa (MES «Kroy» tugmasisiz) ham buyurtma ↔ loyiha bog'lansin."""
    link = (await db.execute(select(KroyLoyiha).where(KroyLoyiha.order_id == order.id))).scalar_one_or_none()
    if link is None:
        db.add(KroyLoyiha(order_id=order.id, project_id=mp.project_id, number=mp.project_number))
    else:
        link.project_id, link.number = mp.project_id, mp.project_number
    await db.flush()


async def olish(db: AsyncSession, order: Order) -> dict[str, Any]:
    """Bog'langan MX loyihasidan paketni oladi (faqat korxonada ishlatiladigan stanoklar fayllari bilan)."""
    link = (await db.execute(select(KroyLoyiha).where(KroyLoyiha.order_id == order.id))).scalar_one_or_none()
    if link is None:
        raise kroy.KroyXato("Bu buyurtma MX Kroy loyihasiga bog'lanmagan — avval «Kroy (MX)» ni bosing.")
    code, pkg = await kroy.mx_get(
        f"/projects/{link.project_id}/mes-package?version=1&pp=enabled&files=inline"
        f"&mes_order_id={order.id}&mes_order_number={order.number}"
    )
    if code != 200 or not isinstance(pkg, dict):
        detail = pkg.get("detail") if isinstance(pkg, dict) else None
        raise kroy.KroyXato(f"MX Kroy paketni bermadi ({code}): {detail or ''}".strip())
    if not pkg.get("cut_maps"):
        raise kroy.KroyXato("MX loyihasida kroy hali qilinmagan — avval MX da kesishni hisoblang.")
    return pkg


__all__ = ["ParseError", "olish", "qabul"]
