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

from .models import (
    CutOperation,
    ParsedMaterial,
    ParsedPart,
    ParsedProduct,
    ParsedProject,
    ParseError,
    xml_bool,
)
from .xnc import merge_xnc_ops, parse_xnc_program

_EDGE_SIDES = ("l", "r", "t", "b")

# GibLab'da 9 xil operatsiya turi bor ("+Операция" ro'yxati). Biz uchtasini o'qiymiz
# (CS, EL, XNC), uchtasi ataylab jim o'tkaziladi:
#   LB — GibLab yorliq shablonlari; tizim o'z yorlig'ini chiqaradi (TZ 5.2.8).
#   O  — furnitura komplektatsiyasi; sanoqlar `typeId="simple"` goodlarining o'zida bor,
#        ya'ni material registriga baribir tushadi.
# CL — погонажный раскрой (profil kesish) alohida holat: uning detallari arrachiga
# BERILMAYDI (sexda profil kesish posti yo'q, profillar tayyor keladi), lekin faylda
# borligi texnologga ma'lum bo'lishi kerak — u profillarni ta'minlashni bilishi shart.
# Shuning uchun ogohlantirish emas, MA'LUMOT yoziladi: nechta operatsiya, nechta detal
# va zagotovka uzunligi. Profil kesish posti paydo bo'lsa: CL detallarini marshrutga
# qo'shish + yangi PostCode kerak.
# Qolgan uchtasi (CN, SP, GR) HAQIQIY bosqich va import qilinmaydi — ular faylda
# uchrasa texnolog buni bilishi shart, aks holda bosqich jimgina yo'qoladi.
_HANDLED_OPS = {"CS", "EL", "XNC"}
_IGNORED_OPS = {"LB", "O", "CL"}
_OP_NAMES = {
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


def _base_material(op_el: ET.Element) -> ET.Element | None:
    """Operatsiyaning ASOSIY materiali. Spetsifikatsiya `<material used="base">` bilan kesishdagi
    asosiy listni belgilaydi; korpusda kesish operatsiyasida material doim bitta (`used` ham
    yozilmagan), lekin bittadan ko'p bo'lsa birinchisini olish list nomini butun xarita bo'yicha
    xato ko'rsatardi."""
    mats = op_el.findall("material")
    return next((m for m in mats if m.get("used") == "base"), mats[0] if mats else None)


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
        # GibLab detal kodini TALAB QILMAYDI: eski eksport (21052101) uni umuman yozmaydi,
        # yangi eksportda ham dizayner bermasligi mumkin (1160.project, 23051701 buildi —
        # kod yo'q, nomi "01"). Tartib raqamidan beramiz: GibLab'ning o'z sxemasi ham shu
        # (kod berilganda u "{blok}_{part.position}" ko'rinishida bo'ladi).
        code = f"{len(product.parts) + 1:03d}"
        if len(product.parts) == 0:
            warnings.append(
                f"{product.code}: faylda detal kodlari yo'q — tartib raqami bo'yicha berildi "
                f"(001, 002, ...). QR va SCX nomlari shu raqamga bog'lanadi."
            )
    code = _dedupe_part_code(code, seen, product.code, warnings)
    seen.add(code)

    edges: dict[str, dict[str, object]] = {}
    for side in _EDGE_SIDES:
        if p.get(f"el{side}") is not None:
            edges[side] = {"mat": p.get(f"el{side}Mat"), "symbol": None}

    # Spetsifikatsiya (help/format_ru.html) to'rt juft o'lcham beradi va qaysi biri MAJBURIY
    # ekanini CS operatsiyasining `cSizeMode` i belgilaydi:
    #   cSizeMode=0 -> l/w   (zagotovka)
    #   cSizeMode=1 -> dl/dw (tayyor detal; korpusdagi 8 faylda hammasi shu)
    #   cSizeMode=2 -> jl/jw (prifugovkadan keyingi zagotovka)
    #   cl/cw       -> pilla o'lchami, majburiy emas
    # Zanjir bilan olamiz, aks holda 2-rejimdagi fayl o'lchamsiz detal berishi mumkin.
    # Korpusda cl/cw doim dl/dw ga teng (560 detal), ya'ni ko'rsatilgan o'lcham = pilla o'lchami.
    length = _f(p, "l") or _f(p, "dl") or _f(p, "cl") or _f(p, "jl")
    width = _f(p, "w") or _f(p, "dw") or _f(p, "cw") or _f(p, "jw")
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
        txt=xml_bool(p.get("txt")),
        material_name=None,
        edges=edges,
    )


