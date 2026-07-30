"""*.project XML parser (TZ 5.1–5.3).

Hard rules from the 205-file corpus analysis:
- A REAL XML parser only — regex is FORBIDDEN (old files contain `elb ="` with a space, 1014×).
- Encoding comes from the XML declaration (windows-1251 or UTF-8); ElementTree handles it
  when given raw bytes.
- good@id / operation@id / part@id are THREE separate id spaces — lookups stay inside
  their own element kind.
- Kerf lives ONLY in tool.cutting@swSawthick.
- part@id is NOT stable across files; the durable key is productCode_partCode (+ project.uuid).
"""

import xml.etree.ElementTree as ET

from .models import CutOperation, ParsedMaterial, ParsedPart, ParsedProduct, ParsedProject, ParseError
from .xnc import merge_xnc_ops, parse_xnc_program

_EDGE_SIDES = ("l", "r", "t", "b")

# GibLab'da 9 xil operatsiya turi bor ("+Операция" ro'yxati). Biz uchtasini o'qiymiz
# (CS, EL, XNC). Qolganlari ataylab o'tkazib yuboriladi, lekin ikkitasi tashqarida:
#   LB — GibLab yorliq shablonlari; tizim o'z yorlig'ini chiqaradi (TZ 5.2.8).
#   O  — furnitura komplektatsiyasi; sanoqlar `typeId="simple"` goodlarining o'zida bor,
#        ya'ni material registriga baribir tushadi.
# Qolgan to'rttasi HAQIQIY ishlab chiqarish bosqichi va import qilinmaydi — ular
# faylda uchrasa texnolog buni bilishi shart, aks holda bosqich jimgina yo'qoladi.
_HANDLED_OPS = {"CS", "EL", "XNC"}
_IGNORED_OPS = {"LB", "O"}
_OP_NAMES = {
    "CL": "погонажный раскрой (profil kesish)",
    "CN": "нестинговый раскрой (CNC nesting)",
    "SP": "обработка поверхности (yuza ishlovi)",
    "GR": "пазование (paz)",
}


def _f(el: ET.Element, attr: str) -> float | None:
    raw = el.get(attr)
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _i(el: ET.Element, attr: str, default: int = 0) -> int:
    raw = el.get(attr)
    try:
        return int(float(raw)) if raw not in (None, "") else default
    except ValueError:
        return default


def _dedupe_part_code(code: str, seen: set[str], product_code: str, warnings: list[str]) -> str:
    """Real exports repeat codes (e.g. the same product good twice) — rename deterministically
    so the durable key productCode_partCode stays unique (QR, SCX)."""
    if code not in seen:
        return code
    n = 2
    while f"{code}-{n}" in seen:
        n += 1
    renamed = f"{code}-{n}"
    warnings.append(f"Detal kodi takrorlangan: {product_code} ichida {code} — {renamed} deb saqlandi.")
    return renamed


def _build_part(p: ET.Element, product: ParsedProduct, seen: set[str], warnings: list[str]) -> ParsedPart:
    """Bitta <part> elementidan ParsedPart. Kod va o'lcham shu yerda normallashtiriladi."""
    code = p.get("code") or p.get("part.code") or ""
    if not code:
        # Eski GibLab eksporti (version 21052101) detal kodini umuman yozmaydi —
        # nomida kod o'rniga "№" turadi. Tartib raqamidan beramiz: GibLab'ning
        # o'z sxemasi ham shu (yangi eksportda code = "{blok}_{part.position}").
        code = f"{len(product.parts) + 1:03d}"
        if len(product.parts) == 0:
            warnings.append(
                f"{product.code}: faylda detal kodlari yo'q (eski GibLab eksporti) — "
                f"tartib raqami bo'yicha berildi (001, 002, ...)."
            )
    code = _dedupe_part_code(code, seen, product.code, warnings)
    seen.add(code)

    edges: dict[str, dict[str, object]] = {}
    for side in _EDGE_SIDES:
        if p.get(f"el{side}") is not None:
            edges[side] = {"mat": p.get(f"el{side}Mat"), "symbol": None}

    length = _f(p, "l") or _f(p, "dl")
    width = _f(p, "w") or _f(p, "dw")
    # Manfiy o'lcham fizik ma'noga ega emas — GibLab uni ba'zi X-profillarga bayroq
    # sifatida qo'yadi. Modul olamiz, aks holda hisobotlarda maydon manfiy chiqadi.
    if (length or 0) < 0 or (width or 0) < 0:
        warnings.append(f"{product.code}/{code}: faylda manfiy o'lcham ({length}x{width}) — moduli olindi.")
        length, width = abs(length or 0), abs(width or 0)

    return ParsedPart(
        file_part_id=int(p.get("id", 0)),
        product_code=product.code,
        code=code,
        name=p.get("name", code),
        count=_i(p, "count", 1),
        length=length,
        width=width,
        saw_length=_f(p, "jl"),
        saw_width=_f(p, "jw"),
        thickness=None,  # CS materialidan quyida to'ldiriladi
        txt=p.get("txt") == "true",
        material_name=None,
        edges=edges,
    )


