"""Persist a parsed .project into the order (TZ 6.3): products, parts, instances, routes,
materials auto-registry, SCX files and the cut map. Re-upload fully replaces previous results
(gate — `_require_editable`: PRODUCTION included, until the first live scan)."""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, OrderFile, Part, PartInstance, PartRoute, Post, Product, WasteItem
from app.models.enums import FileKind, PostCode, RouteSource

from .cutmap import build_cutmap
from .models import PROCESS_POSTS, TAIL_CODES, ParsedPart, ParsedProject, ParseError
from .scx import build_scx_files, plate_thickness_map

logger = logging.getLogger(__name__)


#: `(mahsulot kodi, detal kodi)` -> (nostandart bayrog'i, jarayon kodlari, asosiy detal kaliti)
RouteSnapshot = dict[tuple[str, str], tuple[bool, list[int], tuple[str, str] | None]]


_K = TypeVar("_K", str, PostCode)  # posts lug'ati ingest'da str, restore'da PostCode kalitli


def _post(posts: dict[_K, Post], post_code: _K) -> Post:
    post = posts.get(post_code)
    if post is None:
        raise ParseError(f"Post sozlanmagan: {post_code}. Administratorga murojaat qiling.")
    return post


async def snapshot_custom_routes(db: AsyncSession, order: Order) -> RouteSnapshot:
    """Qo'lda kiritilgan marshrutlarni `(mahsulot kodi, detal kodi)` bo'yicha eslab qolish.

    Qayta yuklash eski parse'ni butunlay o'chiradi — texnolog yuzlab detalga chizgan
    marshrut ham yo'qolardi. Kalit sifatida detal KODI olinadi: u fayl ichidagi ID'dan
    farqli o'laroq qayta eksportda ham o'zgarmaydi (TZ 5.8).

    Nostandart detallar ham, matritsadan qo'lda qadam qo'shilgan STANDART detallar ham
    olinadi — ikkalasi ham fayldan tiklanmaydi. Bayroqning o'zi ham saqlanadi."""
    # Yig'ma bog'lam ham eslab qolinadi: id qayta yuklashda o'zgaradi, shuning
    # uchun asosiy detal ham KOD bilan yoziladi.
    keys = {
        part_id: (product_code, part_code)
        for part_id, product_code, part_code in (
            await db.execute(
                select(Part.id, Product.code, Part.code)
                .join(Product, Product.id == Part.product_id)
                .where(
                    Part.order_id == order.id,
                    Part.is_deleted == False,  # noqa: E712
                )
            )
        ).tuples()
    }
    parents: dict[int, tuple[str, str] | None] = {
        part_id: keys.get(parent_id) if parent_id is not None else None
        for part_id, parent_id in (
            await db.execute(
                select(Part.id, Part.assembly_parent_id).where(
                    Part.order_id == order.id,
                    Part.assembly_parent_id.is_not(None),
                    Part.is_deleted == False,  # noqa: E712
                )
            )
        ).tuples()
    }

    rows = (
        await db.execute(
            select(Part.id, Product.code, Part.code, Part.is_custom, PartRoute.process_code)
            .join(Part, Part.product_id == Product.id)
            .join(PartRoute, PartRoute.part_id == Part.id)
            .where(
                Part.order_id == order.id,
                Part.is_deleted == False,  # noqa: E712
                PartRoute.source == RouteSource.MANUAL,
                PartRoute.is_deleted == False,  # noqa: E712
            )
            .order_by(Product.code, Part.code, PartRoute.seq)
        )
    ).tuples()
    saved: RouteSnapshot = {}
    for part_id, product_code, part_code, is_custom, process_code in rows:
        entry = saved.setdefault((product_code, part_code), (is_custom, [], parents.get(part_id)))
        # Dum (qadoqlash/TMO) saqlanmaydi — tiklashda o'zi qo'shiladi. Saqlansa
        # har qayta yuklashda ikkilanib borardi: ... UPAKOVKA TMO UPAKOVKA TMO.
        if process_code not in TAIL_CODES:
            entry[1].append(process_code)
    return saved