def _allowance_warning(products_goods: list[ET.Element], operations: list[ET.Element]) -> str | None:
    """Ishlov qo'shimchasi (припуск) bo'lsa ogohlantirish matni, aks holda None.

    GibLab uni PILLA o'lchamiga qo'shadi va kesish xaritasida PUNKTIR chiziq bilan
    ko'rsatadi (help/question/stock.html). Bizning xarita punktir chizmaydi — ya'ni qo'shimcha
    bo'lsa arrachi detal chizig'iga qarab kesib qo'shimchani yo'qotadi. Korpusdagi 8 faylda
    hammasi nol, shuning uchun chizish qo'shilmadi; nolga teng bo'lmasa xabar beramiz.
    """
    per_part = sum(
        1
        for g in products_goods
        for pe in g.findall("part")
        if any((_f(pe, f"allowance{side}") or 0) > 0 for side in ("T", "B", "L", "R"))
    )
    overall = max((_f(op, "cAllowanceWorkpiece") or 0) for op in operations) if operations else 0.0
    if not per_part and overall <= 0:
        return None
    detail = f"{per_part} detalda" if per_part else f"umumiy {overall} mm"
    return (
        f"Faylda ishlov qo'shimchasi bor ({detail}). Kesish xaritasida u punktir chiziq bilan "
        f"ko'rsatilmaydi — arrachi o'lchamni GibLab kartasi bilan solishtirishi kerak."
    )


