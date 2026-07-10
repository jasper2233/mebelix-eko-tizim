"""GoDEX EZPL label builder (TZ 5.8.2 / 13.2.2): 80×60 mm thermal label, 203 dpi (8 dots/mm).

Layout per Appendix C: QR top-left (~25 mm), text block right (code big, name, project,
material, size), edge-banding row for 4 sides + tech icons (P/S/F), footer date + №num.
ponytail: dot offsets tuned for GoDEX G500 defaults — calibrate on the real printer once.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class LabelData:
    qr_text: str  # productCode_partCode_n — unique per copy (TZ 5.8)
    part_code: str
    part_name: str
    project_name: str
    material: str
    length: float | None
    width: float | None
    thickness: float | None
    edges: dict[str, Any]  # side -> {"mat": ..., "symbol": ...}
    xnc_summary: dict[str, Any]
    label_num: int | None
    printed_at: datetime


def _edge_text(edges: dict[str, Any], side: str) -> str:
    e = edges.get(side)
    if not e:
        return "-"
    mat = str(e.get("mat") or "")
    # shorten '06-19 SASNA' -> '06-19'
    return mat.split()[0] if mat else "KE"


def build_label_ezpl(d: LabelData) -> str:
    size = ""
    if d.length and d.width:
        size = f"{_n(d.length)} x {_n(d.width)}"
        if d.thickness:
            size += f" x {_n(d.thickness)}"
        size += " mm"

    icons = []
    if d.xnc_summary.get("grooves"):
        icons.append("P")  # paz
    if d.xnc_summary.get("bores") or d.xnc_summary.get("edge_bores"):
        icons.append("S")  # teshik
    if d.xnc_summary.get("mills"):
        icons.append("F")  # freza
    edge_row = (
        f"Ch:{_edge_text(d.edges, 'l')}  O'ng:{_edge_text(d.edges, 'r')}  "
        f"Yuq:{_edge_text(d.edges, 't')}  Past:{_edge_text(d.edges, 'b')}  {' '.join(icons)}"
    )

    lines = [
        "^Q60,3",  # label height 60mm, gap 3mm
        "^W80",  # width 80mm
        "^H10",  # darkness
        "^P1",  # copies (one label per copy — on-demand printing, TZ 7.1.4)
        "^S2",  # speed
        "^AD",
        "^C1",
        "^R0",
        "~Q+0",
        "^O0",
        "^D0",
        "^E12",
        "~R255",
        "^XSET,ROTATION,0",
        "^L",
        f"Dy{d.printed_at.strftime('%y-%m-%d')}",
        f"T{d.printed_at.strftime('%H:%M:%S')}",
        # QR top-left: cell version auto, scale 5 (~25mm at 203dpi)
        f"BQ,16,16,2,5,80,0,0,M2,N,'{d.qr_text}'",
        # Text block right of QR (x=240 dots = 30mm)
        f"AB,240,20,2,2,0,0E,{_esc(d.part_code)}",
        f"AB,240,80,1,1,0,0E,{_esc(d.part_name[:28])}",
        f"AB,240,120,1,1,0,0E,{_esc(d.project_name[:28])}",
        f"AB,240,160,1,1,0,0E,{_esc(d.material[:24])}",
        f"AB,240,200,1,1,0,0E,{_esc(size)}",
        # Edge banding row (below QR)
        f"AB,16,250,1,1,0,0E,{_esc(edge_row[:46])}",
        # Footer: printed at + label number
        f"AB,16,420,1,1,0,0E,{d.printed_at.strftime('%d.%m.%Y %H:%M')}   N{d.label_num or ''}",
        "E",
    ]
    return "\n".join(lines) + "\n"


def _esc(text: str) -> str:
    return text.replace(",", " ").replace("'", " ")


def _n(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"
