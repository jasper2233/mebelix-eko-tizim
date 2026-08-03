"""SCX file generation for CNC machines (TZ 5.6).

Konvensiya D:\\MebeliX\\Scx korpusidan keltirilgan (87 proyekt, 10500 qirra
teshigi, 509-ovozlik Face6 transformi): GibLab'ning joriy eksporti bilan
semantik bir xil — sexdagi Nanxing aynan shu formatni yeydi.

- Yuza (Face 5): Y_scx = Width − y_program; X o'zgarmaydi.
- Qirra teshik Face: l→4, r→3, t→1, b→2. l/r: X=0/Length, Y=Width−pos;
  t: X=pos, Y=Width; b: X=pos, Y=0.
- Kromka lenta Face: qirra bilan bir xil (l→4, r→3, t→1, b→2).
- ORQA tomon (_2 dastur) ALOHIDA FAYL EMAS: yuza elementlari Face="6" bilan
  o'sha faylga birlashadi, transform old tomon bilan bir xil (x, Width−y).
- Qo'shqavat detal (dz = 2×plita): eksport qalinligi plita (masalan 32→16),
  qirra Z ham shu masshtabda (16→8) — korpusdagi 1004 Rustam holati.
- Machining'larga ID (1000+ketma-ket) va IsGenCode="2", Panel'ga
  MachiningPoint="1" — eksport namunalaridagi kabi.

Freza (Type 3): GibLab KOMPENSATSIYALANGAN (asbob markazi) yo'lni chiqaradi —
bosh nuqta + <Lines> ichida Line elementlari (Angle=0 to'g'ri chiziq,
Angle=±N — N gradusli yoy). Biz ham xuddi shunday ofset hisoblaymiz:
chiziq perpendikulyar r ga siljiydi, yoy radiusi markaz tomonga ∓r.
# ponytail: tangens-uzluksiz konturlar uchun (GibLab dasturlarida burchaklar
# doim yoy bilan) — keskin burchakli kontur chiqsa join yoyi qo'shilmaydi.
"""

import math
import xml.etree.ElementTree as ET
from xml.dom import minidom

from .models import ParsedPart, XncOp

# Korpus ovozlari (derive_conv): l:3988, r:3730, t:1435, b:1323 — qarshi ovoz <0.5%
_EDGE_BORE_FACE = {"l": "4", "r": "3", "t": "1", "b": "2"}
_EDGE_BAND_FACE = {"l": "4", "r": "3", "t": "1", "b": "2"}


