"""Self-check for the GibLab parser stack (TZ 5): synthetic .project + hand-encoded CS blob.

Run: uv run python -m tests.test_giblab  (assert-based, no framework)
"""

import struct
from base64 import b64encode
from xml.sax.saxutils import quoteattr

from app.services.giblab import parse_project
from app.services.giblab.csblob import decode_cs_blob
from app.services.giblab.cutmap import build_cutmap
from app.services.giblab.models import XncOp
from app.services.giblab.scx import generate_scx, scx_filename
from app.services.giblab.xnc import merge_xnc_ops, parse_xnc_program


def make_blob() -> str:
    """One pattern, mult=2, sheet 2750×1830, horizontal root axis.

    Layout: [trim 2] [strip 500: trim 2 | part#1 1000 | waste#90 1500] [strip 400: part#3 600]
    """
    out = bytearray()
    out += struct.pack(">I", 0) + struct.pack(">I", 1) + bytes([3]) + struct.pack(">I", 1)

    def rec(depth: int, rtype: int, value: float, qty: int, pid: int) -> bytes:
        return struct.pack(">BdBBi", (depth << 3) | rtype, value, 0, qty, pid)

    records = [
        rec(1, 1, 2.0, 1, -1),  # top trim
        rec(1, 2, 500.0, 1, -1),  # strip 1
        rec(2, 1, 2.0, 1, -1),  # left trim
        rec(2, 3, 1000.0, 1, 1),  # part A
        rec(2, 4, 1500.0, 1, 90),  # registered waste
        rec(1, 2, 400.0, 1, -1),  # strip 2
        rec(2, 3, 600.0, 1, 3),  # part B
    ]
    nr = len(records) + 1  # + slot

    out += struct.pack(">I", 2)  # mult
    out += struct.pack(">d", 2750.0) + struct.pack(">d", 1830.0)  # L, W (dims)
    out += struct.pack(">I", 80) + bytes([0])  # stock part id, pad
    out += struct.pack(">d", -1.0) * 4  # signature
    out += struct.pack(">I", 4)  # partCount (2 cells × mult 2)
    out += struct.pack(">d", 4.2925)  # wasteArea per sheet
    out += struct.pack(">I", 4)  # partCount dup
    out += struct.pack(">d", 0.74)  # partArea per sheet
    out += struct.pack(">I", 1)  # wasteCount (multsiz)
    out += struct.pack(">d", 4.2925)  # wasteArea dup
    out += struct.pack(">I", 1)  # packets
    out += struct.pack(">d", 7.5)  # cutLength m
    out += struct.pack(">I", 5)  # cutCount
    out += struct.pack(">d", 0.9)  # filling
    out += struct.pack(">I", nr)
    out += rec(0, 1, 0.0, 0, -1)  # null slot → horizontal root axis
    for r in records:
        out += r
    return b64encode(bytes(out)).decode()


def make_project_xml(blob: str) -> bytes:
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<project name="3014 Test" project.uuid="49826456-aaaa-bbbb-cccc-121212121212" currency="UZS" version="23051701">
  <good typeId="product" id="1" code="301401" name="01 Kuxniya" count="1">
    <part id="1" code="01_001" name="01_001 BOK" l="1000" w="500" jl="998" jw="500" count="2"
          ell="@operation#1" ellMat="06-19 SASNA" elt="@operation#1" eltMat="06-19 SASNA"/>
    <part id="3" code="01_002" name="01_002 TOKCHA" l="600" w="400" count="2"/>
  </good>
  <good typeId="sheet" id="5" name="LDSP OQ GLYANETS" t="16" l="2750" w="1830" count="2">
    <part id="80" l="2750" w="1830" count="10000"/>
    <part id="90" l="1490" w="490" waste="true" business="true" sheetId="80" rl="1500" rw="500" usedCount="0"/>
  </good>
  <good typeId="band" id="11" name="06-19 SASNA" t="1" w="19" count="12"/>
  <good typeId="tool.cutting" id="2" swSawthick="3"/>
  <good typeId="tool.edgeline" id="4" elRestSide="30"/>
  <operation typeId="CS" id="6" tool1="2" cPartCount="4" cMaterialCount="2" cWasteCount="2"
             cWasteAmount="8.585" cPartAmount="1.48" cCountPackets="1" cTrimLength="7.5"
             cTrimCount="5" cFilling="0.9" cTrimL="2" cTrimW="2" data="{blob}">
    <material id="5" count="2"/>
    <part id="1"/>
    <part id="3"/>
  </operation>
  <operation typeId="EL" id="1" tool1="4" elSymbol="A" elColor="#000000" elLength="6.0">
    <material id="11"/>
    <part id="1"/>
  </operation>
  <operation typeId="XNC" id="100" code="301401_01_001" typeName="01_001 BOK">
    <part id="1"/>
    <program dx="1000" dy="500" dz="16">
      <tool name="Bore8" d="8"/>
      <var name="throughBoreDepth" type="0" expr="dz+3"/>
      <bf x="34" y="70" dp="12.5" name="Bore8"/>
      <bf x="34" y="430" dp="throughBoreDepth" name="Bore8"/>
      <bl y="70" z="8" dp="34" name="Bore8"/>
      <gr x1="0" y1="50" x2="1000" y2="50" dp="8" t="4"/>
    </program>
  </operation>
  <operation typeId="XNC" id="101" code="301401_01_001_2" typeName="01_001 BOK">
    <part id="1"/>
    <program dx="1000" dy="500" dz="16">
      <tool name="Mill8" d="8"/>
      <ms x="10" y="10" dp="16" c="1" name="Mill8"/>
      <ml x="500" y="10"/>
      <mac x="600" y="110" cx="500" cy="110" dir="true"/>
    </program>
  </operation>
