"""MX Kroy paketini buyurtmaga qabul qilish (K2) — `MES_PAKET_V1.md` §2.

Ikki yo'l, bitta ishlov:
- MX yuboradi (`POST /integ/kroy/loyiha/{project_id}/paket`, xizmat tokeni + xodim tokeni) — MX dagi «MES ga yuborish»;
- MES o'zi oladi («Kroyni olish» — `GET {MX}/api/projects/{pid}/mes-package`), bog'langan loyihadan.

Paket `.project` yuklash bilan AYNAN bir yo'ldan o'tadi (`orders/files.py: load_project`): qayta yuklash qoidasi
(postda skan bo'lsa rad), qo'lda marshrutlar saqlanadi, rezerv quriladi. Stanok fayllari shu tranzaksiyada saqlanadi.
"""

import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.orders._common import _require_editable
from app.api.routes.orders.files import load_project
from app.core.exceptions import ForbiddenException
from app.models import Order, OrderFile, WasteItem
from app.models.enums import FileKind, OrderStatus
from app.modules.integratsiya import kroy
from app.modules.integratsiya.models import KroyLoyiha, KroyVersiya
from app.modules.integratsiya.outbox import navbatga
from app.modules.ombor import service as ombor
from app.schemas.orders import ProjectUploadResult
from app.services.giblab.models import ParseError
from app.services.giblab.mx_paket import MxPaket, parse_package


async def qabul(
    db: AsyncSession, order: Order, pkg: dict[str, Any], *, user_id: int | None, ip: str | None, manba: str
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
        await _yorliqla(db, order, mp)
        await _versiya(db, order, pkg, manba, user_id)

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


def xulosa(pkg: dict[str, Any]) -> dict[str, Any]:
    """Versiyalarni solishtirish uchun paketning qisqa ko'rinishi (stanok fayllari mazmunisiz)."""
    detallar = {
        str(d.get("key")): {
            "nom": str(d.get("name") or d.get("code") or ""),
            "soni": len(d.get("instances") or []),
            "L": d.get("length"),
            "W": d.get("width"),
        }
        for d in pkg.get("parts") or []
    }
    sarf: dict[str, list[Any]] = {}
    for c in pkg.get("consumption") or []:
        q = sarf.setdefault(str(c.get("name") or c.get("code") or ""), [0.0, str(c.get("unit") or "")])
        q[0] = round(q[0] + float(c.get("qty") or 0), 3)
    return {
        "detallar": detallar,
        "nusxalar": sum(d["soni"] for d in detallar.values()),
        "listlar": sum(int(s.get("mult") or 1) for m in pkg.get("cut_maps") or [] for s in m.get("sheets") or []),
        "fayllar": len(pkg.get("postprocessor_files") or []),
        "sarf": sarf,
    }


async def _versiya(db: AsyncSession, order: Order, pkg: dict[str, Any], manba: str, user_id: int | None) -> None:
    """Paket qabul qilish tranzaksiyasi ichida: yangi versiya; MES o'zi olgan bo'lsa MX da loyiha qulflanadi."""
    link = (await db.execute(select(KroyLoyiha).where(KroyLoyiha.order_id == order.id))).scalar_one_or_none()
    oxirgi = (
        await db.execute(select(func.max(KroyVersiya.versiya)).where(KroyVersiya.order_id == order.id))
    ).scalar_one()
    versiya = int(oxirgi or 0) + 1
    db.add(KroyVersiya(order_id=order.id, versiya=versiya, manba=manba, user_id=user_id, xulosa=xulosa(pkg)))
    if link is not None:
        link.qayta_ochilgan = False
        if manba == "mes":
            # MX o'zi yuborganda qulfni o'zi qo'yadi; bu yerda — kroy MES ga o'tganini MX ham bilsin
            await navbatga(
                db,
                f"kroy-qulf:{order.id}:{versiya}",
                "POST",
                f"/projects/{link.project_id}/mes-sent",
                {"version": versiya, "order_number": order.number},
            )
    await db.flush()


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


async def _yorliqla(db: AsyncSession, order: Order, mp: MxPaket) -> None:
    """Paketdagi qoldiqlar (`ATX-…`, arra chek chiqaradi) ↔ MX kirimidagi bo'laklar (ombor) — bir jismoniy bo'lak."""
    await db.flush()
    kartalar = {
        int(sh["no"]): (str(sh["mx_op"]), int(sh["mx_index"]))
        for mat in mp.cutmap.model.get("materials", [])
        for sh in mat.get("sheets", [])
        if sh.get("mx_op") and sh.get("mx_index")
    }
    qoldiqlar = [
        (w.id, w.qr_text, w.sheet_no, float(w.length), float(w.width))
        for w in (
            await db.execute(
                select(WasteItem).where(WasteItem.order_id == order.id, WasteItem.is_deleted == False)  # noqa: E712
            )
        ).scalars()
    ]
    await ombor.kroy_yorliqla(db, mp.project_id, kartalar, qoldiqlar)


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
