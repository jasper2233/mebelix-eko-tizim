"""Mavjud buyurtmalarning SCX fayllarini qayta generatsiya qilish.

Parser tuzatilganda eski buyurtmalar fayllari ingest paytidagi (xato) holatda
qolib ketadi — prisadkachi eski koordinatali fayl bilan ishlashi mumkin.
Bu komanda saqlangan .project fayldan SCX'larni yangidan quradi: eski SCX
qatorlari soft-delete, diskdagi fayllar almashtiriladi; detallar, nusxalar va
skanlar TEGILMAYDI.

Run: python -m app.commands.regen_scx <order_id> [order_id ...]
     python -m app.commands.regen_scx --all
"""

import asyncio
import logging
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import local_session
from app.models import Order, OrderFile, Part, Product
from app.models.enums import FileKind, OrderStatus
from app.services.giblab.parser import parse_project
from app.services.giblab.scx import build_scx_files

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("regen_scx")

_SKIP_STATUSES = (OrderStatus.CANCELLED, OrderStatus.DELIVERED)


async def regen_order(db: AsyncSession, order: Order, upload_root: Path) -> str:
    proj_row = (
        (
            await db.execute(
                select(OrderFile)
                .where(
                    OrderFile.order_id == order.id,
                    OrderFile.kind == FileKind.PROJECT,
                    OrderFile.is_deleted == False,  # noqa: E712
                )
                .order_by(OrderFile.id.desc())
            )
        )
        .scalars()
        .first()
    )
    if proj_row is None:
        return "project fayli yo'q (DB)"
    proj_path = upload_root / proj_row.path
    if not proj_path.is_file():
        return f"project fayli diskda yo'q: {proj_row.path}"

    project = parse_project(proj_path.read_bytes())

    # DB detallari: (product_code, part_code) -> part_id
    pmap = {
        (prod_code, code): pid
        for pid, code, prod_code in (
            await db.execute(
                select(Part.id, Part.code, Product.code)
                .join(Product, Product.id == Part.product_id)
                .where(Part.order_id == order.id, Part.is_deleted == False)  # noqa: E712
            )
        ).all()
    }

    # Eski SCX qatorlari soft-delete; diskdagi fayllar to'liq almashadi
    old_rows = (
        (
            await db.execute(
                select(OrderFile).where(
                    OrderFile.order_id == order.id,
                    OrderFile.kind == FileKind.SCX,
                    OrderFile.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    for row in old_rows:
        row.is_deleted = True

    scx_dir = upload_root / "scx" / str(order.id)
    scx_dir.mkdir(parents=True, exist_ok=True)
    for f in scx_dir.glob("*.scx"):
        f.unlink()

    written = 0
    unmatched: list[str] = []
    plate_by_name = {m.name: m.thickness for m in project.materials if m.kind == "sheet" and m.thickness}
    for prod in project.products:
        for pp in prod.parts:
            if not pp.xnc_ops:
                continue
            part_id = pmap.get((prod.code, pp.code))
            if part_id is None:
                unmatched.append(f"{prod.code}_{pp.code}")
                continue
            qr_texts = [f"{pp.key}_{n}" for n in range(1, pp.count + 1)]
            for filename, content, meta in build_scx_files(
                pp, qr_texts, plate_thickness=plate_by_name.get(pp.material_name or "")
            ):
                (scx_dir / filename).write_text(content, encoding="utf-8")
                db.add(
                    OrderFile(
                        order_id=order.id,
                        part_id=part_id,
                        kind=FileKind.SCX,
                        path=str((scx_dir / filename).relative_to(upload_root)),
                        filename=filename,
                        size=len(content.encode()),
                        meta=meta,
                    )
                )
                written += 1

    msg = f"eski {len(old_rows)} -> yangi {written} fayl"
    if unmatched:
        msg += f"; DB'da topilmadi: {', '.join(unmatched[:5])}"
    return msg


async def main(argv: list[str]) -> None:
    upload_root = Path(settings.UPLOAD_DIR).resolve()
    async with local_session() as db:
        q = select(Order).where(Order.is_deleted == False)  # noqa: E712
        if argv == ["--all"]:
            q = q.where(Order.status.notin_(_SKIP_STATUSES), Order.project_loaded_at.isnot(None))
        else:
            q = q.where(Order.id.in_([int(a) for a in argv]))
        orders = (await db.execute(q.order_by(Order.id))).scalars().all()
        if not orders:
            logger.info("Buyurtma topilmadi.")
            return
        for order in orders:
            try:
                result = await regen_order(db, order, upload_root)
            except Exception as exc:  # noqa: BLE001 - bitta buyurtma xatosi qolganlarini to'xtatmasin
                await db.rollback()
                logger.info("%s (%s): XATO - %s", order.number, order.id, exc)
                continue
            await db.commit()
            logger.info("%s (%s): %s", order.number, order.id, result)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    asyncio.run(main(sys.argv[1:]))