</project>"""
    return xml.encode("utf-8")


def test_blob_decoder() -> None:
    patterns = decode_cs_blob(make_blob())
    assert len(patterns) == 1
    p = patterns[0]
    assert p.mult == 2 and p.length == 2750.0 and p.width == 1830.0
    assert p.stock_part_id == 80 and p.part_count == 4 and p.cut_count == 5
    assert p.root_axis_vertical is False and p.leading_trim is None
    assert len(p.records) == 3  # trim + 2 strips
    strip1 = p.records[1]
    assert strip1.type == 2 and len(strip1.children) == 3
    assert [c.type for c in strip1.children] == [1, 3, 4]
    print("blob decoder OK")


def test_parser_and_routes() -> None:
    project = parse_project(make_project_xml(make_blob()))
    assert project.generation == "processed"
    assert project.uuid and project.name == "3014 Test"
    assert len(project.products) == 1 and len(project.all_parts) == 2
    assert {m.kind for m in project.materials} == {"sheet", "band"}

    part_a, part_b = project.all_parts
    assert part_a.key == "301401_01_001" and part_a.count == 2
    assert part_a.label_num == 1 and part_b.label_num == 2
    assert part_a.kromka_sides == 2
    assert part_a.edges["l"]["symbol"] == "A" and part_a.edges["t"]["symbol"] == "A"
    assert part_a.material_name == "LDSP OQ GLYANETS" and part_a.thickness == 16.0

    # XNC: merged, never "last one wins" (TZ 5.2.7)
    assert len(part_a.xnc_ops) == 2
    sides = part_a.stage_sides()
    assert sides == {"PRISADKA": 1, "PAZ": 1, "ROVER": 1}
    merged = part_a.merged_machining()
    assert merged is not None
    assert len(merged.bores) == 2 and len(merged.edge_bores) == 1
    assert merged.bores[1]["thru"] is True  # dp = dz+3 = 19 >= 16
    assert len(merged.grooves) == 1 and len(merged.mills) == 1
    print("parser + routes OK")


def test_cutmap() -> None:
    project = parse_project(make_project_xml(make_blob()))
    result = build_cutmap(project)
    model = result.model
    assert len(model["materials"]) == 1
    mat = model["materials"][0]
    assert mat["kerf"] == 3.0 and len(mat["sheets"]) == 1
    sheet = mat["sheets"][0]
    assert sheet["mult"] == 2 and sheet["L"] == 2750.0

    cells = sheet["parts"]
    part_cells = [c for c in cells if not c["waste"]]
    waste_cells = [c for c in cells if c["waste"]]
    assert len(part_cells) == 2 and len(waste_cells) == 1

    a = next(c for c in part_cells if c["key"] == "301401_01_001")
    assert (a["x"], a["y"], a["w"], a["h"]) == (2.0, 2.0, 1000.0, 500.0)
    assert a["rot"] is False and a["num"] == 1
    assert a["eW"] == ["A", None] and a["eH"] == ["A", None]

    w = waste_cells[0]
    assert (w["w"], w["h"]) == (1490.0, 490.0)  # useful size from def, not raw 1500×500

    b = next(c for c in part_cells if c["key"] == "301401_01_002")
    assert (b["x"], b["y"], b["w"], b["h"]) == (0.0, 502.0, 600.0, 400.0)

    # bindings: one instance per copy — part A: 1 cell × mult 2; part B ditto
    keys = [x.part_key for x in result.bindings]
    assert keys.count("301401_01_001") == 2 and keys.count("301401_01_002") == 2

    holes = model["holes"]["1"]
    assert len(holes["bores"]) == 2 and len(holes["edge"]) == 1
    print("cutmap OK")


def test_scx() -> None:
    project = parse_project(make_project_xml(make_blob()))
    part_a = project.all_parts[0]
    op1, op2 = part_a.xnc_ops
    assert scx_filename(part_a, op1) == "301401_01_001.scx"
    assert scx_filename(part_a, op2) == "301401_01_001_2.scx"

    scx = generate_scx(part_a, op1)
    assert 'Length="1000"' in scx and 'Width="500"' in scx and 'Thickness="16"' in scx
    # Y_scx = Width − y_program: bf y=70 → 430 (TZ 5.6.3)
    assert 'Y="430"' in scx
    # edge bore bl y=70 → Face="4", X="0", Y="430", Z="8"
    assert 'Face="4" Type="1" Diameter="8" Depth="34" X="0" Y="430" Z="8"' in scx.replace("\n", " ").replace(
        "  ", " "
    ) or ('Face="4"' in scx and 'Depth="34"' in scx)
    assert "<Edge " in scx  # edge group present (2 banded sides)
    print("scx OK")


def test_windows_1251_template() -> None:
    xml = (
        '<?xml version="1.0" encoding="windows-1251"?>\n'
        '<project importBMV="1.86">'
        '<good typeId="product" id="1" code="200" name="Шкаф" count="1">'
        '<part id="1" code="00_001" name="боковина" dl="700" dw="500" count="1"/>'
        "</good>"
        '<operation typeId="CS" id="2"><part id="1"/></operation>'
        "</project>"
    ).encode("windows-1251")
    project = parse_project(xml)
    assert project.generation == "template"
    assert project.products[0].name == "Шкаф"  # Cyrillic survives cp1251 decode (TZ 5.3.1)
    assert project.all_parts[0].length == 700.0  # dl fallback for old generation
    print("windows-1251 template OK")


def test_old_export_without_part_codes() -> None:
    """GibLab 21052101 eksporti: detallarda code yo'q (nomida kod o'rniga "№"),
    XNC esa standart konstantani e'lonsiz ishlatadi. Ikkalasi ham fayl umuman
    import bo'lmasligiga olib kelardi."""
    program = (
        '<program dx="1000" dy="500" dz="16">'
        '<tool name="Mill40" d="40"/>'
        # throughCutDepth <var> bilan e'lon QILINMAGAN — eski eksportning o'zi shunday
        '<ms x="60" y="60" dp="throughCutDepth" name="Mill40"/>'
        '<ml x="940" y="60"/>'
        '<bf x="100" y="200" dp="throughBoreDepth" name="Bore8"/>'
        "</program>"
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<project version="21052101">'
        '<good typeId="product" id="1" code="200101" name="01" count="1">'
        '<part id="1" name="№ polka $1,2,3$" dl="1000" dw="500" count="1"/>'
        '<part id="2" name="№ bok" dl="800" dw="400" count="2"/>'
        "</good>"
        f'<operation typeId="XNC" id="3" program={quoteattr(program)}><part id="1"/></operation>'
        "</project>"
    ).encode()
    project = parse_project(xml)

    parts = project.all_parts
    assert [p.code for p in parts] == ["001", "002"]  # tartib raqamidan
    assert [p.key for p in parts] == ["200101_001", "200101_002"]  # QR/SCX uchun yaroqli
    assert any("detal kodlari yo'q" in w for w in project.warnings)
    assert len(project.warnings) == 1  # har detal uchun emas, bir marta

    op = parts[0].xnc_ops[0]
    assert op.mills[0][0]["dp"] == 19.0  # throughCutDepth = dz+3
    assert op.bores[0]["dp"] == 19.0  # throughBoreDepth = dz+3
    print("old export (kodsiz detal + e'lonsiz XNC konstanta) OK")


