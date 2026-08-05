"""Persist a parsed .project into the order (TZ 6.3): products, parts, instances, routes,
materials auto-registry, SCX files and the cut map. Re-upload fully replaces previous results
(allowed until PRODUCTION)."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Material, Order, OrderFile, Part, PartInstance, PartRoute, Post, Product
from app.models.enums import FileKind, MaterialType, PostCode, RouteSource

from .cutmap import build_cutmap
from .models import PROCESS_POSTS, ParsedPart, ParsedProject, ParseError
from .scx import build_scx_files

logger = logging.getLogger(__name__)


async def wipe_previous_parse(db: AsyncSession, order: Order, upload_root: Path) -> None:
    """Re-upload replaces everything derived from the old file (TZ 6.3.1)."""
    now = datetime.now(UTC)
    for model in (Product, Part, PartInstance, PartRoute):
        await db.execute(
            update(model)
            .where(model.order_id == order.id, model.is_deleted == False)  # noqa: E712
            .values(is_deleted=True, deleted_at=now)
        )
    # Fayllarda yo'l ham kerak (diskdan o'chirish uchun) — avval yo'llar, keyin bulk UPDATE
    file_where = (
        OrderFile.order_id == order.id,
        OrderFile.kind.in_([FileKind.PROJECT, FileKind.SCX]),
        OrderFile.is_deleted == False,  # noqa: E712
    )
    paths = (await db.execute(select(OrderFile.path).where(*file_where))).scalars().all()
    await db.execute(update(OrderFile).where(*file_where).values(is_deleted=True, deleted_at=now))
    for path in paths:
        try:
            (upload_root / path).unlink(missing_ok=True)
        except OSError:
            logger.warning("Eski faylni o'chirib bo'lmadi: %s", path)


# Sarf birligi: list va kromkada faylda `unit` yo'q, furnitura esa doim 'шт' beradi.
_USAGE_UNITS = {"sheet": "list", "band": "metr", "hardware": "dona"}


async def _upsert_materials(db: AsyncSession, project: ParsedProject) -> None:
    """New materials appear automatically when a project references them (TZ 4.5)."""
    for mat in project.materials:
        mtype = MaterialType(mat.kind)
        exists = (
            await db.execute(
                select(Material).where(
                    Material.name == mat.name,
                    Material.type == mtype,
                    Material.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            db.add(
                Material(
                    name=mat.name,
                    code=mat.code,
                    type=mtype,
                    thickness=mat.thickness,
                    width=mat.width,
                    length=mat.length,
                )
            )
            await db.flush()


def write_and_register_scx(
    db: AsyncSession,
    order_id: int,
    part_id: int,
    pp: ParsedPart,
    qr_texts: list[str],
    upload_root: Path,
    plate_thickness: float | None = None,
) -> int:
    """SCX fayllarni diskka yozib, har biriga OrderFile qatori qo'shadi (TZ 5.6.5 / 12.5).

    Ham birinchi ingest, ham "SCX qayta yaratish" (orders.regenerate_order_scx) shu yo'ldan
    o'tadi — fayl nomi/joyi va OrderFile maydonlari bir joyda. Nechta fayl yaratilgani qaytadi.
    """
    scx_dir = upload_root / "scx" / str(order_id)
    scx_dir.mkdir(parents=True, exist_ok=True)
    created = 0
    for filename, content, meta in build_scx_files(pp, qr_texts, plate_thickness=plate_thickness):
        (scx_dir / filename).write_text(content, encoding="utf-8")
        db.add(
            OrderFile(
                order_id=order_id,
                part_id=part_id,
                kind=FileKind.SCX,
                path=str((scx_dir / filename).relative_to(upload_root)),
                filename=filename,
                size=len(content.encode()),
                meta=meta,
            )
        )
        created += 1
    return created


async def ingest_project(
    db: AsyncSession,
    order: Order,
    project: ParsedProject,
    raw_content: bytes,
    original_filename: str,
    upload_root: Path,
) -> dict[str, Any]:
    """Create all DB rows + files for a parsed PROCESSED project. Caller commits."""
    # Yuklangan fayl nomi yo'l qismisiz saqlanadi — "../" bilan uploads tashqarisiga
    # yozishning oldi olinadi
    original_filename = Path(original_filename).name or "project.project"

    # QR to'qnashuvini OLDINDAN aniqlash: masalan "010" (2 nusxa) va "010_2" kodli
    # detal bir xil QR beradi — unique indeks 500 bermasin, do'stona xato bersin
    qr_owner: dict[str, str] = {}
    for pp in project.all_parts:
        for qr in pp.qr_texts:
            if qr in qr_owner:
                raise ParseError(
                    f"Detal ID to'qnashuvi: {qr} ham {qr_owner[qr]}, ham {pp.key} uchun chiqdi. "
                    "GibLab'da detal kodlarini tekshiring."
                )
            qr_owner[qr] = pp.key

    # Kalit — matn: marshrut kodlari ham matn (PROCESS_POSTS), va noma'lum post
    # `get()` da None beradi (enumga aylantirilsa ValueError -> 500 bo'lardi)
    posts = {str(p.code): p for p in (await db.execute(select(Post))).scalars()}

    cutmap = build_cutmap(project) if any(c.data_blob for c in project.cut_ops) else None

    await _upsert_materials(db, project)

    # --- store the raw project file ---
    project_dir = upload_root / "projects" / str(order.id)
    project_dir.mkdir(parents=True, exist_ok=True)
    project_path = project_dir / original_filename
    project_path.write_bytes(raw_content)
    db.add(
        OrderFile(
            order_id=order.id,
            kind=FileKind.PROJECT,
            path=str(project_path.relative_to(upload_root)),
            filename=original_filename,
            size=len(raw_content),
        )
    )

    # Plita qalinligi material nomi bo'yicha — qo'shqavat detal SCX'i uchun (scx.py)
    _plate_thickness: dict[str, float] = {
        m.name: m.thickness for m in project.materials if m.kind == "sheet" and m.thickness
    }

    # --- products, parts, instances, routes, scx ---
    bindings_by_key: dict[str, list[Any]] = {}
    if cutmap:
        for b in cutmap.bindings:
            bindings_by_key.setdefault(b.part_key, []).append(b)

    parts_created = 0
    instances_created = 0
    for parsed_product in project.products:
        product = Product(
            order_id=order.id,
            code=parsed_product.code,
            name=parsed_product.name,
            count=parsed_product.count,
        )
        db.add(product)
        await db.flush()

        for pp in parsed_product.parts:
            merged = pp.merged_machining()
            part = Part(
                order_id=order.id,
                product_id=product.id,
                code=pp.code,
                name=pp.name,
                count=pp.count,
                length=pp.length,
                width=pp.width,
                thickness=pp.thickness,
                txt=pp.txt,
                material_name=pp.material_name,
                label_num=pp.label_num,
                edges=pp.edges,
                xnc_summary={
                    "sides": len(pp.xnc_ops),
                    "bores": len(merged.bores) if merged else 0,
                    "edge_bores": len(merged.edge_bores) if merged else 0,
                    "grooves": len(merged.grooves) if merged else 0,
                    "mills": len(merged.mills) if merged else 0,
                },
            )
            db.add(part)
            await db.flush()
            parts_created += 1

            # instances with cut-map cell binding (TZ 5.8.1 / 7.1.4)
            cell_bindings = bindings_by_key.get(pp.key, [])
            for n in range(1, pp.count + 1):
                binding = cell_bindings[n - 1] if n - 1 < len(cell_bindings) else None
                db.add(
                    PartInstance(
                        order_id=order.id,
                        part_id=part.id,
                        instance_no=n,
                        qr_text=pp.qr_texts[n - 1],
                        pattern_no=binding.pattern_no if binding else None,
                        cell_index=binding.cell_index if binding else None,
                    )
                )
                instances_created += 1

            # Marshrut (TZ 5.4) ikki manbadan: NOODATIY detalda — nomdagi ro'yxatdan,
            # qolganlarida — fayl mazmunidan.
            # Kalit post KODI (matn): noma'lum post `posts.get()` da None beradi va
            # tushunarli xato chiqadi; `PostCode(...)` bo'lsa ValueError -> 500 bo'lardi.
            stage_per_instance: dict[str, int] = {}
            if pp.process_codes:
                # Texnolog nomga yozgan ro'yxat ("eshik {7;11;8}") fayldagi bosqichlarni
                # BUTUNLAY almashtiradi — arra ham avtomatik qo'shilmaydi, chunki jarayon
                # roverdan yoki boshqa postdan boshlanishi mumkin.
                for code in pp.process_codes:
                    post_code = PROCESS_POSTS[code]
                    # Kromka skanlari QIRRA bo'yicha sanaladi (terminalda "tomonlar",
                    # ish haqi metrda) — boshqa postlarda bitta o'tish = bitta skan.
                    per = (pp.kromka_sides or 1) if post_code == PostCode.KROMKA else 1
                    stage_per_instance[post_code] = stage_per_instance.get(post_code, 0) + per
            else:
                # ARRA — faqat listdan kesiladigan detalga. Optimizatsiya qilingan faylda
                # materiali ham, yorliq raqami ham yo'q detal umuman listga joylashtirilmagan
                # (masalan kupe alyuminiy profillari) — unga ARRA vazifasi berilsa arrachi
                # kesa olmaydigan soxta ish paydo bo'lardi.
                sheet_part = project.generation != "processed" or pp.material_name or pp.label_num is not None
                if sheet_part:
                    stage_per_instance[PostCode.ARRA] = 1
                if pp.kromka_sides:
                    stage_per_instance[PostCode.KROMKA] = pp.kromka_sides
                stage_per_instance.update(pp.stage_sides())
            for post_code, per_instance in stage_per_instance.items():
                post = posts.get(post_code)
                if post is None:
                    raise ParseError(f"Post sozlanmagan: {post_code}. Administratorga murojaat qiling.")
                db.add(
                    PartRoute(
                        order_id=order.id,
                        part_id=part.id,
                        post_id=post.id,
                        source=RouteSource.AUTO,
                        per_instance=per_instance,
                        total_required=pp.count * per_instance,
                    )
                )

            # SCX (TZ 5.6.5 / 12.5): har nusxaga bitta TO'LIQ fayl (old + orqa Face=6
            # birlashgan, nom/ID = QR — Nanxing skaneri to'g'ridan-to'g'ri topadi).
            # plate: qo'shqavat detalda (32mm) eksport qalinligi plita bo'yicha
            plate = _plate_thickness.get(pp.material_name or "")
            write_and_register_scx(db, order.id, part.id, pp, pp.qr_texts, upload_root, plate_thickness=plate)

    # --- order metadata ---
    # `code` — sexning `goods.xls` katalogidagi SKU. Parser uni o'qiydi, lekin bu yerda
    # tushib qolardi: sklad va material hisoboti faqat nomni ko'rardi. Sex katalogga
    # o'tgandan keyin (yangi eksportlarda `code="110083"`, `code="КРМ1009"`) nom emas, kod
    # barqaror kalit. Eski fayllarda `code` yo'q — o'shanda `None` bo'lib qoladi.
    order.material_usage = [
        {"name": m.name, "code": m.code, "kind": m.kind, "count": m.count, "unit": _USAGE_UNITS[m.kind]}
        for m in project.materials
        if m.count
    ]
    order.project_uuid = project.uuid
    order.project_name = project.name
    order.project_loaded_at = datetime.now(UTC)
    order.cutmap = cutmap.model if cutmap else None

    # Kesish xaritasi qurilgan bo'lsa: unda joyi yo'q detallarni texnolog bilishi shart.
    # Ikki sabab bo'ladi — (a) listdan kesilmaydigan profil, (b) GibLab uni ataylab
    # joylashtirmagan (usedCount=0), ya'ni material yetmagan yoki dizayner chiqarib tashlagan.
    if cutmap:
        placed = {b.part_key for b in cutmap.bindings}
        ghosts = [p for p in project.all_parts if p.key not in placed]
        if ghosts:
            names = ", ".join(f"{p.code} ({p.name})" for p in ghosts[:5])
            more = f" va yana {len(ghosts) - 5} ta" if len(ghosts) > 5 else ""
            project.warnings.append(
                f"Kesish xaritasida {len(ghosts)} ta detalning joyi yo'q: {names}{more}. "
                f"Ular arrachi ro'yxatiga tushmaydi."
            )

    return {
        "products": len(project.products),
        "parts": parts_created,
        "instances": instances_created,
        "materials": len(project.materials),
        "warnings": project.warnings,
    }