async def restore_custom_routes(db: AsyncSession, order: Order, saved: RouteSnapshot) -> tuple[int, list[str]]:
    """Saqlangan marshrutlarni yangi detallarga qaytarish. Qaytadi: (tiklangan, yo'qolgan)."""
    if not saved:
        return 0, []
    posts = {p.code: p for p in (await db.execute(select(Post))).scalars()}
    # Anketadagi "Upakovka qilish" xizmati (manager kelishadi) — marshrutga
    # qadoqlash qadamini qo'shadimi. `survey` JSONB, eski yozuvda kalit umuman yo'q.
    packaging = order.needs_packaging
    posts_by_id = {p.id: p.code for p in posts.values()}
    parts = (
        await db.execute(
            select(Product.code, Part)
            .join(Part, Part.product_id == Product.id)
            .where(Part.order_id == order.id, Part.is_deleted == False)  # noqa: E712
        )
    ).tuples()
    by_key = {(product_code, part.code): part for product_code, part in parts}
    # Buyurtmaning HAMMA tirik marshruti bitta so'rovda: sikl ichida har detal uchun
    # alohida SELECT qilinmasin (detallar soni yuzlab bo'lishi mumkin).
    live_by_part: dict[int, list[PartRoute]] = {}
    for route in (
        await db.execute(
            select(PartRoute).where(
                PartRoute.order_id == order.id,
                PartRoute.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars():
        live_by_part.setdefault(route.part_id, []).append(route)

    # Nostandart detalda marshrut TO'LIQ qo'lda — fayldan qurilgani o'chadi. Sikldan
    # OLDIN va bitta UPDATE bilan: sikl ichida bo'lsa, avval qo'shilgan MANUAL
    # qatorlar autoflush bo'lib qolar edi.
    custom_ids = [by_key[key].id for key, entry in saved.items() if entry[0] and key in by_key]
    if custom_ids:
        await db.execute(
            update(PartRoute)
            .where(PartRoute.part_id.in_(custom_ids), PartRoute.is_deleted == False)  # noqa: E712
            .values(is_deleted=True, deleted_at=datetime.now(UTC))
        )

    # Yig'ma bog'lamlar marshrutdan OLDIN tiklanadi: dum (qadoqlash/TMO)
    # biriktirilgan detalga qo'shilmasligi shu bayroqqa qarab hal bo'ladi.
    for key, entry in saved.items():
        part, parent_key = by_key.get(key), entry[2]
        if part is None:
            continue
        parent = by_key.get(parent_key) if parent_key else None
        part.assembly_parent_id = parent.id if parent is not None else None

    restored = 0
    for key, entry in saved.items():
        was_custom, codes = entry[0], entry[1]
        part = by_key.get(key)
        if part is None:
            continue
        part.is_custom = was_custom
        if was_custom:
            # AUTO qatorlari yuqorida bitta UPDATE bilan allaqachon o'chirilgan.
            start_seq, seen = 1, set()
        else:
            # Standart detalda qo'lda qo'shilgan qadam fayl qadamlariga QO'SHIMCHA edi
            # (matritsadagi tugma) — fayl qadamlari joyida qoladi, bular ketidan tushadi.
            live = live_by_part.get(part.id, [])
            start_seq = max((r.seq for r in live), default=0) + 1
            seen = {posts_by_id[r.post_id] for r in live if r.post_id in posts_by_id}
        edge_count = len(part.edges) or 1
        for offset, code in enumerate(codes):
            post_code = PROCESS_POSTS[code]
            post = _post(posts, post_code)
            # OVAL bu yerda YO'Q: oval kromkada detal bitta o'tishda ishlanadi — bitta skan.
            # KROMKA esa har qirrani alohida yopishtiradi, shuning uchun birinchi o'tishda
            # qirralar soni marta skanlanadi (takror kelsa — bitta).
            first_edge_pass = post_code == PostCode.KROMKA and post_code not in seen
            seen.add(post_code)
            per = edge_count if first_edge_pass else 1
            db.add(
                PartRoute(
                    order_id=order.id,
                    part_id=part.id,
                    post_id=post.id,
                    seq=start_seq + offset,
                    process_code=code,
                    source=RouteSource.MANUAL,
                    per_instance=per,
                    total_required=part.count * per,
                )
            )
        # Nostandart detalning marshruti to'liq qayta yozilgani uchun qadoqlash va
        # TMO qadamlari shu yerda tiklanadi (standart detalda ular AUTO bo'lib qoladi).
        # Biriktirilgan MAYDA detalga dum qo'shilmaydi — u asosiy detalga
        # yopishib yaxlit buyumga aylanadi (orders._set_custom_route bilan bir xil qoida).
        if was_custom and part.assembly_parent_id is None:
            tail = [(15, PostCode.UPAKOVKA)] if packaging else []
            tail.append((16, PostCode.TMO))
            for offset, (code, post_code) in enumerate(tail):
                post = _post(posts, post_code)
                db.add(
                    PartRoute(
                        order_id=order.id,
                        part_id=part.id,
                        post_id=post.id,
                        seq=start_seq + len(codes) + offset,
                        process_code=code,
                        source=RouteSource.MANUAL,
                        per_instance=1,
                        total_required=part.count,
                    )
                )
        restored += 1
    lost = [f"{p}_{c}" for (p, c) in saved if (p, c) not in by_key]
    return restored, lost


async def wipe_previous_parse(db: AsyncSession, order: Order, upload_root: Path) -> None:
    """Re-upload replaces everything derived from the old file (TZ 6.3.1)."""
    now = datetime.now(UTC)
    for model in (Product, Part, PartInstance, PartRoute, WasteItem):
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
    for filename, content in build_scx_files(pp, qr_texts, plate_thickness=plate_thickness):
        (scx_dir / filename).write_text(content, encoding="utf-8")
        db.add(
            OrderFile(
                order_id=order_id,
                part_id=part_id,
                kind=FileKind.SCX,
                path=str((scx_dir / filename).relative_to(upload_root)),
                filename=filename,
                size=len(content.encode()),
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
    # Anketadagi "Upakovka qilish" xizmati — marshrutga qadoqlash qadamini
    # qo'shadimi. `survey` JSONB, eski yozuvda kalit umuman bo'lmasligi mumkin.
    packaging = order.needs_packaging

    cutmap = build_cutmap(project) if any(c.data_blob for c in project.cut_ops) else None

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
    _plate_thickness = plate_thickness_map(project)

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

            # STANDART marshrut (TZ 5.4) — faqat fayl mazmunidan. Qadamlar TARTIBLI:
            # (process_code, post_code, per_instance); tartib skan navbatini belgilaydi.
            # Rover/stolyarka/bo'yoq bu yerdan CHIQMAYDI: roverdan chiqqan detal keyin
            # bo'yalishi mumkinligini fayl bilmaydi — texnolog uni "nostandart" deb
            # belgilab, marshrutini o'zi chizadi.
            # Post sozlanmagan bo'lsa `_post()` tushunarli ParseError beradi.
            steps: list[tuple[int, PostCode, int]] = []
            # ARRA — faqat listdan kesiladigan detalga. Optimizatsiya qilingan faylda
            # materiali ham, yorliq raqami ham yo'q detal umuman listga joylashtirilmagan
            # (masalan kupe alyuminiy profillari) — unga ARRA vazifasi berilsa arrachi
            # kesa olmaydigan soxta ish paydo bo'lardi.
            if pp.material_name or pp.label_num is not None:
                steps.append((1, PostCode.ARRA, 1))  # 1 = Raspil
            if pp.kromka_sides:
                steps.append((3, PostCode.KROMKA, pp.kromka_sides))  # 3 = Kromka
            if prisadka := pp.prisadka_passes():
                steps.append((6, PostCode.PRISADKA, prisadka))  # 6 = Prisadka
            # Qadoqlash — anketada belgilangan bo'lsa HAMMA detalga oxirgi qadam.
            # Qisman qadoqlash yo'q: buyurtma yo butunlay qadoqlanadi, yo yo'q.
            if packaging:
                steps.append((15, PostCode.UPAKOVKA, 1))
            # TMO — eng oxirgi qadam, qadoqlangan-qadoqlanmaganidan qat'i nazar.
            # Omborchi qabul qilmaguncha detal tugallanmagan bo'lib turadi.
            steps.append((16, PostCode.TMO, 1))
            for seq, (process_code, post_code, per_instance) in enumerate(steps, start=1):
                post = _post(posts, post_code)
                db.add(
                    PartRoute(
                        order_id=order.id,
                        part_id=part.id,
                        post_id=post.id,
                        seq=seq,
                        process_code=process_code,
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
    # `code` — tsexning `goods.xls` katalogidagi SKU. Parser uni o'qiydi, lekin bu yerda
    # tushib qolardi: materiallar ombori va material hisoboti faqat nomni ko'rardi. Tsex katalogga
    # o'tgandan keyin (yangi eksportlarda `code="110083"`, `code="КРМ1009"`) nom emas, kod
    # barqaror kalit. Eski fayllarda `code` yo'q — o'shanda `None` bo'lib qoladi.
    order.material_usage = [
        {"name": m.name, "code": m.code, "kind": m.kind, "count": m.count, "unit": _USAGE_UNITS[m.kind]}
        for m in project.materials
        if m.count
    ]
    order.project_uuid = project.uuid
    # Nom YUKLANGAN FAYL nomidan olinadi (kengaytmasiz): "2064 alisher.project" -> "2064 alisher".
    # Ilgari `project.name` — ya'ni fayl ICHIDAGI `<root name=...>` atributi ishlatilardi, lekin
    # GibLab eksportlarining bir qismida u umuman bo'lmaydi: prodda 39 buyurtmadan faqat 19 tasida
    # nom bor edi, qolganlarida `.project` fayli yuklangan bo'lsa ham nom BO'SH qolardi va reestrda
    # ham, TABLOda ham ko'rinmasdi. Fayl nomi esa doim bor.
    order.project_name = Path(original_filename).stem or project.name
    order.project_loaded_at = datetime.now(UTC)
    order.cutmap = cutmap.model if cutmap else None

    # FOYDALI atxotlar (GibLab `business="true"`) — chek va treking uchun yozuv.
    # QR prefiksi "ATX-": skan dvijoki detal QR'i bilan adashtirmasin. Raqamlash
    # material/list tartibida — chekdagi raqam xaritadagi bilan mos keladi.
    if cutmap:
        atx_n = 0
        for mat in cutmap.model.get("materials", []):
            for sh in mat.get("sheets", []):
                for cell in sh.get("parts", []):
                    if not (cell.get("waste") and cell.get("business")):
                        continue
                    atx_n += 1
                    # Katakka raqam yoziladi (order.cutmap JSONB ga tushadi) —
                    # frontend shu raqam orqali WasteItem'ni topadi.
                    cell["atx"] = atx_n
                    db.add(
                        WasteItem(
                            order_id=order.id,
                            material_name=str(mat.get("name") or "")[:150],
                            sheet_no=int(sh.get("no") or 0),
                            length=float(cell.get("w") or 0),
                            width=float(cell.get("h") or 0),
                            qr_text=f"ATX-{order.number}-{atx_n}",
                        )
                    )

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