def test_negative_dimensions() -> None:
    """GibLab ba'zi X-profillarga manfiy uzunlik yozadi (kupe alyuminiy profillari).
    Manfiy o'lcham hisobotlarda maydonni manfiy qiladi — moduli olinadi va ogohlantiriladi."""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<project version="21052101">'
        '<good typeId="product" id="1" code="4210" name="Model2" count="1">'
        '<part id="1" code="X1" name="№ X1" dl="-818" dw="26" count="1"/>'
        '<part id="2" code="A1" name="bok" dl="700" dw="500" count="1"/>'
        "</good>"
        "</project>"
    ).encode()
    project = parse_project(xml)

    x1, a1 = project.all_parts
    assert (x1.length, x1.width) == (818.0, 26.0)  # moduli olindi
    assert (a1.length, a1.width) == (700.0, 500.0)  # musbat o'lcham tegilmaydi
    assert sum("manfiy o'lcham" in w for w in project.warnings) == 1
    print("manfiy o'lcham normallashtirish OK")


def test_hardware_goods() -> None:
    """typeId="simple" — furnitura (petlya, yevrovint...). Faqat furnitura qo'yilgan
    eksportlarda bo'ladi; ilgari parser uni umuman o'qimasdi va material registrida
    "Furnitura" bo'limi doim bo'sh turardi."""
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<project version="21052101">'
        '<good typeId="product" id="1" code="4210" name="Model2" count="1">'
        '<part id="1" code="A1" name="bok" dl="700" dw="500" count="1"/>'
        "</good>"
        '<good typeId="sheet" id="5" name="LDSP OQ" t="16" l="2750" w="1830" count="2"/>'
        '<good typeId="simple" id="7" code="PR teks 0" name="Petlya ROBUST" unit="шт" count="14"/>'
        '<good typeId="simple" id="8" name="Yevrovint" unit="шт" count="72"/>'
        "</project>"
    ).encode()
    project = parse_project(xml)

    hw = [m for m in project.materials if m.kind == "hardware"]
    assert len(hw) == 2
    assert (hw[0].code, hw[0].name, hw[0].count) == ("PR teks 0", "Petlya ROBUST", 14.0)
    assert hw[1].code is None and hw[1].count == 72.0  # kodsiz furnitura ham o'tadi
    # Furnitura listga joylashtirilmaydi — detal bo'lib qolmasligi shart
    assert [p.code for p in project.all_parts] == ["A1"]
    print("furnitura (typeId=simple) OK")


