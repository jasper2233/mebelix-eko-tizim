"""SCX file generation for CNC machines (TZ 5.6).

The critical, corpus-proven transform: Y_scx = Panel.Width − y_program; X is unchanged.
Verified against GibLab 2.0 output; re-verify if GibLab ships a new version (TZ 5.6.3).
One SCX per XNC operation — a part machined on both sides (`_2`) gets two files (TZ 5.6.5).
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom

from .models import ParsedPart, XncOp

# ponytail: Machining/Edge Face codes — bl→4 and bf→5/ms→5 are corpus-confirmed (TZ 5.6.1/B);
# bt/bb/br and edge-group codes follow the same clockwise convention; calibrate on the real
# machine software if a station rejects a face.
_EDGE_BORE_FACE = {"l": "4", "r": "2", "t": "1", "b": "3"}
_EDGE_BAND_FACE = {"l": "1", "r": "2", "t": "3", "b": "4"}


def generate_scx(part: ParsedPart, op: XncOp) -> str:
    """Build one SCX document for one XNC operation of one part."""
    length, width, thick = op.dx, op.dy, op.dz

    root = ET.Element("Root", {"Cad": "Built in GibLab", "version": "2.0"})
    panels = ET.SubElement(ET.SubElement(root, "Project"), "Panels")
    panel = ET.SubElement(
        panels,
        "Panel",
        {
            "ID": op.code or part.key,
            "Length": _n(length),
            "Width": _n(width),
            "Thickness": _n(thick),
            "Name": part.name,
            "IsProduce": "true",
        },
    )

    outline = ET.SubElement(panel, "Outline")
    for px, py in ((length, 0), (length, width), (0, width), (0, 0)):
        ET.SubElement(outline, "Point", {"X": _n(px), "Y": _n(py)})

    if part.edges:
        group = ET.SubElement(panel, "EdgeGroup")
        for side in ("l", "r", "t", "b"):
            if side in part.edges:
                ET.SubElement(
                    group,
                    "Edge",
                    {"Face": _EDGE_BAND_FACE[side], "Thickness": "1.0", "CentralAngle": "0"},
                )

    machines = ET.SubElement(panel, "Machines")

    for b in op.edge_bores:
        side = b["side"]
        if side in ("l", "r"):
            x = 0.0 if side == "l" else length
            y = width - b["pos"]  # Y_scx = Width − y_program
        else:
            x = b["pos"]
            y = 0.0 if side == "t" else width  # program top edge maps to Y_scx = 0 after the flip
        ET.SubElement(
            machines,
            "Machining",
            {
                "Face": _EDGE_BORE_FACE[side],
                "Type": "1",
                "Diameter": _n(b["d"]),
                "Depth": _n(b["dp"]),
                "X": _n(x),
                "Y": _n(y),
                "Z": _n(b["z"]),
            },
        )

    for b in op.bores:
        ET.SubElement(
            machines,
            "Machining",
            {
                "Face": "5",
                "Type": "2",
                "Diameter": _n(b["d"]),
                "Depth": _n(b["dp"]),
                "X": _n(b["x"]),
                "Y": _n(width - b["y"]),
            },
        )

    for g in op.grooves:
        ET.SubElement(
            machines,
            "Machining",
            {
                "Face": "5",
                "Type": "4",
                "X": _n(g["x1"]),
                "Y": _n(width - g["y1"]),
                "EndX": _n(g["x2"]),
                "EndY": _n(width - g["y2"]),
                "Width": _n(g["t"]),
                "Depth": _n(g["dp"]),
            },
        )

    for contour in op.mills:
        if not contour:
            continue
        head = contour[0]
        mill = ET.SubElement(
            machines,
            "Machining",
            {
                "Face": "5",
                "Type": "3",
                "Diameter": _n(head.get("d") or 0),
                "Depth": _n(head.get("dp") or thick),
                "X": _n(head["x"]),
                "Y": _n(width - head["y"]),
            },
        )
        for seg in contour[1:]:
            attrs = {"X": _n(seg["x"]), "Y": _n(width - seg["y"])}
            if seg["op"] == "mac":
                attrs.update(
                    {"CenterX": _n(seg["cx"]), "CenterY": _n(width - seg["cy"]), "Dir": str(seg["dir"]).lower()}
                )
                ET.SubElement(mill, "Arc", attrs)
            else:
                ET.SubElement(mill, "Line", attrs)

    xml_bytes = ET.tostring(root, encoding="unicode")
    return (
        minidom.parseString(xml_bytes)
        .toprettyxml(indent="  ", encoding=None)
        .replace('<?xml version="1.0" ?>', '<?xml version="1.0" encoding="UTF-8"?>')
    )


def scx_filename(part: ParsedPart, op: XncOp) -> str:
    """{productCode}_{partCode}.scx; the second side gets the _2 suffix (TZ 5.6.5)."""
    suffix = "_2" if op.side2 else ""
    return f"{part.product_code}_{part.code}{suffix}.scx"


def _n(value: float | int) -> str:
    f = float(value)
    return str(int(f)) if f.is_integer() else f"{f:g}"
