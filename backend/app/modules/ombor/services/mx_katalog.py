"""MES katalogi → MX Kroy katalogi shakli (K5, MX `POST /api/catalog/sync`, `CatalogIn`).

MX faqat kesadi: unga listlar va panellar (`M` katalogi → `sheet`) va kromka (`F-KM` → `edge`) kerak, furnitura
emas. Guruhlar MX da papka (`folder`). ID — MES kodi (`M-LD-054-03`): MX paketida `code` shu bo'lib qaytadi va
rezerv uni katalogga O'ZI moslaydi (EKO 3c). Narx — sotuv narxi (MX loyiha narxini shundan hisoblaydi).
"""

import re
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ombor.models import CatalogItem

ILDIZ = "mes"


def _olcham(size_text: str | None) -> list[float]:
    return [float(x.replace(",", ".")) for x in re.findall(r"\d+(?:[.,]\d+)?", size_text or "")]


def _item(c: CatalogItem) -> dict[str, Any]:
    edge = c.group_code == "KM"
    o = _olcham(c.size_text)
    d: dict[str, Any] = {
        "id": c.code,
        "parent_id": f"{ILDIZ}:{c.catalog}-{c.group_code}",
        "kind": "edge" if edge else "sheet",
        "code": c.code,
        "name": c.name[:300],
        "unit": c.unit or "",
        "price": float(c.sale_price or 0),
        "stock": max(float(c.quantity), 0.0),
        "thickness": float(c.thickness_mm) if c.thickness_mm is not None else (o[2] if len(o) > 2 else None),
        "params": {k: v for k, v in {"decor": c.decor_name, "article": c.article}.items() if v},
    }
    if edge:
        # Kromka: o'lcham matni «19x0.4» — eni va qalinligi
        if o:
            d["width"] = o[0]
        if len(o) > 1 and d["thickness"] is None:
            d["thickness"] = o[1]
    elif len(o) >= 2:
        d["length"], d["width"] = o[0], o[1]
    return d


async def items(db: AsyncSession) -> list[dict[str, Any]]:
    """Papkalar (avval) va pozitsiyalar — MX `CatalogIn` ro'yxati. Arxivdagi pozitsiya ham yuboriladi:
    MX dagi eski loyihalar unga ishora qiladi (o'chirish — alohida)."""
    rows = list(
        (
            await db.execute(
                select(CatalogItem)
                .where(
                    or_(CatalogItem.catalog == "M", CatalogItem.group_code == "KM"),
                    CatalogItem.catalog != "X",
                    CatalogItem.is_deleted == False,  # noqa: E712
                )
                .order_by(CatalogItem.catalog, CatalogItem.group_code, CatalogItem.model_no, CatalogItem.variant_no)
            )
        ).scalars()
    )
    papka: dict[str, dict[str, Any]] = {
        ILDIZ: {"id": ILDIZ, "parent_id": None, "kind": "folder", "code": "", "name": "MES katalogi"}
    }
    for c in rows:
        fid = f"{ILDIZ}:{c.catalog}-{c.group_code}"
        papka.setdefault(
            fid,
            {
                "id": fid,
                "parent_id": ILDIZ,
                "kind": "folder",
                "code": f"{c.catalog}-{c.group_code}",
                "name": c.group_name,
            },
        )
    return [*papka.values(), *(_item(c) for c in rows)]
