"""Cut-map visual model builder (TZ 5.7.5) — the JSON the ARRA terminal renders.

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

from .csblob import BlobPattern, BlobRecord, decode_cs_blob, self_check
from .models import ParsedPart, ParsedProject, ParseError


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
    (TZ 5.7.2). Children of an inner strip cut across the other axis.
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
        # type 1 (trim/kerf) consumes space only — kerf is not drawn separately (TZ 5.7.2)

        consumed += node.value
        # Guillotine cut at this boundary — edge-to-edge across the parent region (TZ 5.7.5).
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

        material: dict[str, Any] = {
            "name": cut.material_name,
            "thick": cut.thickness,
            "kerf": cut.kerf,
            "trimL": cut.trim_l,
            "trimW": cut.trim_w,
            "fill": cut.stats.get("cFilling"),
            "kd": cut.stats.get("cPartCount"),
            "kk": cut.stats.get("cMaterialCount"),
            "ko": cut.stats.get("cWasteCount"),
            "dr": cut.stats.get("cTrimLength"),
            "kr": cut.stats.get("cTrimCount"),
            "sheets": [],
        }

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
                    if wdef:  # useful size from the definition, not the raw cut (TZ 5.2.3)
                        entry["w"], entry["h"] = wdef["l"], wdef["w"]
                    entry.update({"id": cell["part_id"], "qty": 0, "waste": True, "name": "atxot"})
                else:
                    part = parts_by_file_id.get(cell["part_id"])
                    if part is None:
                        problems.append(
                            f"{cut.material_name}: blob noma'lum detalga ishora qiladi (id={cell['part_id']})"
                        )
                        continue
                    material_placed += pat.mult
                    rot = (
                        part.length is not None
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
                            "qty": 1,
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

    # Holes overlay (TZ 5.7.5): merged XNC per part, duplicates removed.
    for part in project.all_parts:
        merged = part.merged_machining()
        if merged and (merged.bores or merged.edge_bores):
            result.model["holes"][str(part.file_part_id)] = {
                "l": part.length,
                "w": part.width,
                "bores": [{"x": b["x"], "y": b["y"], "d": b["d"], "thru": b["thru"]} for b in merged.bores],
                "edge": [
                    {"side": b["side"], "pos": b["pos"], "d": b["d"], "dp": b["dp"], "thru": b["thru"]}
                    for b in merged.edge_bores
                ],
            }

    # Cross-check map instances vs part.count (catches blob/product mismatches early).
    for part in project.all_parts:
        got = instance_counters.get(part.key, 0)
        if got and got != part.count:
            problems.append(f"{part.key}: xaritadagi nusxalar {got} ≠ detal soni {part.count}")

    if problems:
        raise ParseError("Kesish xaritasi mos kelmadi: " + " · ".join(problems[:5]))
    return result