def parse_project(content: bytes) -> ParsedProject:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ParseError(f"XML faylni o'qib bo'lmadi: {exc}") from exc
    if root.tag != "project":
        raise ParseError("Bu .project fayl emas — <project> ildiz elementi topilmadi.")

    goods = root.findall("good")
    operations = root.findall("operation")

    products_goods = [g for g in goods if g.get("typeId") == "product"]
    if not products_goods:
        raise ParseError("Faylda birorta mahsulot (product) topilmadi.")

    sheets = {int(g.get("id", 0)): g for g in goods if g.get("typeId") == "sheet"}
    bands = {int(g.get("id", 0)): g for g in goods if g.get("typeId") == "band"}
    # typeId="simple" — furnitura (petlya, yevrovint, dasta, napravlyayushiye...).
    # Faqat furnitura qo'yilgan eksportlarda uchraydi va listga joylashtirilmaydi:
    # bu yerda u faqat material registriga va sarf hisobiga tushadi.
    hardware = [g for g in goods if g.get("typeId") == "simple"]
    cutting_tools = {int(g.get("id", 0)): g for g in goods if g.get("typeId") == "tool.cutting"}
    edge_tools = [g for g in goods if g.get("typeId") == "tool.edgeline"]

    project = ParsedProject(
        uuid=root.get("project.uuid"),
        name=root.get("name"),
        generation="template",  # upgraded below if CS data is present
        currency=root.get("currency"),
        version=root.get("version"),
    )
    if edge_tools:
        project.edge_rest_side = _f(edge_tools[0], "elRestSide") or 30.0

    # --- materials (auto-registry, TZ 4.5) ---
    for gid, g in sheets.items():
        project.materials.append(
            ParsedMaterial(
                good_id=gid,
                kind="sheet",
                name=g.get("name", f"Sheet {gid}"),
                code=g.get("code"),
                thickness=_f(g, "t"),
                length=_f(g, "l"),
                width=_f(g, "w"),
                count=_f(g, "count"),
            )
        )
    for gid, g in bands.items():
        project.materials.append(
            ParsedMaterial(
                good_id=gid,
                kind="band",
                name=g.get("name", f"Band {gid}"),
                code=g.get("code"),
                thickness=_f(g, "t"),
                width=_f(g, "w"),
                count=_f(g, "count"),
            )
        )
    for g in hardware:
        project.materials.append(
            ParsedMaterial(
                good_id=int(g.get("id", 0)),
                kind="hardware",
                name=g.get("name", "Furnitura"),
                code=g.get("code"),
                count=_f(g, "count"),
            )
        )

    # --- products & parts ---
    part_by_file_id: dict[int, ParsedPart] = {}
    part_code_seen: dict[str, set[str]] = {}
    for g in products_goods:
        product = ParsedProduct(
            file_good_id=int(g.get("id", 0)),
            code=g.get("code") or g.get("name") or "PRODUCT",
            name=g.get("name", ""),
            count=_i(g, "count", 1),
            import_source=g.get("product.import"),
        )
        seen = part_code_seen.setdefault(product.code, set())
        for p in g.findall("part"):
            part = _build_part(p, product, seen, project.warnings)
            product.parts.append(part)
            part_by_file_id[part.file_part_id] = part
        project.products.append(product)

    # --- operations ---
    label_counter = 0  # file-global: matches GibSaw print order (TZ 5.8)
    xnc_ops_by_part: dict[int, list] = {}

    for op_el in operations:
        type_id = op_el.get("typeId")

        if type_id == "CS":
            label_counter = _parse_cs_operation(op_el, sheets, cutting_tools, part_by_file_id, project, label_counter)

        elif type_id == "EL":
            _apply_el_symbols(op_el, products_goods, part_by_file_id)

        elif type_id == "XNC":
            stub_el = op_el.find("part")
            if stub_el is None:
                continue
            # Usually an HTML-escaped attribute (TZ 5.2.7); some exports keep <program> as a child.
            program = op_el.get("program")
            if program is None:
                prog_el = op_el.find("program")
                if prog_el is not None:
                    program = ET.tostring(prog_el, encoding="unicode")
            if not program:
                continue
            pid = int(stub_el.get("id", 0))
            code = op_el.get("code") or ""
            xnc_ops_by_part.setdefault(pid, []).append(parse_xnc_program(code, program))

    unhandled = sorted(
        {
            t
            for op_el in operations
            if (t := op_el.get("typeId") or "") and t not in _HANDLED_OPS and t not in _IGNORED_OPS
        }
    )
    if unhandled:
        names = ", ".join(f"{t} — {_OP_NAMES.get(t) or 'nomaʼlum tur'}" for t in unhandled)
        project.warnings.append(
            f"Faylda import qilinmaydigan operatsiya bor: {names}. O'sha bosqich detallari vazifa ro'yxatiga tushmaydi."
        )

    for pid, ops in xnc_ops_by_part.items():
        target = part_by_file_id.get(pid)
        if target is None:
            project.warnings.append(f"XNC operatsiya noma'lum detalga ishora qiladi: part id={pid}")
            continue
        target.xnc_ops = merge_xnc_ops(ops)

    # --- generation detection (TZ 5.3.3) ---
    has_blob = any(c.data_blob for c in project.cut_ops)
    if has_blob and project.uuid:
        project.generation = "processed"
    else:
        project.generation = "template"

    return project


