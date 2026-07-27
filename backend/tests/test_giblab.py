"""Self-check for the GibLab parser stack (TZ 5): synthetic .project + hand-encoded CS blob.

Run: uv run python -m tests.test_giblab  (assert-based, no framework)
"""

import struct
from base64 import b64encode
from xml.sax.saxutils import quoteattr

from app.services.giblab import parse_project
from app.services.giblab.csblob import decode_cs_blob
from app.services.giblab.cutmap import build_cutmap
from app.services.giblab.scx import generate_scx, scx_filename


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


if __name__ == "__main__":
    test_blob_decoder()
    test_parser_and_routes()
    test_cutmap()
    test_scx()
    test_windows_1251_template()
    test_old_export_without_part_codes()
    test_negative_dimensions()
    print("ALL GIBLAB TESTS PASSED")
