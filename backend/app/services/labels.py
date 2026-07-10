"""GoDEX EZPL label builder (TZ 5.8.2 / 13.2.2): 80×60 mm thermal label, 203 dpi (8 dots/mm).

Layout mirrors the MES PRO sample label (chek/IMG_4925.JPG) the shop already reads:
header (logo text + order no), big QR right, detail key + product/project, kromka line,
huge "L x W = count", part sketch with banded sides drawn thick, footer material + date.
ponytail: dot offsets tuned for GoDEX G500 defaults — calibrate on the real printer once.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class LabelData:
    qr_text: str  # productCode_partCode_n — unique per copy (TZ 5.8)
    part_code: str  # productCode_partCode (chek: "4202_8")
    part_name: str
    project_name: str
    order_number: str
    material: str  # plita (chek: "ldsp kashmir shagrin")
    length: float | None
    width: float | None
    thickness: float | None
    count: int
    instance_no: int | None
    edges: dict[str, Any]  # side -> {"mat": ..., "symbol": ...}
    xnc_summary: dict[str, Any]
    label_num: int | None
    printed_at: datetime


async def load_label_data(db: "AsyncSession", instance_id: int) -> LabelData | None:
    """Bitta nusxa uchun yorliq ma'lumotini DB'dan yig'adi (print task va PNG endpoint uchun umumiy)."""
    from app.models import Order, Part, PartInstance

    instance = await db.get(PartInstance, instance_id)
    if instance is None:
        return None
    part = await db.get(Part, instance.part_id)
    order = await db.get(Order, instance.order_id)
    if part is None or order is None:
        return None
    return LabelData(
        qr_text=instance.qr_text,
        part_code=instance.qr_text.rsplit("_", 1)[0],
        part_name=part.name,
        project_name=order.project_name or order.number,
        order_number=order.number,
        material=part.material_name or "",
        length=part.length,
        width=part.width,
        thickness=part.thickness,
        count=part.count,
        instance_no=instance.instance_no,
        edges=part.edges,
        xnc_summary=part.xnc_summary,
        label_num=part.label_num,
        printed_at=datetime.now(UTC).astimezone(ZoneInfo("Asia/Tashkent")),
    )


def _edge_mats(edges: dict[str, Any]) -> str:
    """Unique kromka materials, chek style: '19*06 kashmir'."""
    mats: list[str] = []
    for side in ("l", "r", "t", "b"):
        e = edges.get(side)
        mat = str(e.get("mat") or "").strip() if e else ""
        if mat and mat not in mats:
            mats.append(mat)
    return " / ".join(mats)


def build_label_ezpl(d: LabelData) -> str:
    size = ""
    if d.length and d.width:
        size = f"{_n(d.length)} x {_n(d.width)}"
        if d.count:
            size += f" = {d.count}"

    icons = []
    if d.xnc_summary.get("grooves"):
        icons.append("P")  # paz
    if d.xnc_summary.get("bores") or d.xnc_summary.get("edge_bores"):
        icons.append("S")  # teshik
    if d.xnc_summary.get("mills"):
        icons.append("F")  # freza

    kromka = _edge_mats(d.edges)

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
        # --- Header: brand left, order number right, rule under ---
        "AB,16,10,2,2,0,0E,MEBELIX",
        f"AB,300,10,2,2,0,0E,{_esc(d.order_number[:16])}",
        "R16,52,624,55,2,2",
        # --- QR right (scale 6 ~ 30mm) ---
        f"BQ,440,66,2,6,80,0,0,M2,N,'{d.qr_text}'",
        # --- Left column: detail key, product/project, kromka, big size ---
        f"AB,16,66,2,2,0,0E,{_esc(d.part_code[:20])}",
        f"AB,16,116,1,1,0,0E,{_esc(d.part_name[:30])}",
        f"AB,16,148,1,1,0,0E,{_esc(d.project_name[:30])}",
        f"AB,16,180,1,1,0,0E,KROMKA: {_esc(kromka[:24]) if kromka else '-'}",
        f"AB,16,212,3,2,0,0E,{_esc(size)}",
        f"AB,16,264,1,1,0,0E,{' '.join(icons)}",
    ]

    lines += _sketch(d)

    footer = f"{_esc(d.material[:28])}  {d.printed_at.strftime('%d.%m.%Y %H:%M')}"
    n = f"N{d.label_num}" if d.label_num else ""
    copy = f"{d.instance_no}/{d.count}" if d.instance_no else ""
    lines += [
        f"AB,16,446,1,1,0,0E,{footer}",
        f"AB,500,446,1,1,0,0E,{n} {copy}".rstrip(),
        "E",
    ]
    return "\n".join(lines) + "\n"