def _parse_cs_operation(
    op_el: ET.Element,
    sheets: dict[int, ET.Element],
    cutting_tools: dict[int, ET.Element],
    part_by_file_id: dict[int, ParsedPart],
    project: ParsedProject,
    label_counter: int,
) -> int:
    """One CS = one sheet material (TZ 5.2.5). Returns the advanced file-global label counter."""
    tool = cutting_tools.get(_i(op_el, "tool1"))
    material_el = op_el.find("material")
    mat_gid = int(material_el.get("id", 0)) if material_el is not None else 0
    sheet = sheets.get(mat_gid)
    stats = {
        key: _f(op_el, key) or 0.0
        for key in (
            "cPartCount",
            "cMaterialCount",
            "cWasteCount",
            "cWasteAmount",
            "cPartAmount",
            "cMaterialAmount",
            "cCountPackets",
            "cTrimLength",
            "cTrimCount",
            "cFilling",
        )
    }
    cut = CutOperation(
        op_id=_i(op_el, "id"),
        material_good_id=mat_gid,
        material_name=sheet.get("name", "") if sheet is not None else "",
        thickness=_f(sheet, "t") if sheet is not None else None,
        kerf=(_f(tool, "swSawthick") if tool is not None else None) or 3.0,  # the ONLY kerf source (TZ 5.3.4)
        trim_l=(_f(op_el, "cTrimL") or 2.0),
        trim_w=(_f(op_el, "cTrimW") or 2.0),
        stats=stats,
        data_blob=op_el.get("data") or None,
    )
    # Stub order = GibSaw label number (1-based, file-global) — TZ 5.2.3/5.8.
    for stub in op_el.findall("part"):
        pid = int(stub.get("id", 0))
        cut.stub_part_ids.append(pid)
        label_counter += 1
        ref_part = part_by_file_id.get(pid)
        if ref_part is not None:
            ref_part.label_num = label_counter
            ref_part.material_name = cut.material_name
            ref_part.thickness = cut.thickness
    # Stock + registered waste part defs live INSIDE the sheet good (TZ 5.2.3).
    if sheet is not None:
        for sp in sheet.findall("part"):
            spid = int(sp.get("id", 0))
            entry = {
                "l": _f(sp, "l") or _f(sp, "dl") or 0.0,
                "w": _f(sp, "w") or _f(sp, "dw") or 0.0,
                "rl": _f(sp, "rl") or 0.0,
                "rw": _f(sp, "rw") or 0.0,
            }
            if sp.get("waste") == "true":
                cut.waste_parts[spid] = entry
            else:
                cut.stock_parts[spid] = entry
    project.cut_ops.append(cut)
    return label_counter


def _apply_el_symbols(
    op_el: ET.Element,
    products_goods: list[ET.Element],
    part_by_file_id: dict[int, ParsedPart],
) -> None:
    """Attach the EL map symbol to every referencing part edge — part attrs point back
    via el{side}="@operation#N" (TZ 5.1.2)."""
    symbol = op_el.get("elSymbol")
    if not symbol:
        return
    op_id = _i(op_el, "id")
    for g in products_goods:
        for p in g.findall("part"):
            ref_part = part_by_file_id.get(int(p.get("id", 0)))
            if ref_part is None:
                continue
            for side in _EDGE_SIDES:
                if p.get(f"el{side}") == f"@operation#{op_id}" and side in ref_part.edges:
                    ref_part.edges[side]["symbol"] = symbol
