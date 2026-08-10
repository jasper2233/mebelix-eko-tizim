"""Yorliq renderi (TZ 5.8.2 / 13.2.2): 80×60 mm termal yorliq, 203 dpi (8 dot/mm).

render_label_png PNG chizadi — bridge-agent uni USB GoDEX'ga Windows drayveri (GDI)
orqali chiqaradi. Maket MES PRO chekiga (chek/IMG_4925.JPG) va GibSaw shablonlariga
asoslangan. EZPL yo'q: G500-U'da tarmoq porti yo'q, RAW dialekt kerak emas.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.core.config import TASHKENT_TZ

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class LabelData:
    qr_text: str  # productCode_partCode[_n] — `_n` only when count > 1 (TZ 5.8)
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
    # Haqiqiy teshiklar (cutmap'dan): {"l","w","bores":[{x,y,d,thru}],"edge":[{side,pos,d,dp}]}
    holes: dict[str, Any] | None = None
    texture: bool = False  # tekstura yo'nalishi qulflangan (uzunlik bo'ylab)
    #: Marshrut jarayon kodlari tartib bilan ("7/11/8"). Detal NOMIGA qo'shilmaydi —
    #: nom 24 belgida kesiladi va marshrut jimgina yo'qolardi.
    route_codes: list[int] = field(default_factory=list)


async def load_label_data(db: "AsyncSession", instance_id: int) -> LabelData | None:
    """Bitta nusxa uchun yorliq ma'lumotini DB'dan yig'adi (print task va PNG endpoint uchun umumiy)."""
    from sqlalchemy import select

    from app.models import Order, Part, PartInstance, PartRoute
    from app.services.scanning import qr_part_code

    instance = await db.get(PartInstance, instance_id)
    if instance is None:
        return None
    part = await db.get(Part, instance.part_id)
    order = await db.get(Order, instance.order_id)
    if part is None or order is None:
        return None

    # Cutmap'dan shu detal teshiklari: label_num -> file_part_id -> holes.
    # Birinchi mos katak yetarli: katakdagi `id` va `num` bitta part'dan keladi
    # (cutmap.py `part.file_part_id` / `part.label_num`), ya'ni bir xil `num` li
    # barcha kataklar bir xil `id` ga ega — boshqa varaqda qidirish natijani o'zgartirmaydi.
    holes = None
    if order.cutmap and part.label_num is not None:
        cell = next(
            (
                c
                for mat in order.cutmap.get("materials", [])
                for sheet in mat.get("sheets", [])
                for c in sheet.get("parts", [])
                if not c.get("waste") and c.get("num") == part.label_num
            ),
            None,
        )
        if cell:
            holes = order.cutmap.get("holes", {}).get(str(cell.get("id")))

    route_codes = list(
        (
            await db.execute(
                select(PartRoute.process_code)
                .where(
                    PartRoute.part_id == part.id,
                    PartRoute.is_enabled == True,  # noqa: E712
                    PartRoute.is_deleted == False,  # noqa: E712
                )
                .order_by(PartRoute.seq)
            )
        )
        .scalars()
        .all()
    )

    return LabelData(
        route_codes=route_codes,
        qr_text=instance.qr_text,
        part_code=qr_part_code(instance.qr_text, part.count),
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
        printed_at=datetime.now(UTC).astimezone(TASHKENT_TZ),
        holes=holes,
        texture=part.txt,
    )