def _sketch(d: LabelData) -> list[str]:
    """Part outline like the chek: rectangle, banded sides thick, dims alongside."""
    if not (d.length and d.width):
        return []
    bx, by, bw = 16, 292, 300
    long_side, short_side = max(d.length, d.width), min(d.length, d.width)
    bh = max(36, min(120, int(bw * short_side / long_side)))
    t = 8  # banded-side mark thickness
    out = [f"R{bx},{by},{bx + bw},{by + bh},2,2"]
    if d.edges.get("t"):
        out.append(f"R{bx},{by},{bx + bw},{by + t},4,4")
    if d.edges.get("b"):
        out.append(f"R{bx},{by + bh - t},{bx + bw},{by + bh},4,4")
    if d.edges.get("l"):
        out.append(f"R{bx},{by},{bx + t},{by + bh},4,4")
    if d.edges.get("r"):
        out.append(f"R{bx + bw - t},{by},{bx + bw},{by + bh},4,4")
    # dims: length under the box, width to the right (chek: 1900 below, 330 side)
    out.append(f"AB,{bx + bw // 2 - 40},{by + bh + 8},1,1,0,0E,{_n(long_side)}")
    out.append(f"AB,{bx + bw + 12},{by + bh // 2 - 12},1,1,0,0E,{_n(short_side)}")
    return out


def _esc(text: str) -> str:
    return text.replace(",", " ").replace("'", " ")


def _n(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


# --- PNG render (brauzerdan chop etish / ko'rish uchun) ---
# EZPL chiqishini o'zini parslab chizadi — shablon o'zgarsa PNG ham avtomatik mos bo'ladi.

_FONT_CANDIDATES = (
    "C:/Windows/Fonts/consolab.ttf",  # Windows dev
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",  # Debian docker
    "/usr/share/fonts/dejavu/DejaVuSansMono-Bold.ttf",
)


def render_label_png(d: LabelData, scale: int = 2) -> bytes:
    """80×60mm yorliqni PNG qilib qaytaradi (640×480 dot × scale)."""
    import io

    import qrcode
    from PIL import Image, ImageDraw, ImageFont

    def font(mul_y: int) -> Any:
        for path in _FONT_CANDIDATES:
            try:
                return ImageFont.truetype(path, 20 * mul_y * scale)
            except OSError:
                continue
        return ImageFont.load_default()

    img = Image.new("RGB", (640 * scale, 480 * scale), "white")
    draw = ImageDraw.Draw(img)

    for line in build_label_ezpl(d).splitlines():
        if line.startswith("AB,"):
            parts = line.split(",", 7)
            x, y, my, text = int(parts[1]), int(parts[2]), int(parts[4]), parts[7]
            draw.text((x * scale, y * scale), text, fill="black", font=font(my))
        elif line.startswith("R") and line[1].isdigit():
            x1, y1, x2, y2, tx, _ty = (int(v) for v in line[1:].split(","))
            draw.rectangle((x1 * scale, y1 * scale, x2 * scale, y2 * scale), outline="black", width=tx * scale)
        elif line.startswith("BQ,"):
            parts = line.split(",")
            x, y = int(parts[1]), int(parts[2])
            qr = qrcode.make(line.split("'")[1], box_size=6 * scale, border=0)
            img.paste(qr.get_image().convert("RGB").resize((170 * scale, 170 * scale)), (x * scale, y * scale))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