def generate_scx(
    part: ParsedPart,
    ops: list[XncOp],
    panel_id: str | None = None,
    plate_thickness: float | None = None,
) -> str:
    """Bitta detalning BARCHA XNC dasturlarini bitta SCX hujjatga yig'adi.

    panel_id — Nanxing "Сканир" qidiruvi Panel ID bo'yicha ishlaydi: fayllar
    nusxa QR'i bilan nomlanadi (100701_02_003_1) va ID ham shu bo'ladi,
    shunda yorliq skaneri faylni to'g'ridan-to'g'ri topadi (TZ 12.5).
    plate_thickness — plita qalinligi: qo'shqavat detalda (dz ≈ 2×plita)
    eksport qalinligi va qirra Z shu masshtabga tushiriladi.
    """
    front = next((o for o in ops if not o.side2), ops[0])
    length, width, thick = front.dx, front.dy, front.dz
    scale = 1.0
    layer_cut = 0.0  # qo'shqavatda olib tashlangan qatlam qalinligi
    # Qo'shqavat detal: korpus faktlari — dz=32 (2×16 yelimlangan LDSP) 16 va Z/2
    # bo'lib chiqadi (42 fayl, qarshi ovoz 0); 18/26/40 esa o'zgarmaydi.
    # Yuza teshik chuqurligi ham bir qatlamga kamayadi (masalan 35 → 19).
    if (plate_thickness and abs(thick - 2 * plate_thickness) < 0.1) or abs(thick - 32.0) < 0.1:
        layer_cut = thick / 2
        thick /= 2
        scale = 0.5

    root = ET.Element("Root", {"Cad": "Built in GibLab", "version": "2.0"})
    panels = ET.SubElement(ET.SubElement(root, "Project"), "Panels")
    panel = ET.SubElement(
        panels,
        "Panel",
        {
            "ID": panel_id or front.code or part.key,
            "Length": _n(length),
            "Width": _n(width),
            "Thickness": _n(thick),
            "Name": part.name,
            "IsProduce": "true",
            "MachiningPoint": "1",
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
                    {
                        "Face": _EDGE_BAND_FACE[side],
                        "Thickness": "1.0",
                        "CentralAngle": "0",
                        "Pre_Milling": "1.0",
                        "X": "0",
                        "Y": "0",
                    },
                )

    machines = ET.SubElement(panel, "Machines")
    # Eksport namunasidagi kabi har Machining'ga ketma-ket ID (1000, 1001, ...)
    next_id = 1000

    def _mach(attrs: dict[str, str]) -> ET.Element:
        nonlocal next_id
        attrs = {**attrs, "ID": str(next_id), "IsGenCode": "2"}
        next_id += 1
        return ET.SubElement(machines, "Machining", attrs)

    for op in ops:
        surface_face = "6" if op.side2 else "5"

        for b in op.edge_bores:
            side = b["side"]
            if side in ("l", "r"):
                x = 0.0 if side == "l" else length
                y = width - b["pos"]  # Y_scx = Width − y_program
            else:
                x = b["pos"]
                # t (program y=0 cheti) flip'dan keyin Y=Width chetiga tushadi, b — Y=0
                y = width if side == "t" else 0.0
            z = b["z"] * scale
            if op.side2:
                z = thick - z  # orqa dasturda Z orqa yuzadan o'lchanadi
            _mach(
                {
                    "Face": _EDGE_BORE_FACE[side],
                    "Type": "1",
                    "Diameter": _n(b["d"]),
                    "Depth": _n(b["dp"]),
                    "X": _n(x),
                    "Y": _n(y),
                    "Z": _n(z),
                }
            )

        for b in op.bores:
            dp = b["dp"]
            if layer_cut and dp > layer_cut:
                dp -= layer_cut
            _mach(
                {
                    "Face": surface_face,
                    "Type": "2",
                    "Diameter": _n(b["d"]),
                    "Depth": _n(dp),
                    "X": _n(b["x"]),
                    "Y": _n(width - b["y"]),
                }
            )

        for g in op.grooves:
            _mach(
                {
                    "Face": surface_face,
                    "Type": "4",
                    "X": _n(g["x1"]),
                    "Y": _n(width - g["y1"]),
                    "Z": _n(thick),
                    "EndX": _n(g["x2"]),
                    "EndY": _n(width - g["y2"]),
                    "EndZ": _n(thick),
                    "Width": _n(g["t"]),
                    "Depth": _n(g["dp"]),
                    "ToolOffset": "中",
                }
            )

        for contour in op.mills:
            if not contour:
                continue
            head = contour[0]
            radius = float(head.get("d") or 0) / 2
            comp = str(head.get("c") or "0")
            dp = float(head.get("dp") or thick)
            if layer_cut:
                dp = min(dp, thick)  # qo'shqavatda freza ham bitta qatlam
            pts = [(s["x"], s["y"]) for s in contour if "x" in s]
            on_border = (
                all(abs(x) < 0.05 for x, _ in pts)
                or all(abs(x - length) < 0.05 for x, _ in pts)
                or all(abs(y) < 0.05 for _, y in pts)
                or all(abs(y - width) < 0.05 for _, y in pts)
            )
            if comp == "0":
                # Kompensatsiyasiz dastur — yo'l xom, stanokka ham buyruq yo'q
                hx, hy = head["x"], width - head["y"]
                segments = _raw_segments(contour, width)
                tool_offset = "中"
            elif on_border and comp == "2":
                # Panel cheti bo'ylab tirim: xom yo'l, tomonini stanok oladi
                hx, hy = head["x"], width - head["y"]
                segments = _raw_segments(contour, width)
                tool_offset = "右"
            else:
                # Korpus jadvali: c='2' -> harakatga CHAP, c='1' -> O'NG ofset, 中
                hx, hy, segments = _offset_contour(contour, width, radius, comp)
                tool_offset = "中"
            mill = _mach(
                {
                    "Face": surface_face,
                    "Type": "3",
                    "Diameter": _n(radius * 2),
                    "Depth": _n(dp),
                    "X": _n(hx),
                    "Y": _n(hy),
                    "Closed": "0",
                    "Pocket": "0",
                    "ToolOffset": tool_offset,
                }
            )
            lines = ET.SubElement(mill, "Lines")
            for i, (ex, ey, angle) in enumerate(segments):
                ET.SubElement(
                    lines,
                    "Line",
                    {"Angle": _n(angle), "EndX": _n(ex), "EndY": _n(ey), "LineID": str(i)},
                )

    xml_bytes = ET.tostring(root, encoding="unicode")
    return (
        minidom.parseString(xml_bytes)
        .toprettyxml(indent="  ", encoding=None)
        .replace('<?xml version="1.0" ?>', '<?xml version="1.0" encoding="UTF-8"?>')
    )


def build_scx_files(
    part: ParsedPart,
    qr_texts: list[str],
    plate_thickness: float | None = None,
) -> list[tuple[str, str, dict]]:
    """Bitta detalning SCX fayllari: (filename, content, meta) ro'yxati.

    HAR NUSXAGA bitta to'liq fayl (old + orqa Face=6 birlashgan), nomi va
    Panel ID = nusxa QR'i (100701_02_003_1.scx) — Nanxing skaneri yorliqdagi
    QR bilan faylni to'g'ridan-to'g'ri topadi. GibLab eksporti kabi alohida
    orqa (_2) fayl YO'Q.
    """
    if not part.xnc_ops:
        return []
    out: list[tuple[str, str, dict]] = []
    codes = [op.code for op in part.xnc_ops]
    for qr in qr_texts:
        content = generate_scx(part, part.xnc_ops, panel_id=qr, plate_thickness=plate_thickness)
        out.append((f"{qr}.scx", content, {"codes": codes, "qr": qr}))
    return out


def _raw_segments(contour: list[dict], width: float) -> list[tuple[float, float, float]]:
    """Kompensatsiyasiz yo'l — eksport tekisligida (x, Width−y), yoy sweep bilan."""
    out: list[tuple[float, float, float]] = []
    prev = (contour[0]["x"], width - contour[0]["y"])
    for seg in contour[1:]:
        pt = (seg["x"], width - seg["y"])
        if seg["op"] == "mac":
            cx, cy = seg["cx"], width - seg["cy"]
            ccw = not bool(seg["dir"])
            th0 = math.atan2(prev[1] - cy, prev[0] - cx)
            th1 = math.atan2(pt[1] - cy, pt[0] - cx)
            sweep = th1 - th0
            if ccw and sweep < 0:
                sweep += 2 * math.pi
            if not ccw and sweep > 0:
                sweep -= 2 * math.pi
            out.append((pt[0], pt[1], -math.degrees(sweep)))
        else:
            out.append((pt[0], pt[1], 0.0))
        prev = pt
    return out


def _offset_contour(
    contour: list[dict], width: float, radius: float, comp: str
) -> tuple[float, float, list[tuple[float, float, float]]]:
    """Asbob-markazi (kompensatsiyalangan) yo'l — GibLab eksporti bilan bir xil.

    Eksport tekisligida ishlaymiz (x, Y=Width−y; yoy yo'nalishi shunda teskari).
    Korpus jadvali (218 freza): c='2' — harakat yo'nalishiga CHAPGA r siljish,
    c='1' — O'NGGA. Chiziq segmenti parallel siljiydi, yoy radiusi markaz chap
    tomonida bo'lsa (CCW) R−r, aks holda R+r. Qaytish: (bosh X, bosh Y,
    [(EndX, EndY, Angle°)...]), Angle=0 — to'g'ri chiziq, aks holda yoy
    sweep'i (CCW manfiy — korpus).
    """
    # eksport tekisligiga o'tkazish
    pts: list[tuple[float, float]] = []
    segs: list[dict] = []  # har biri pts[i] -> pts[i+1] orasidagi segment
    for seg in contour:
        pts.append((seg["x"], width - seg["y"]))
        if seg is not contour[0]:
            segs.append(seg)

    sign = 1.0 if comp == "2" else -1.0  # chap normal koeffitsienti

    def left_normal(dx: float, dy: float) -> tuple[float, float]:
        ln = math.hypot(dx, dy) or 1.0
        return (-dy / ln, dx / ln)

    out_pts: list[tuple[float, float]] = [(0.0, 0.0)] * len(pts)
    angles: list[float] = []
    for i, seg in enumerate(segs):
        p0, p1 = pts[i], pts[i + 1]
        if seg["op"] == "mac":
            cx, cy = seg["cx"], width - seg["cy"]
            # dasturdagi dir Y-aks o'girilganda teskarilanadi
            ccw = not bool(seg["dir"])
            big_r = math.hypot(p0[0] - cx, p0[1] - cy) or 1.0
            # CCW yoyda markaz harakatning chap tomonida: chap ofset = ichkariga
            new_r = big_r - sign * radius if ccw else big_r + sign * radius
            k = new_r / big_r
            a0 = (cx + (p0[0] - cx) * k, cy + (p0[1] - cy) * k)
            a1 = (cx + (p1[0] - cx) * k, cy + (p1[1] - cy) * k)
            out_pts[i] = a0
            out_pts[i + 1] = a1
            th0 = math.atan2(p0[1] - cy, p0[0] - cx)
            th1 = math.atan2(p1[1] - cy, p1[0] - cx)
            sweep = th1 - th0
            if ccw and sweep < 0:
                sweep += 2 * math.pi
            if not ccw and sweep > 0:
                sweep -= 2 * math.pi
            # korpus belgisi: CCW sweep manfiy Angle bilan yoziladi
            angles.append(-math.degrees(sweep))
        else:
            nx, ny = left_normal(p1[0] - p0[0], p1[1] - p0[1])
            off = (sign * radius * nx, sign * radius * ny)
            out_pts[i] = (p0[0] + off[0], p0[1] + off[1])
            out_pts[i + 1] = (p1[0] + off[0], p1[1] + off[1])
            angles.append(0.0)

    head = out_pts[0]
    return head[0], head[1], [(out_pts[i + 1][0], out_pts[i + 1][1], angles[i]) for i in range(len(segs))]


def _n(value: float | int) -> str:
    f = float(value)
    return str(int(f)) if f.is_integer() else f"{f:g}"