def _n(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


_BW_THRESHOLD = 160  # chek pechati qoraligi — GoDEX uchun sozlanadigan yagona nuqta


def _bw(v: int) -> int:
    """Image.point uchun binarizatsiya: har piksel sof qora yoki oq."""
    return 0 if v < _BW_THRESHOLD else 255


# --- PNG render: GibSaw shablonlari asosidagi maket (80x60mm), mm-koordinatalarda ---
# Manba ikkita: Universal.lbl (kromka konturdan tashqarida, QR/eskiz joylashuvi, logo) va
# mebelix.lbl (ustunlar tartibi, index_name "12_bok"). Har joyda qaysi biridan olingani yozilgan.
# GDI chop etish (bridge-agent PRINTER_NAME rejimi) va brauzer ko'rinishi uchun
# yagona manba. QR kutubxona bilan chiziladi — printer dialektiga bog'liq emas.

# Liberation Sans — Arial bilan metrik mos (harf kengliklari bir xil), shuning
# uchun Windowsda sozlangan maket serverda ham aynan shunday joylashadi.
# DejaVu kengroq: zaxira sifatida qoladi, chunki maketni siljitadi.
_FONT_REGULAR = (
    "C:/Windows/Fonts/arial.ttf",  # Windows dev
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",  # Debian docker
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
)
_FONT_BOLD = (
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
)


def render_label_png(d: LabelData, scale: int = 1) -> bytes:  # noqa: C901 — chiziqli layout kodi
    """80x60mm yorliq PNG (203 dpi: 8 dot/mm -> 640x480 px).

    Ustunlar tartibi mebelix.lbl bo'yicha: chap ustun — matnlar, o'ng ustun —
    QR (tepada) va detal eskizi vertikal (ostida). 1-bit, antialiasing'siz.
    """
    import io as _io
    from pathlib import Path

    import qrcode
    from PIL import Image, ImageDraw, ImageFont

    mm = 8 * scale  # px per mm
    W, H = 80 * mm, 60 * mm
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    # Termoprinter 1-bit: antialiasing o'chiriladi, aks holda drayver dither qiladi
    draw.fontmode = "1"

    def font(size_mm: float, bold: bool = False) -> Any:
        for path in _FONT_BOLD if bold else _FONT_REGULAR:
            try:
                return ImageFont.truetype(path, int(size_mm * mm))
            except OSError:
                continue
        return ImageFont.load_default()

    def text(x: float, y: float, t: str, size_mm: float, bold: bool = False, anchor: str = "la") -> None:
        draw.text((x * mm, y * mm), t, fill="black", font=font(size_mm, bold), anchor=anchor)

    def edge_mat(side: str) -> str:
        e = d.edges.get(side)
        return str(e.get("mat") or "").strip()[:16] if e else ""

    # ============ CHAP USTUN (x 5..52) ============
    # Logo — Universal.lbl dan ajratilgan, threshold qilingan
    logo_path = Path(__file__).resolve().parents[1] / "assets" / "label-logo.png"
    try:
        logo = Image.open(logo_path).convert("L").point(_bw).convert("RGB")
        lw = 22 * mm
        lh = int(lw * logo.height / logo.width)
        img.paste(logo.resize((lw, lh)), (3 * mm, int(1 * mm)))
    except OSError:
        text(5, 1, "MEBELIX", 4, bold=True)

    product_code = d.part_code.split("_", 1)[0]
    text(26, 1.5, "Formatka", 2.8)
    text(26, 4.8, product_code[:7], 3.7, bold=True)
    # To'liq nusxa ID (= QR matni = SCX fayl nomi): prisadkachi chekdagi yozuv
    # bilan stanokdagi faylni bevosita solishtira oladi
    text(5, 9.5, d.qr_text[:20], 2.7)

    # Loyiha (limit 26: kattaroq shriftda eskiz chizig'iga yetmasin)
    text(5, 13.5, d.project_name[:26], 3.3, bold=True)

    # Kromka 2x2 (tagchiziq bilan): chapda uzunlik tomonlari (t/b), o'ngda en (l/r)
    def edge_cell(x: float, y: float, mat: str) -> None:
        if not mat:
            return
        text(x, y, mat[:14], 2.9, bold=True)
        draw.line(
            (int(x * mm), int((y + 3.4) * mm), int((x + 22) * mm), int((y + 3.4) * mm)),
            fill="black",
            width=max(2, scale),
        )

    edge_cell(5, 19, edge_mat("t"))
    edge_cell(29, 19, edge_mat("l"))
    edge_cell(5, 30, edge_mat("b"))
    edge_cell(29, 30, edge_mat("r"))

    # Katta o'lcham markazda (kromka qatorlari orasida): "1900 x 330 = 4"
    if d.length and d.width:
        size = f"{_n(d.length)} x {_n(d.width)}"
        if d.count:
            size += f" = {d.count}"
        text(28, 24, size, 4.6, bold=True, anchor="ma")

    # N_detal nomi (mebelix.lbl index_name): 12_bok
    label_name = f"{d.label_num}_{d.part_name}" if d.label_num else d.part_name
    text(5, 36.5, label_name[:24], 3.3, bold=True)

    # Paz (П) va freza (Ф) belgilari olib tashlandi: ikkalasi ham marshrutga ta'sir
    # qilmaydi (ROVER bosqichi fayldan avtomatik yaratilmaydi), ya'ni operatorga
    # hech qanday ish ko'rsatmasdi. Teshik esa PRISADKA bosqichini beradi —
    # sverlo ikonkasi qoladi.
    if d.xnc_summary.get("bores") or d.xnc_summary.get("edge_bores"):
        # Sverlo ikonkasi zakaz ID ("Formatka 305201") tagida — detal kodi (~x27
        # gacha), loyiha (y13.5+) va QR (x40+) oralig'idagi bo'sh joyda
        drill_path = Path(__file__).resolve().parents[1] / "assets" / "label-icon-drill.png"
        isz = int(4 * mm)  # zakaz ID (past ~8.9) va loyiha qatori (13.5) orasiga sig'adi
        try:
            raw = Image.open(drill_path)
            flat = Image.new("RGB", raw.size, "white")
            flat.paste(raw, mask=raw.getchannel("A") if "A" in raw.getbands() else None)
            icon = flat.convert("L").point(_bw).convert("RGB").resize((isz, isz))
            img.paste(icon, (int(35 * mm), int(9.4 * mm)))
        except OSError:
            text(35, 9.4, "С", 3.2, bold=True)

    # Marshrut — ALOHIDA qator (nomga qo'shilsa 24 belgi kesimida yo'qolardi).
    # Kodlar sexning "Jarayon uchun kodlar" jadvalidagi raqamlar.
    if d.route_codes:
        text(5, 41.5, "Marshrut: " + "/".join(str(c) for c in d.route_codes), 2.9, bold=True)

    # Material pastda; oxirgi qator BITTA: chapda N/nusxa, o'ngda sana-vaqt.
    # Ikki qator paytida oxirgisi (y 56.2 + 2.9 ≈ 59mm) yorliq pastki chetiga
    # tushib, termal printerda yeyilardi — endi 55.7mm da tugaydi (4mm zaxira)
    text(5, 49, d.material[:24], 2.9, bold=True)
    n = f"N{d.label_num}" if d.label_num else ""
    copy = f"{d.instance_no}/{d.count}" if d.instance_no else ""
    tail = f"{n} {copy}".strip()
    if tail:
        text(5, 52.8, tail, 2.9, bold=True)
    text(52, 53.2, d.printed_at.strftime("%Y.%m.%d %H:%M"), 2.5, anchor="ra")

    # ============ O'NG USTUN (x 56..78) ============
    # QR tepada — to'liq nusxa kodi (skan oqimi)
    qr = qrcode.make(d.qr_text, box_size=max(1, scale * 2), border=0)
    qr_px = 16 * mm
    img.paste(qr.get_image().convert("RGB").resize((qr_px, qr_px)), (40 * mm, 1 * mm))

    # Detal eskizi vertikal — Universal.lbl <part> uslubi: ingichka kontur,
    # kromka konturdan 1mm TASHQARIDA qalin chiziq + tomon belgisi; o'lchamlar
    # pastda (en) va o'ng tomonda aylantirilgan (uzunlik)
    if d.length and d.width:
        long_side, short_side = max(d.length, d.width), min(d.length, d.width)
        off = int(1 * mm)  # edgeband.offset=1mm
        bt = max(2, int(0.6 * mm))  # kromka chizig'i qalinligi
        # QR'dan keyin (kromka chizig'i ham QR'ga tegmasin — quiet zone)
        area_x, area_y = int(58.5 * mm), 3 * mm
        area_w, area_h = 15 * mm, 46 * mm
        bh = area_h
        bw = max(5 * mm, int(bh * short_side / long_side))
        if bw > area_w:
            bw = area_w
            bh = min(area_h, int(bw * long_side / short_side))
        bx = area_x + (area_w - bw) // 2
        by = area_y
        # kamida 2px kontur: GDI kichraytirishda 1px chiziq yo'qolishi mumkin
        draw.rectangle((bx, by, bx + bw, by + bh), outline="black", width=max(2, scale))

        def edge_sym(side: str) -> str:
            e = d.edges.get(side)
            return str(e.get("symbol") or "").strip()[:3] if e else ""

        # 90 gradus burilgan eskiz: t -> chap, b -> o'ng, l -> tepa, r -> past
        if d.edges.get("t"):
            draw.rectangle((bx - off - bt, by, bx - off, by + bh), fill="black")
        if d.edges.get("b"):
            draw.rectangle((bx + bw + off, by, bx + bw + off + bt, by + bh), fill="black")
        if d.edges.get("l"):
            draw.rectangle((bx, by - off - bt, bx + bw, by - off), fill="black")
        if d.edges.get("r"):
            draw.rectangle((bx, by + bh + off, bx + bw, by + bh + off + bt), fill="black")

        # Tekstura yo'nalishi (xaritadagidek): uzunlik bo'ylab 3 ingichka chiziq —
        # eskizda vertikal. Teshiklardan oldin chiziladi (teshik ustida qolsin)
        if d.texture:
            tl = int(bh * 0.32)
            gap = max(3, bw // 4)
            # kamida 2px: GDI kichraytirishda 1px vertikal chiziq yo'qolib qoladi
            for xx in (bx + bw // 2 - gap, bx + bw // 2, bx + bw // 2 + gap):
                draw.line((xx, by + (bh - tl) // 2, xx, by + (bh + tl) // 2), fill="black", width=max(2, scale))

        # Haqiqiy sverlo o'rinlari (GibSaw'da yo'q — bizda cutmap'dan bor):
        # lokal (x bo'ylab uzunlik, y bo'ylab en) -> vertikal eskiz koordinatalari
        if d.holes and d.holes.get("l") and d.holes.get("w"):
            hl, hw = float(d.holes["l"]), float(d.holes["w"])
            kx, ky = bw / hw, bh / hl  # en -> gorizontal, uzunlik -> vertikal
            for b in d.holes.get("bores", []):
                cxp = bx + int(float(b["y"]) * kx)
                cyp = by + int(float(b["x"]) * ky)
                r = max(int(0.4 * mm), int(float(b.get("d", 5)) / 2 * min(kx, ky)))
                draw.ellipse((cxp - r, cyp - r, cxp + r, cyp + r), fill="white", outline="black", width=max(2, scale))
            for b in d.holes.get("edge", []):
                side, pos = b.get("side"), float(b.get("pos", 0))
                dp = min(float(b.get("dp", 12)), 30) * min(kx, ky)
                tick = max(2, int(dp))
                if side == "t":  # y=0 en chizig'i -> eskizda chap qirra
                    yy = by + int(pos * ky)
                    draw.line((bx, yy, bx + tick, yy), fill="black", width=2)
                elif side == "b":
                    yy = by + int(pos * ky)
                    draw.line((bx + bw - tick, yy, bx + bw, yy), fill="black", width=2)
                elif side == "l":  # x=0 uzunlik boshi -> eskizda tepa qirra
                    xx = bx + int(pos * kx)
                    draw.line((xx, by, xx, by + tick), fill="black", width=2)
                elif side == "r":
                    xx = bx + int(pos * kx)
                    draw.line((xx, by + bh - tick, xx, by + bh), fill="black", width=2)

        # O'lchamlar: en pastda gorizontal, uzunlik o'ngda aylantirilgan (Universal size.top/left=false).
        # Har o'lcham yoniga o'sha tomonlar kromka belgilari (xaritadagi "450 B" uslubi):
        # uzunlik <- t/b tomonlar, en <- l/r tomonlar
        sym_long = "".join(s for s in (edge_sym("t"), edge_sym("b")) if s)
        sym_short = "".join(s for s in (edge_sym("l"), edge_sym("r")) if s)
        draw.text(
            (bx + bw // 2, by + bh + off + bt + int(0.6 * mm)),
            f"{_n(short_side)} {sym_short}".strip(),
            fill="black",
            font=font(3.2, bold=True),
            anchor="ma",
        )
        vt = f"{_n(long_side)} {sym_long}".strip()
        vfont = font(3.2, bold=True)
        vbb = draw.textbbox((0, 0), vt, font=vfont)
        vimg = Image.new("RGB", (int(vbb[2]) + 2, int(vbb[3]) + 2), "white")
        vdraw = ImageDraw.Draw(vimg)
        vdraw.fontmode = "1"
        vdraw.text((1, 1), vt, fill="black", font=vfont)
        vimg = vimg.rotate(90, expand=True)
        # Keng eskizda yozuv qog'oz chetidan chiqib ketmasin
        vx = min(bx + bw + off + bt + int(0.6 * mm), W - vimg.width - 1)
        img.paste(vimg, (vx, by + (bh - vimg.height) // 2))

    buf = _io.BytesIO()
    # Yakuniy 1-bit: har piksel sof qora yoki oq
    img.convert("L").point(_bw, "1").save(buf, format="PNG")
    return buf.getvalue()
