"""Arra «list chiqdi» → MX Kroy (EKO 3d): `MES_QOLDIQ_V1.md` «MES → MX: List arradan chiqdi».

Arrachi kesib chek chiqarganda (ARRA skani) shu list andozasidan nechta JISMONIY list to'liq kesilgani
hisoblanadi: andozaning har katagida `mult` nusxa bor, kesilgan list soni = kataklar bo'yicha eng kami.
Son o'sganda:
- MES dagi MX qoldiq bo'laklari ulushi `kutish` → `ombor` (MX javobini kutmasdan, shu tranzaksiyada);
- MX ga `PATCH /projects/{pid}/operations/{op}/maps/{n}` `{done_count}` — outbox orqali (MX o'chiq bo'lsa ham
  yo'qolmaydi). MX keyin o'zi `map.done` webhook yuboradi — inbox uni takror sifatida qabul qiladi.
Faqat MX paketi bilan yuklangan buyurtmada (xaritada `mx_op`/`mx_index` bor) ishlaydi.
"""

from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, PartInstance, Post, Scan
from app.models.enums import PostCode
from app.modules.integratsiya.models import KroyLoyiha
from app.modules.integratsiya.outbox import navbatga
from app.modules.ombor import service as ombor


def _sheet(order: Order, pattern_no: int) -> dict[str, Any] | None:
    for mat in (order.cutmap or {}).get("materials", []):
        for sh in mat.get("sheets", []):
            if sh.get("no") == pattern_no:
                return sh if sh.get("mx_op") and sh.get("mx_index") else None
    return None


async def kesilgan_listlar(db: AsyncSession, order_id: int, pattern_no: int) -> int:
    arra = select(Post.id).where(Post.code == PostCode.ARRA).scalar_subquery()
    rows = (
        await db.execute(
            select(PartInstance.cell_index, func.count(func.distinct(Scan.instance_id)))
            .outerjoin(
                Scan,
                and_(Scan.instance_id == PartInstance.id, Scan.post_id == arra, Scan.is_cancelled == False),  # noqa: E712
            )
            .where(
                PartInstance.order_id == order_id,
                PartInstance.pattern_no == pattern_no,
                PartInstance.is_deleted == False,  # noqa: E712
            )
            .group_by(PartInstance.cell_index)
        )
    ).all()
    return min((int(n) for _, n in rows), default=0)


async def arra_skan(db: AsyncSession, order_id: int, pattern_no: int | None) -> int:
    """ARRA skanidan keyin chaqiriladi (`scanning.finalize_scan`, commit'dan oldin). Qaytaradi: ochilgan bo'lak."""
    if pattern_no is None:
        return 0
    link = (await db.execute(select(KroyLoyiha).where(KroyLoyiha.order_id == order_id))).scalar_one_or_none()
    order = await db.get(Order, order_id)
    sh = _sheet(order, pattern_no) if link is not None and order is not None else None
    if sh is None or link is None:
        return 0
    done = min(await kesilgan_listlar(db, order_id, pattern_no), int(sh.get("mult") or 1))
    if done <= 0:
        return 0
    op, idx = str(sh["mx_op"]), int(sh["mx_index"])
    ochildi = await ombor.kroy_map_done(db, link.project_id, op, idx, done)
    await navbatga(
        db,
        f"map:{link.project_id}:{op}:{idx}:{done}",
        "PATCH",
        f"/projects/{link.project_id}/operations/{op}/maps/{idx}",
        {"done_count": done},
    )
    return ochildi