def test_size_mode_fallback() -> None:
    """Spetsifikatsiya to'rt juft o'lcham beradi va qaysi biri majburiy ekanini cSizeMode
    belgilaydi (0=l/w, 1=dl/dw, 2=jl/jw; cl/cw — pilla o'lchami, majburiy emas).
    Ilgari parser faqat l/w va dl/dw ni bilardi — 2-rejimdagi fayl o'lchamsiz detal berardi."""

    def one(attrs: str) -> tuple[float | None, float | None]:
        xml = (
            '<project version="1"><good typeId="product" id="1" code="42" name="M" count="1">'
            f'<part id="1" code="A1" count="1"{attrs}/></good></project>'
        ).encode()
        part = parse_project(xml).all_parts[0]
        return part.length, part.width

    assert one(' l="700" w="500"') == (700.0, 500.0)  # cSizeMode=0
    assert one(' dl="701" dw="501"') == (701.0, 501.0)  # cSizeMode=1
    assert one(' cl="702" cw="502"') == (702.0, 502.0)  # pilla o'lchami
    assert one(' jl="703" jw="503"') == (703.0, 503.0)  # cSizeMode=2 — ilgari None edi
    # Zanjir tartibi: l/w eng ustun
    assert one(' l="700" w="500" dl="9" dw="9" jl="8" jw="8"') == (700.0, 500.0)
    print("o'lcham zanjiri (cSizeMode) OK")


def test_template_machining_warning() -> None:
    """`description` ishlov dasturi kodini saqlashi mumkin: #nom (yuz) yoki ##nom (orqa).
    Bunday holatda faylda XNC operatsiyasi bo'lmaydi va butun ishlov yo'qoladi."""

    def build(desc: str) -> bytes:
        return (
            '<project version="1"><good typeId="product" id="1" code="42" name="M" count="1">'
            f'<part id="1" code="A1" dl="700" dw="500" count="1" description="{desc}"/>'
            "</good></project>"
        ).encode()

    def hits(xml: bytes) -> list[str]:
        return [w for w in parse_project(xml).warnings if "shablon nomi" in w]

    assert hits(build("oddiy izoh")) == []  # oddiy izoh — jim
    assert len(hits(build("#PETLYA35"))) == 1  # yuz tomon
    assert len(hits(build("##PAZ4"))) == 1  # orqa tomon
    print("shablon-ishlov ogohlantirishi OK")


def test_many_xnc_ops_kept() -> None:
    """GibLab detalga 2 tadan ko'p ishlov dasturi berishi mumkin (yorliq shabloni XNC1..XNC5
    maydonlarini taklif qiladi). Ilgari parser 2 tadan ko'pini ko'rsa BUTUN faylni rad etardi —
    ya'ni uch tomoni ishlanadigan detal import bo'lmasdi. Endi hammasi saqlanadi + advisory."""
    ops = [XncOp(code=f"42_A1_{i}", side2=(i == 2), dx=700, dy=500, dz=16) for i in range(3)]
    kept = merge_xnc_ops(ops)
    assert len(kept) == 3  # birortasi yo'qolmaydi
    assert [o.code for o in kept] == ["42_A1_0", "42_A1_1", "42_A1_2"]  # barqaror tartib

    prog = (
        '<program dx="700" dy="500" dz="16"><tool name="Bore8" d="8"/>'
        '<bf x="10" y="10" dp="12" name="Bore8"/></program>'
    )
    ops_xml = "".join(
        f'<operation typeId="XNC" id="{10 + i}" code="42_A1{"_2" if i == 1 else ""}" '
        f'program={quoteattr(prog)}><part id="1"/></operation>'
        for i in range(3)
    )
    xml = (
        '<project version="23051701">'
        '<good typeId="product" id="1" code="42" name="M" count="1">'
        '<part id="1" code="A1" dl="700" dw="500" count="1"/>'
        "</good>" + ops_xml + "</project>"
    ).encode()
    project = parse_project(xml)
    assert len(project.all_parts[0].xnc_ops) == 3
    assert project.all_parts[0].stage_sides() == {"PRISADKA": 3}  # har operatsiya bir skan
    assert any("XNC operatsiya bor" in w for w in project.warnings)
    print("2 tadan ko'p XNC saqlanadi OK")