def _advisories(
    products_goods: list[ET.Element],
    operations: list[ET.Element],
    xnc_ops_by_part: dict[int, list],
) -> list[str]:
    """Faylning o'zi haqidagi xabarlar: import qilinmagan yoki chizilmagan narsalar.

    Bu tekshiruvlar parse natijasiga ta'sir qilmaydi — ular texnologga faylda nima borligini
    aytadi, aks holda bosqich yoki o'lcham jimgina yo'qoladi.
    """
    out: list[str] = []

    if (msg := _allowance_warning(products_goods, operations)) is not None:
        out.append(msg)

    # CL: arrachiga ketmaydi, lekin texnolog profillarni ta'minlashi uchun bilishi shart.
    cl_ops = [op for op in operations if op.get("typeId") == "CL"]
    if cl_ops:
        cl_parts = sum(len(op.findall("part")) for op in cl_ops)
        stock = sorted({raw for op in cl_ops if (raw := op.get("l"))})
        lengths = f", zagotovka {'/'.join(stock)} mm" if stock else ""
        out.append(
            f"Profil kesish (CL): {len(cl_ops)} operatsiya, {cl_parts} detal{lengths}. "
            f"Sexda kesilmaydi — profillar tayyor holda ta'minlanadi, arrachi ro'yxatiga tushmaydi."
        )

    unhandled = sorted(
        {
            t
            for op_el in operations
            if (t := op_el.get("typeId") or "") and t not in _HANDLED_OPS and t not in _IGNORED_OPS
        }
    )
    if unhandled:
        names = ", ".join(f"{t} — {_OP_NAMES.get(t) or 'nomaʼlum tur'}" for t in unhandled)
        out.append(
            f"Faylda import qilinmaydigan operatsiya bor: {names}. O'sha bosqich detallari vazifa ro'yxatiga tushmaydi."
        )

    # Korpusda detalda ko'pi bilan 2 ta XNC bor; ko'pi bo'lsa skan sonlari kutilmagan
    # bo'lishi mumkin (stage_sides har operatsiyaga +1 beradi), shuning uchun aytamiz.
    many_xnc = sum(1 for ops in xnc_ops_by_part.values() if len(ops) > 2)
    if many_xnc:
        out.append(
            f"{many_xnc} detalda 2 tadan ko'p XNC operatsiya bor. Hammasi saqlandi, lekin "
            f"skan sonini texnolog tekshirishi kerak (har operatsiya bir skan talab qiladi)."
        )

    # `description` faqat izoh emas: u ishlov dasturi kodini ham saqlashi mumkin —
    # `#nom` (yuz tomon) yoki `##nom` (orqa tomon), XNC shablon kutubxonasidan
    # (Настройки -> Папка XNC шаблонов). Bunday holatda faylda XNC operatsiyasi
    # BO'LMAYDI va biz butun ishlovni yo'qotamiz: teshik ham, PRISADKA/PAZ/ROVER
    # bosqichi ham chiqmaydi. Korpusda ishlatilmagan.
    tpl_xnc = sum(
        1 for g in products_goods for pe in g.findall("part") if (pe.get("description") or "").lstrip().startswith("#")
    )
    if tpl_xnc:
        out.append(
            f"{tpl_xnc} detalda ishlov shablon nomi bilan berilgan (description dagi #kod). "
            f"Shablon kutubxonasi o'qilmaydi — teshik va ishlov bosqichlari chiqmaydi."
        )

    # minusCount — omborda tayyor turgan nusxalar (GibLab "Минус количество", 12.05.21).
    # GibLab ularni kesishga qo'ymaydi, biz esa `count` bo'yicha hammasini ishlab chiqaramiz.
    minus = sum(1 for g in products_goods for pe in g.findall("part") if (_f(pe, "minusCount") or 0) > 0)
    if minus:
        out.append(
            f"{minus} detalda 'minus miqdor' bor (omborda tayyor nusxalar). Tizim baribir "
            f"to'liq miqdorni ishlab chiqaradi — texnolog miqdorni tekshirishi kerak."
        )

    # `turn` (0/1/2/3 = 0/90/180/270°), `mirHor`, `mirVert` BUTUN dasturni o'zgartiradi. Biz
    # koordinatalarni dasturdan qanday bo'lsa shundayligicha olamiz, ya'ni bunday operatsiyada
    # teshiklar boshqa joyga tushardi va buni hech kim sezmasdi. Korpusdagi 505 dasturda
    # `turn=0`, `mirHor=false`, `mirVert=false` — shuning uchun ogohlantirish yetarli.
    transformed = sorted(
        {
            op_el.get("code") or f"#{op_el.get('id')}"
            for op_el in operations
            if op_el.get("typeId") == "XNC"
            and (
                (op_el.get("turn") or "0") not in ("0", "")
                or xml_bool(op_el.get("mirHor"))
                or xml_bool(op_el.get("mirVert"))
            )
        }
    )
    if transformed:
        out.append(
            f"XNC dasturi aylantirilgan yoki aks ettirilgan (turn/mirHor/mirVert): {', '.join(transformed[:5])}. "
            f"Teshik koordinatalari o'zgarmagan holda olinadi — SCX faylni CNC'da tekshirish shart."
        )

    notes = sorted({n for ops in xnc_ops_by_part.values() for op in ops for n in op.notes})
    out.extend(f"XNC: {n}." for n in notes)

    unknown_xnc = sorted({t for ops in xnc_ops_by_part.values() for op in ops for t in op.unknown_tags})
    if unknown_xnc:
        out.append(
            f"XNC dasturida o'qilmagan teg: {', '.join(unknown_xnc)}. "
            f"O'sha ishlov yorliq va teshik xaritasida ko'rinmaydi — texnolog tekshirishi kerak."
        )

    return out


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
            _apply_el_symbols(op_el, products_goods, part_by_file_id, bands)

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
            xnc_ops_by_part.setdefault(pid, []).append(parse_xnc_program(code, program, op_el.get("side")))

    project.warnings.extend(_advisories(products_goods, operations, xnc_ops_by_part))

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
        # Optimallashtirilgan faylda ham blobsiz kesish operatsiyasi bo'lishi mumkin: texnolog
        # bir materialni optimallashtirmagan. `build_cutmap` uni jimgina o'tkazib yuboradi
        # (nusxa tekshiruvi ham 0 ni sanamaydi), lekin detallari arrachiga baribir tushadi —
        # ya'ni vazifa bor, xarita yo'q. Faqat shu materialni aytamiz, fayl rad etilmaydi.
        unmapped = [c.material_name or f"operatsiya #{c.op_id}" for c in project.cut_ops if not c.data_blob]
        if unmapped:
            project.warnings.append(
                "Kesish xaritasi yo'q material: " + ", ".join(unmapped) + " — GibLab'da optimallashtirilmagan."
            )
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
    material_el = _base_material(op_el)
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
        # Yagona kerf manbasi (TZ 5.3.4). Yozilmasa GibLab o'zining standarti — 4.4 mm — bilan
        # optimallashtirgan (spetsifikatsiya, `swSawthick`), shuning uchun zaxira qiymat ham 4.4:
        # eski eksportda (`tool.cutting` bo'sh) arrachiga 3.0 deb yolg'on ko'rsatilardi.
        kerf=(_f(tool, "swSawthick") if tool is not None else None) or 4.4,
        # Torsovka. Zaxira qiymatlar spetsifikatsiyadagi GibLab standarti (10 mm) — ilgari bu
        # yerda korpusdan olingan 2.0 turardi, ya'ni atribut yozilmagan faylda arrachi 2 mm
        # ko'rib, GibLab esa 10 mm bilan optimallashtirgan bo'lardi. Geometriyaga ta'sir qilmaydi
        # (torsovka blobdan, type=1), faqat xarita sarlavhasida ko'rsatiladi.
        trim_l=(_f(op_el, "cTrimL") or 10.0),
        trim_w=(_f(op_el, "cTrimW") or 10.0),
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
            if xml_bool(sp.get("waste")):
                cut.waste_parts[spid] = entry
            else:
                cut.stock_parts[spid] = entry
    project.cut_ops.append(cut)
    return label_counter


