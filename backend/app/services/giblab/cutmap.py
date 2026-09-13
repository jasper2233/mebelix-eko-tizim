"""Cut-map visual model builder — the JSON the ARRA terminal renders.

Validated rules from the working prototype (GibCut Viewer):
- rot: placed size swapped vs the part definition → 90° rotated, ⟳ shown on the map;
- edge symbols: on a rotated part l/r ↔ t/b swap;
- registered waste geometry is replaced by the useful size from its <part> definition
  (~10 mm is lost when registering from the raw cut);
- qty > 1 records expand into separate physical cells;
- every guillotine cut crosses its parent piece edge-to-edge;
- self-check: placed part cells (Σ qty × mult) == cPartCount, Σ mult == cMaterialCount.
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import ColumnElement, Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, Part, PartInstance, PartRoute, Post, Product, Scan, WasteItem
from app.models.enums import PostCode
from app.schemas.terminal import (
    CutmapInstanceState,
    CutmapMachining,
    CutmapModel,
    CutmapState,
    CutmapWasteItem,
)

from .csblob import BlobPattern, BlobRecord, decode_cs_blob, self_check
from .models import ParsedPart, ParsedProject, ParseError, stored_machined_sides


@dataclass
class InstanceCell:
    """Binding of one physical copy to a cut-map cell — persisted on PartInstance."""

    part_key: str  # productCode_partCode
    pattern_no: int  # 1-based, global across materials
    cell_index: int  # 1-based within the pattern


@dataclass
class CutmapResult:
    model: dict[str, Any]
    bindings: list[InstanceCell] = field(default_factory=list)


def _edge_markers(part: ParsedPart, rot: bool) -> tuple[list[str | None], list[str | None]]:
    """eW = [left, right] and eH = [top, bottom] symbols as placed (rotation swaps l/r ↔ t/b)."""

    def sym(side: str) -> str | None:
        e = part.edges.get(side)
        if e is None:
            return None
        return str(e.get("symbol") or "•")

    if not rot:
        return [sym("l"), sym("r")], [sym("t"), sym("b")]
    # HAQIQIY 90° burilish (x,y)->(y, h-x), GibSaw bilan bir xil: lokal l qirra
    # (x=0) katakning PASTIGA, r (x=l) TEPASIGA tushadi. Ilgari [l, r] edi —
    # transpose (oyna) izi, ya'ni burilgan detalda tepa/past kromka almashib
    # ko'rsatilardi.
    return [sym("t"), sym("b")], [sym("r"), sym("l")]


def _place(
    node: BlobRecord,
    x: float,
    y: float,
    w: float,
    h: float,
    vertical: bool,
    cells: list[dict[str, Any]],
    cuts: list[dict[str, Any]],
    dims: list[dict[str, Any]] | None = None,
) -> float:
    """Place one preorder node whose slice starts at (x, y) inside a w×h region.

        vertical=True → the slice runs along X (slice size = value × h);
        otherwise along Y (w × value). qty expands into consecutive physical copies
    . Children of an inner strip cut across the other axis.
        Returns the consumed extent along the current axis.
    """
    consumed = 0.0
    for _rep in range(max(node.qty, 1)):
        rx = x + consumed if vertical else x
        ry = y if vertical else y + consumed
        rw = node.value if vertical else w
        rh = h if vertical else node.value

        # Root strip dimension chain (GibSaw: chain drawn on the root-cut side only).
        if dims is not None and node.value >= 10:
            if vertical:
                dims.append({"ax": "X", "a": round(rx), "b": round(rx + node.value), "v": round(node.value)})
            else:
                dims.append({"ax": "Y", "a": round(ry), "b": round(ry + node.value), "v": round(node.value)})

        if node.type in (3, 4):  # part or registered waste — a physical cell
            cells.append({"part_id": node.part_id, "waste": node.type == 4, "x": rx, "y": ry, "w": rw, "h": rh})
        elif node.type == 2:
            cursor = 0.0
            for child in node.children:
                if vertical:  # children cut horizontally inside this vertical strip
                    cursor += _place(child, rx, ry + cursor, rw, rh, False, cells, cuts)
                else:
                    cursor += _place(child, rx + cursor, ry, rw, rh, True, cells, cuts)
        # type 1 (trim/kerf) consumes space only — kerf is not drawn separately

        consumed += node.value
        # Guillotine cut at this boundary — edge-to-edge across the parent region.
        if vertical:
            cuts.append({"x1": x + consumed, "y1": y, "x2": x + consumed, "y2": y + h})
        else:
            cuts.append({"x1": x, "y1": y + consumed, "x2": x + w, "y2": y + consumed})
    return consumed


def _place_pattern(
    pattern: BlobPattern,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    cells: list[dict[str, Any]] = []
    cuts: list[dict[str, Any]] = []
    dims: list[dict[str, Any]] = []
    cursor = pattern.leading_trim or 0.0
    if pattern.leading_trim:
        # Yetakchi torsovka FAQAT vertikal root o'qda bo'ladi (csblob: slot depth=1, type=1)
        cuts.append({"x1": cursor, "y1": 0.0, "x2": cursor, "y2": pattern.width})
    for node in pattern.records:
        if pattern.root_axis_vertical:
            cursor += _place(node, cursor, 0.0, pattern.length, pattern.width, True, cells, cuts, dims)
        else:
            cursor += _place(node, 0.0, cursor, pattern.length, pattern.width, False, cells, cuts, dims)

    # Deduplicate identical lines and drop ones lying on the sheet border.
    unique: dict[tuple[float, float, float, float], dict[str, Any]] = {}
    for c in cuts:
        key = (round(c["x1"], 1), round(c["y1"], 1), round(c["x2"], 1), round(c["y2"], 1))
        on_border = (c["x1"] == c["x2"] and (c["x1"] <= 0.01 or c["x1"] >= pattern.length - 0.01)) or (
            c["y1"] == c["y2"] and (c["y1"] <= 0.01 or c["y1"] >= pattern.width - 0.01)
        )
        if not on_border:
            unique[key] = c
    return cells, list(unique.values()), dims


def build_cutmap(project: ParsedProject) -> CutmapResult:
    """Build the full visual model + instance/cell bindings from all CS operations."""
    parts_by_file_id: dict[int, ParsedPart] = {p.file_part_id: p for p in project.all_parts}
    result = CutmapResult(model={"materials": [], "holes": {}})
    pattern_no = 0
    instance_counters: dict[str, int] = {}
    problems: list[str] = []

    for cut in project.cut_ops:
        if not cut.data_blob:
            continue
        patterns = decode_cs_blob(cut.data_blob)
        problems.extend(f"{cut.material_name}: {p}" for p in self_check(patterns, cut.stats))

        # Reja ko'rsatkichlari (kerf/tirim/to'ldirish/atxot/rez) JSON'ga yozilmaydi —
        # UI ularni ko'rsatmaydi (2026-09-03); `self_check` ularni fayldan to'g'ridan-to'g'ri oladi.
        material: dict[str, Any] = {"name": cut.material_name, "sheets": []}

        material_placed = 0  # part cells × mult, compared to cPartCount below
        for pat in patterns:
            pattern_no += 1
            cells, cuts, dims = _place_pattern(pat)
            sheet: dict[str, Any] = {
                "no": pattern_no,
                "L": pat.length,
                "W": pat.width,
                "mult": pat.mult,
                "parts": [],
                "dims": dims,  # root strip chain (GibSaw style)
                "cuts": cuts,
            }
            cell_index = 0
            for cell in cells:
                cell_index += 1
                entry: dict[str, Any] = {
                    "cell": cell_index,
                    "x": round(cell["x"], 2),
                    "y": round(cell["y"], 2),
                    "w": round(cell["w"], 2),
                    "h": round(cell["h"], 2),
                }
                if cell["waste"]:
                    wdef = cut.waste_parts.get(cell["part_id"])
                    # GibLab "business" atxoti — saqlanadigan foydali qoldiq;
                    # chek chiqarish va ombor trekingi faqat shularga.
                    entry["business"] = bool(wdef and wdef.get("business"))
                    if wdef:  # useful size from the definition, not the raw cut
                        entry["w"], entry["h"] = wdef["l"], wdef["w"]
                    entry.update({"id": cell["part_id"], "waste": True, "name": "atxot"})
                else:
                    part = parts_by_file_id.get(cell["part_id"])
                    if part is None:
                        problems.append(
                            f"{cut.material_name}: blob noma'lum detalga ishora qiladi (id={cell['part_id']})"
                        )
                        continue
                    material_placed += pat.mult
                    # Avval to'g'ridan-to'g'ri moslik: deyarli kvadrat detalda
                    # (masalan 400x399) ikkala test ham o'tadi, shuning uchun
                    # aylantirilmagan joylashuv ustun turadi.
                    fits_direct = (
                        part.length is not None
                        and part.width is not None
                        and abs(cell["w"] - part.length) < 1.5
                        and abs(cell["h"] - part.width) < 1.5
                    )
                    rot = (
                        not fits_direct
                        and part.length is not None
                        and part.width is not None
                        and part.length != part.width
                        and abs(cell["w"] - part.width) < 1.5
                        and abs(cell["h"] - part.length) < 1.5
                    )
                    e_w, e_h = _edge_markers(part, rot)
                    entry.update(
                        {
                            "id": part.file_part_id,
                            "key": part.key,
                            "num": part.label_num,
                            "name": part.name,
                            "rot": rot,
                            "waste": False,
                            "eW": e_w,
                            "eH": e_h,
                            "txt": part.txt,
                        }
                    )
                    for _rep in range(pat.mult):  # one physical copy per sheet repetition
                        instance_counters[part.key] = instance_counters.get(part.key, 0) + 1
                        result.bindings.append(
                            InstanceCell(part_key=part.key, pattern_no=pattern_no, cell_index=cell_index)
                        )
                sheet["parts"].append(entry)
            material["sheets"].append(sheet)

        expected = int(cut.stats.get("cPartCount") or 0)
        if expected and material_placed != expected:
            problems.append(f"{cut.material_name}: joylashtirilgan detallar {material_placed} ≠ cPartCount {expected}")
        result.model["materials"].append(material)

    # Holes overlay: merged XNC per part, duplicates removed.
    for part in project.all_parts:
        merged = part.merged_machining()
        if merged and (merged.bores or merged.edge_bores):
            result.model["holes"][str(part.file_part_id)] = {
                "l": part.length,
                "w": part.width,
                "bores": [{"x": b["x"], "y": b["y"], "d": b["d"]} for b in merged.bores],
                "edge": [{"side": b["side"], "pos": b["pos"], "d": b["d"], "dp": b["dp"]} for b in merged.edge_bores],
            }

    # Cross-check map instances vs part.count (catches blob/product mismatches early).
    for part in project.all_parts:
        got = instance_counters.get(part.key, 0)
        if got and got != part.count:
            problems.append(f"{part.key}: xaritadagi nusxalar {got} ≠ detal soni {part.count}")

    if problems:
        raise ParseError("Kesish xaritasi mos kelmadi: " + " · ".join(problems[:5]))
    return result


def arra_parts_query(*where: ColumnElement[bool]) -> Select[tuple[int]]:
    """Marshrutida yoqilgan ARRA qadami bor detallar (`part_id`) — listning egasi shundan aniqlanadi."""
    return (
        select(PartRoute.part_id)
        .join(Post, Post.id == PartRoute.post_id)
        .where(
            Post.code == PostCode.ARRA,
            PartRoute.is_enabled == True,  # noqa: E712
            PartRoute.is_deleted == False,  # noqa: E712
            *where,
        )
    )


async def build_cutmap_state(db: AsyncSession, order: Order, post_id: int) -> CutmapState:
    """ARRA terminali (7.1.7), ROVER terminali va admin paneldagi ko'rinish (10.3) uchun umumiy.

    `done` — SHU postdagi skanlar bo'yicha: roverchi o'z listida o'zi kesganini ko'radi.
    """
    # Nostandart detallar — marshrutini texnolog qo'lda chizgan. Ular xaritada
    # boshqa rang bilan turadi: arrachi ularni odatdagi detal deb o'ylab qo'ymasin
    # (marshruti arradan boshlanmasligi ham mumkin, o'shanda skan qabul qilinmaydi).
    custom_parts = set(
        (
            await db.execute(
                select(Part.id).where(
                    Part.order_id == order.id,
                    Part.is_custom == True,  # noqa: E712
                    Part.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    instances = (
        (
            await db.execute(
                select(PartInstance).where(
                    PartInstance.order_id == order.id,
                    PartInstance.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    done_ids = set(
        (
            await db.execute(
                select(Scan.instance_id).where(
                    Scan.order_id == order.id,
                    Scan.post_id == post_id,
                    Scan.is_cancelled == False,  # noqa: E712
                    Scan.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    arra_parts = set((await db.execute(arra_parts_query(PartRoute.order_id == order.id))).scalars().all())
    waste_rows = (
        (
            await db.execute(
                select(WasteItem).where(
                    WasteItem.order_id == order.id,
                    WasteItem.is_deleted == False,  # noqa: E712
                )
            )
        )
        .scalars()
        .all()
    )
    # Paz/freza — `Part.xnc_summary` dan HAR SO'ROVDA. `order.cutmap` ichiga
    # yozilmaydi: u yuklashda muzlaydi, ya'ni eski buyurtma qayta yuklanmaguncha
    # bo'sh qolardi. Kalit — chek va `holes` bilan bir xil `CutmapCell.id`.
    model = CutmapModel.model_validate(order.cutmap) if order.cutmap else None
    machining: dict[str, CutmapMachining] = {}
    if model:
        kalit_boyicha = {
            f"{product_code}_{code}": (stored_machined_sides(xs), length, width)
            for code, product_code, xs, length, width in (
                await db.execute(
                    select(Part.code, Product.code, Part.xnc_summary, Part.length, Part.width)
                    .join(Product, Product.id == Part.product_id)
                    .where(Part.order_id == order.id, Part.is_deleted == False)  # noqa: E712
                )
            ).all()
        }
        for material in model.materials:
            for sheet in material.sheets:
                for cell in sheet.parts:
                    topilgan = kalit_boyicha.get(cell.key or "")
                    if not topilgan:
                        continue
                    ishlov, length, width = topilgan
                    if ishlov.paz or ishlov.frez or ishlov.paz_yollari or ishlov.frez_yollari:
                        machining[str(cell.id)] = CutmapMachining(
                            l=length,
                            w=width,
                            paz_sides=ishlov.paz,
                            frez_sides=ishlov.frez,
                            paz_paths=ishlov.paz_yollari,
                            frez_paths=ishlov.frez_yollari,
                        )

    return CutmapState(
        order_id=order.id,
        order_number=order.number,
        waste_items=[
            CutmapWasteItem(
                id=w.id,
                qr_text=w.qr_text,
                sheet_no=w.sheet_no,
                length=w.length,
                width=w.width,
                label_printed_at=w.label_printed_at,
            )
            for w in waste_rows
        ],
        model=model,
        machining=machining,
        instances=[
            CutmapInstanceState(
                instance_id=i.id,
                instance_no=i.instance_no,
                qr_text=i.qr_text,
                pattern_no=i.pattern_no,
                cell_index=i.cell_index,
                done=i.id in done_ids,
                label_printed_at=i.label_printed_at,
                custom=i.part_id in custom_parts,
                arra_route=i.part_id in arra_parts,
            )
            for i in instances
        ],
    )