def test_minus_count_warning() -> None:
    """minusCount — omborda tayyor turgan nusxalar (GibLab "Минус количество"). GibLab ularni
    kesishga qo'ymaydi, biz esa count bo'yicha hammasini ishlab chiqaramiz — shuning uchun
    texnologga aytamiz. Korpusda hamma joyda nol."""

    def build(extra: str) -> bytes:
        return (
            '<project version="1"><good typeId="product" id="1" code="42" name="M" count="1">'
            f'<part id="1" code="A1" dl="700" dw="500" count="5"{extra}/>'
            "</good></project>"
        ).encode()

    assert [w for w in parse_project(build(' minusCount="0"')).warnings if "minus miqdor" in w] == []
    hit = [w for w in parse_project(build(' minusCount="2"')).warnings if "minus miqdor" in w]
    assert len(hit) == 1 and "1 detalda" in hit[0]
    print("minus miqdor ogohlantirishi OK")


def test_allowance_warning() -> None:
    """Ishlov qo'shimchasi (припуск) GibLab kartasida punktir chiziq bilan chiziladi
    (help/question/stock.html); bizning xarita chizmaydi. Nolga teng bo'lmasa ogohlantiramiz —
    aks holda arrachi qo'shimchani yo'qotib kesadi. Har detalda ham, umumiy ham bo'lishi mumkin."""

    def build(part_extra: str = "", op: str = "") -> bytes:
        return (
            '<project version="1">'
            '<good typeId="product" id="1" code="42" name="M" count="1">'
            f'<part id="1" code="A1" dl="700" dw="500" count="1"{part_extra}/>'
            "</good>" + op + "</project>"
        ).encode()

    def hits(xml: bytes) -> list[str]:
        return [w for w in parse_project(xml).warnings if "qo'shimchasi" in w]

    assert hits(build()) == []  # qo'shimchasiz — jim
    assert hits(build(' allowanceT="0" allowanceB="0"')) == []  # nol — jim

    per_part = hits(build(' allowanceT="5"'))
    assert len(per_part) == 1 and "1 detalda" in per_part[0]

    overall = hits(build(op='<operation typeId="CS" id="2" cAllowanceWorkpiece="3"/>'))
    assert len(overall) == 1 and "3.0 mm" in overall[0]
    print("ishlov qo'shimchasi ogohlantirishi OK")


def test_hole_arrays_and_inheritance() -> None:
    """XNC dasturining uch xususiyati (help/format_ru.html, "XNC программа"):
    1. `ac`/`as`/`av` — bitta element teshik QATORINI bildiradi (32 mm javon teshiklari).
    2. `enable="false"` — element o'chirilgan, bajarilmaydi.
    3. Atribut yozilmasa OLDINGI qiymat olinadi; ilgari bu ParseError berardi."""

    def prog(body: str) -> str:
        return f'<program dx="1000" dy="500" dz="16"><tool name="Bore8" d="8"/>{body}</program>'

    # Vertikal qator: y bo'ylab qadam
    op = parse_xnc_program("t", prog('<bf x="37" y="100" dp="12" ac="8" as="32" av="true" name="Bore8"/>'))
    assert len(op.bores) == 8
    assert [b["y"] for b in op.bores] == [100.0 + 32 * i for i in range(8)]
    assert all(b["x"] == 37.0 for b in op.bores)  # vertikalda x o'zgarmaydi

    # Gorizontal qator (korpusdagi av=false): x bo'ylab
    op = parse_xnc_program("t", prog('<bf x="37" y="100" dp="12" ac="3" as="32" av="false" name="Bore8"/>'))
    assert [b["x"] for b in op.bores] == [37.0, 69.0, 101.0]

    # ac=1 — korpusdagi holat, bitta teshik (regressiya himoyasi)
    assert len(parse_xnc_program("t", prog('<bf x="37" y="100" dp="12" ac="1" name="Bore8"/>')).bores) == 1

    # Qadam berilmasa qator yasamaymiz
    assert len(parse_xnc_program("t", prog('<bf x="37" y="100" dp="12" ac="5" name="Bore8"/>')).bores) == 1

    # enable="false" — o'tkazib yuboriladi
    two = '<bf x="1" y="1" dp="12" enable="false" name="Bore8"/><bf x="2" y="2" dp="12" name="Bore8"/>'
    op = parse_xnc_program("t", prog(two))
    assert [b["x"] for b in op.bores] == [2.0]

    # Meros: ikkinchi teshikda dp yo'q -> oldingi qiymat (ilgari ParseError edi)
    op = parse_xnc_program("t", prog('<bf x="10" y="10" dp="12" name="Bore8"/><bf x="50" y="10" name="Bore8"/>'))
    assert [b["dp"] for b in op.bores] == [12.0, 12.0]

    # Qirra teshiklari qatori — chet bo'ylab yagona o'q
    op = parse_xnc_program("t", prog('<bl y="50" dp="34" ac="4" as="64" name="Bore8"/>'))
    assert [b["pos"] for b in op.edge_bores] == [50.0, 114.0, 178.0, 242.0]
    assert all(b["side"] == "l" for b in op.edge_bores)
    print("teshik qatori + enable + atribut merosi OK")