def _apply_el_symbols(
    op_el: ET.Element,
    products_goods: list[ET.Element],
    part_by_file_id: dict[int, ParsedPart],
    bands: dict[int, ET.Element],
) -> None:
    """Attach the EL map symbol to every referencing part edge — part attrs point back
    via el{side}="@operation#N" (TZ 5.1.2)."""
    symbol = op_el.get("elSymbol")
    # Kromkalash operatsiyasida `used="base"` KLEY emas, LENTA ni bildiradi (spetsifikatsiya).
    # Detalning `el{side}Mat` i yozilmasligi mumkin (korpusda 779 qirradan 21 tasi) — o'shanda
    # yorliqdagi lenta katakchasi bo'sh chiqib, kromkachi qaysi lentani olishini bilmasdi.
    mat_el = _base_material(op_el)
    band = bands.get(int(mat_el.get("id", 0))) if mat_el is not None else None
    band_name = band.get("name") if band is not None else None
    if not symbol and not band_name:
        return
    op_id = _i(op_el, "id")
    for g in products_goods:
        for p in g.findall("part"):
            ref_part = part_by_file_id.get(int(p.get("id", 0)))
            if ref_part is None:
                continue
            for side in _EDGE_SIDES:
                if p.get(f"el{side}") == f"@operation#{op_id}" and side in ref_part.edges:
                    edge = ref_part.edges[side]
                    if symbol:
                        edge["symbol"] = symbol
                    if not edge.get("mat") and band_name:
                        edge["mat"] = band_name