def test_unknown_xnc_tag_warning() -> None:
    """GibLab XNC dasturi spetsifikatsiyasida <ma> (yoy) va <xy> (koordinata boshi) ham bor;
    biz ularni hisoblamaymiz. Jimgina tashlash xavfli — <xy> e'tiborsiz qolsa undan keyingi
    barcha teshik joylari xato bo'ladi. Shuning uchun ogohlantirish chiqadi."""
    program = (
        '<program dx="1000" dy="500" dz="16">'
        '<tool name="Bore8" d="8"/>'
        '<xy x="10" y="20"/>'
        '<bf x="34" y="70" dp="12" name="Bore8"/>'
        "</program>"
    )
    op = parse_xnc_program("t_001", program)
    assert sorted(op.unknown_tags) == ["xy"]
    assert len(op.bores) == 1  # bilgan teglar baribir o'qiladi

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<project version="23051701">'
        '<good typeId="product" id="1" code="42" name="M" count="1">'
        '<part id="1" code="A1" name="bok" dl="1000" dw="500" count="1"/>'
        "</good>"
        f'<operation typeId="XNC" id="3" code="42_A1" program={quoteattr(program)}>'
        '<part id="1"/></operation>'
        "</project>"
    ).encode()
    hits = [w for w in parse_project(xml).warnings if "XNC dasturida o'qilmagan teg" in w]
    assert len(hits) == 1 and "xy" in hits[0]
    print("noma'lum XNC teg ogohlantirishi OK")


def test_unhandled_operation_warning() -> None:
    """GibLab'da 9 xil operatsiya turi bor; biz CS/EL/XNC ni o'qiymiz. GR/CN/SP kabi
    haqiqiy bosqich import qilinmaydi — texnolog buni bilishi shart. LB (yorliq),
    O (furnitura) va CL (profil kesish — sexda bunday post yo'q) ataylab jim."""

    def build(ops: str) -> bytes:
        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<project version="21052101">'
            '<good typeId="product" id="1" code="42" name="M" count="1">'
            '<part id="1" code="A1" name="bok" dl="700" dw="500" count="1"/>'
            "</good>" + ops + "</project>"
        ).encode()

    def warned(xml: bytes) -> list[str]:
        return [w for w in parse_project(xml).warnings if "operatsiya bor" in w]

    # GR — ogohlantiriladi va turi nomi bilan ataladi
    hit = warned(build('<operation typeId="GR" id="5"><part id="1"/></operation>'))
    assert len(hit) == 1 and "GR" in hit[0] and "paz" in hit[0]

    # LB va O — butunlay jim (yorliqni o'zimiz chiqaramiz, furnitura goodlardan keladi)
    assert warned(build('<operation typeId="LB" id="5"/><operation typeId="O" id="6"/>')) == []

    # CL — "import qilinmaydi" ogohlantirishi CHIQMAYDI, lekin borligi MA'LUMOT sifatida
    # yoziladi: texnolog profillarni ta'minlashi kerak, arrachi esa ularni ko'rmasligi kerak
    cl = build('<operation typeId="CL" id="5" l="3200"><part id="1"/><part id="2"/></operation>')
    assert warned(cl) == []
    info = [w for w in parse_project(cl).warnings if "Profil kesish" in w]
    assert len(info) == 1
    assert "2 detal" in info[0] and "3200" in info[0] and "arrachi" in info[0]

    # Bir necha noma'lum tur — bitta ogohlantirishda jamlanadi
    hit = warned(build('<operation typeId="CN" id="5"/><operation typeId="GR" id="6"/>'))
    assert len(hit) == 1 and "CN" in hit[0] and "GR" in hit[0]
    print("o'qilmagan operatsiya ogohlantirishi OK")


def test_groove_endpoint_default() -> None:
    """Spetsifikatsiya: pazning `x2`/`y2` yozilmasa SHU elementning `x1`/`y1` i olinadi.
    Umumiy "oldingi qiymat" merosi bu yerda ishlamaydi — aks holda ikkinchi paz birinchisining
    oxirigacha cho'zilib, detal kesib yuborilardi."""
    prog = (
        '<program dx="1000" dy="500" dz="16">'
        '<gr x1="100" y1="50" x2="900" y2="50" dp="8" t="4"/>'
        '<gr x1="200" y1="80" dp="8" t="4"/>'
        "</program>"
    )
    a, b = parse_xnc_program("t", prog).grooves
    assert (a["x1"], a["y1"], a["x2"], a["y2"]) == (100.0, 50.0, 900.0, 50.0)
    assert (b["x1"], b["y1"], b["x2"], b["y2"]) == (200.0, 80.0, 200.0, 80.0)
    print("paz oxiri o'z x1/y1 dan olinadi OK")


def test_edge_material_fallback() -> None:
    """Detalda `el{side}Mat` yozilmasligi mumkin (korpusda 779 qirradan 112 tasi) — o'shanda
    lenta nomini EL operatsiyasining bazaviy materialidan olamiz. Kromkalashda `used="base"`
    KLEY emas, LENTA ni bildiradi (spetsifikatsiya), shuning uchun tartib emas, `used` muhim."""
    xml = (
        b'<project version="1">'
        b'<good typeId="band" id="9" name="06-19 SASNA" w="22" t="0.4"/>'
        b'<good typeId="band" id="8" name="KLEY" w="22" t="0.4"/>'
        b'<good typeId="product" id="1" code="42" name="M" count="1">'
        b'<part id="2" code="A1" dl="700" dw="500" count="1" elt="@operation#5" elb="@operation#5" elbMat="QO\'LDA"/>'
        b"</good>"
        b'<operation typeId="EL" id="5" elSymbol="A">'
        b'<material id="8" count="1"/><material id="9" count="1" used="base"/>'
        b"</operation>"
        b"</project>"
    )
    part = next(iter(parse_project(xml).all_parts))
    assert part.edges["t"] == {"mat": "06-19 SASNA", "symbol": "A"}  # bo'sh edi -> lentadan
    assert part.edges["b"] == {"mat": "QO'LDA", "symbol": "A"}  # yozilgani ustun turadi
    print("qirra lentasi zaxira yo'li OK")


def test_giblab_default_kerf_and_trim() -> None:
    """Eski eksportda `tool.cutting` bo'sh, CS da `cTrimL/cTrimW` yo'q. Zaxira qiymatlar
    GibLab standarti bo'lishi kerak (pila 4.4 mm, torsovka 10 mm) — aks holda arrachiga
    GibLab optimallashtirganidan boshqa raqam ko'rsatilardi."""
    xml = (
        b'<project version="21052101">'
        b'<good typeId="tool.cutting" id="2"/>'
        b'<good typeId="sheet" id="3" t="16" name="LDSP"/>'
        b'<good typeId="product" id="1" code="42" name="M" count="1">'
        b'<part id="4" code="A1" dl="700" dw="500" count="1"/>'
        b"</good>"
        b'<operation typeId="CS" id="5" tool1="2"><material id="3" count="1"/><part id="4"/></operation>'
        b"</project>"
    )
    cut = parse_project(xml).cut_ops[0]
    assert (cut.kerf, cut.trim_l, cut.trim_w) == (4.4, 10.0, 10.0)
    print("GibLab standart pila/torsovka qiymatlari OK")


def test_unmapped_material_warning() -> None:
    """Optimallashtirilgan faylda blobsiz kesish operatsiyasi bo'lsa (bir material
    optimallashtirilmagan) detallari arrachiga tushadi, xaritasi esa yo'q. Xarita quruvchi
    uni jimgina o'tkazib yuboradi, shuning uchun materialni nomi bilan aytamiz."""
    blob = make_blob()
    two_cs = (
        f'<operation typeId="CS" id="6" tool1="2" cTrimL="2" cTrimW="2" data="{blob}">'
        '<material id="5" count="2"/><part id="1"/><part id="3"/></operation>'
        '<operation typeId="CS" id="7" tool1="2"><material id="12" count="1"/></operation>'
    )
    xml = make_project_xml(blob).decode()
    xml = xml.replace("</project>", '<good typeId="sheet" id="12" name="XDF 3mm" t="3"/>' + two_cs + "</project>")
    project = parse_project(xml.encode())
    assert project.generation == "processed"
    hits = [w for w in project.warnings if "Kesish xaritasi yo'q" in w]
    assert len(hits) == 1 and "XDF 3mm" in hits[0] and "LDSP OQ GLYANETS" not in hits[0]
    print("xaritasiz material ogohlantirishi OK")


def test_xnc_side_attribute() -> None:
    """Tomonni operatsiyaning `side` atributi belgilaydi (spetsifikatsiya: default true =
    litsevaya, eski eksportda `1`/`0`). Kod suffiksi faqat zaxira: korpusda orqa tomon `x2`
    bilan ham tugaydi, hatto old va orqa dasturning kodi aynan bir xil ham bo'ladi — o'shanda
    ikkalasi bitta SCX nomiga yozilib biri o'chib ketardi."""
    prog = '<program dx="1000" dy="500" dz="16"><tool name="B8" d="8"/><bf x="34" y="70" dp="12" name="B8"/></program>'
    assert parse_xnc_program("A_1", prog, "true").side2 is False
    assert parse_xnc_program("A_1", prog, "1").side2 is False  # eski eksport shakli
    assert parse_xnc_program("A_1", prog, "false").side2 is True  # kod suffiksi yo'q, lekin orqa
    assert parse_xnc_program("0000x006x2", prog, "false").side2 is True
    assert parse_xnc_program("A_2", prog).side2 is True  # `side` yo'q -> zaxira suffiks
    assert parse_xnc_program("A_1", prog).side2 is False

    # Bir xil kodli old+orqa juftlik (korpusdagi 3052_Hikmat holati): SCX nomlari farq qilishi shart
    xml = (
        '<project version="1">'
        '<good typeId="product" id="1" code="42" name="M" count="1">'
        '<part id="2" code="A1" name="bok" dl="1000" dw="500" count="1"/>'
        "</good>"
        f'<operation typeId="XNC" id="7" code="X" side="false" program={quoteattr(prog)}><part id="2"/></operation>'
        f'<operation typeId="XNC" id="8" code="X" side="true" program={quoteattr(prog)}><part id="2"/></operation>'
        "</project>"
    ).encode()
    part = next(iter(parse_project(xml).all_parts))
    assert [scx_filename(part, o) for o in part.xnc_ops] == ["42_A1.scx", "42_A1_2.scx"]
    print("XNC tomoni `side` dan olinadi OK")


def test_geometry_change_warnings() -> None:
    """Geometriyani jimgina o'zgartiradigan ikki holat ogohlantiriladi: butun dasturni
    aylantirish/aks ettirish (`turn`/`mirHor`/`mirVert`) va qirra teshigining qalinlik
    markazidan chetlashishi (`m`/`z` talqini korpusda tekshirilmagan)."""
    prog = '<program dx="1000" dy="500" dz="16"><tool name="B8" d="8"/><bl y="70" z="{z}" dp="34" name="B8"/></program>'

    def build(op_extra: str = "", z: str = "8") -> bytes:
        body = prog.format(z=z)
        return (
            '<project version="1">'
            '<good typeId="product" id="1" code="42" name="M" count="1">'
            '<part id="2" code="A1" name="bok" dl="1000" dw="500" count="1"/>'
            "</good>"
            f'<operation typeId="XNC" id="7" code="X"{op_extra} program={quoteattr(body)}>'
            '<part id="2"/></operation>'
            "</project>"
        ).encode()

    assert [w for w in parse_project(build()).warnings if "XNC" in w] == []  # markazda + burilishsiz

    turned = [w for w in parse_project(build(' turn="1"')).warnings if "aylantirilgan" in w]
    assert len(turned) == 1 and "X" in turned[0]
    assert [w for w in parse_project(build(' mirVert="true"')).warnings if "aks ettirilgan" in w]
    assert [w for w in parse_project(build(' turn="0" mirHor="false"')).warnings if "aylantirilgan" in w] == []

    off = [w for w in parse_project(build(z="12")).warnings if "markazida emas" in w]
    assert len(off) == 1
    print("geometriya o'zgarishi ogohlantirishlari OK")


if __name__ == "__main__":
    test_blob_decoder()
    test_parser_and_routes()
    test_cutmap()
    test_scx()
    test_windows_1251_template()
    test_old_export_without_part_codes()
    test_negative_dimensions()
    test_hardware_goods()
    test_unhandled_operation_warning()
    test_hole_arrays_and_inheritance()
    test_unknown_xnc_tag_warning()
    test_allowance_warning()
    test_size_mode_fallback()
    test_template_machining_warning()
    test_many_xnc_ops_kept()
    test_minus_count_warning()
    test_groove_endpoint_default()
    test_edge_material_fallback()
    test_giblab_default_kerf_and_trim()
    test_unmapped_material_warning()
    test_xnc_side_attribute()
    test_geometry_change_warnings()
    print("ALL GIBLAB TESTS PASSED")
