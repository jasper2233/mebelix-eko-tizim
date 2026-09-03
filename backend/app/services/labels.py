"""Yorliq renderi: 80×60 mm termal yorliq, 203 dpi (8 dot/mm).

render_label_png PNG chizadi — bridge-agent uni USB GoDEX'ga Windows drayveri (GDI)
orqali chiqaradi. Maket MES PRO chekiga (chek/IMG_4925.JPG) va GibSaw shablonlariga
asoslangan. EZPL yo'q: G500-U'da tarmoq porti yo'q, RAW dialekt kerak emas.
"""

import io
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import TASHKENT_TZ
from app.models import Order, Part, PartInstance, PartRoute
from app.services.scanning import qr_part_code


@dataclass
class LabelData:
    qr_text: str  # {buyurtma}_productCode_partCode[_n] — `_n` faqat count > 1 (docs/11)
    part_code: str  # productCode_partCode (chek: "4202_8")
    part_name: str
    project_name: str
    material: str  # plita (chek: "ldsp kashmir shagrin")
    length: float | None
    width: float | None
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


async def load_label_data(db: AsyncSession, instance_id: int) -> LabelData | None:
    """Bitta nusxa uchun yorliq ma'lumotini DB'dan yig'adi (print task va PNG endpoint uchun umumiy)."""
    # Yumshoq o'chirilgani ham yo'q hisoblanadi: matritsada count kamayganda yoki
    # .project qayta import qilinganda nusxalar `is_deleted` bo'ladi — chek POST/DELETE
    # ular uchun 404 beradi, PNG ham xuddi shunday qilishi kerak.
    instance = await db.get(PartInstance, instance_id)
    if instance is None or instance.is_deleted:
        return None
    part = await db.get(Part, instance.part_id)
    order = await db.get(Order, instance.order_id)
    if part is None or part.is_deleted or order is None or order.is_deleted:
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

    # Marshrut faqat NOSTANDART detalda chiqadi: uni texnolog qo'lda chizgan va
    # operator qaysi bosqichdan keyin qayerga yuborishni chekdan bilishi kerak.
    # Standart detalda marshrut oldindan ma'lum — chekni behuda band qilardi.
    route_codes: list[int] = []
    if part.is_custom:
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
        material=part.material_name or "",
        length=part.length,
        width=part.width,
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

_MM = 8  # piksel/mm — 203 dpi (8 dot/mm), ya'ni 80x60 mm blank = 640x480 px


def _canvas() -> tuple[Any, Any, int]:
    """Bo'sh 80x60 mm blank — to'rtala chek shundan boshlanadi."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (80 * _MM, 60 * _MM), "white")
    draw = ImageDraw.Draw(img)
    # Termoprinter 1-bit: antialiasing o'chiriladi, aks holda drayver dither qiladi
    draw.fontmode = "1"
    return img, draw, _MM


def _font(size_mm: float, bold: bool = False) -> Any:
    """Shrift ro'yxati tartib bilan sinaladi; hech biri topilmasa PIL sukut shrifti."""
    from PIL import ImageFont

    for path in _FONT_BOLD if bold else _FONT_REGULAR:
        try:
            return ImageFont.truetype(path, int(size_mm * _MM))
        except OSError:
            continue
    return ImageFont.load_default()


def _paste_logo(img: Any, *, width_mm: float, xy: tuple[int, int]) -> bool:
    """Logo — Universal.lbl dan ajratilgan, threshold qilingan.
    Fayl o'qilmasa False; chaqiruvchi o'rniga matn yozadi."""
    from pathlib import Path

    from PIL import Image

    try:
        logo_path = Path(__file__).resolve().parents[1] / "assets" / "label-logo.png"
        logo = Image.open(logo_path).convert("L").point(_bw).convert("RGB")
        lw = int(width_mm * _MM)
        img.paste(logo.resize((lw, int(lw * logo.height / logo.width))), xy)
    except OSError:
        return False
    return True


def _to_1bit_png(img: Any) -> bytes:
    """Yakuniy chiqish — sof 1-bit PNG (termodrayver dither qilmasin)."""
    buf = io.BytesIO()
    img.convert("L").point(_bw, "1").save(buf, format="PNG")
    return buf.getvalue()


def render_label_png(d: LabelData) -> bytes:  # noqa: C901 — chiziqli layout kodi
    """80x60mm yorliq PNG (203 dpi: 8 dot/mm -> 640x480 px).

    Ustunlar tartibi mebelix.lbl bo'yicha: chap ustun — matnlar, o'ng ustun —
    QR (tepada) va detal eskizi vertikal (ostida). 1-bit, antialiasing'siz.
    """
    from pathlib import Path

    import qrcode
    from PIL import Image, ImageDraw

    img, draw, mm = _canvas()

    def text(
        x: float,
        y: float,
        t: str,
        size_mm: float,
        bold: bool = False,
        anchor: str = "la",
        max_mm: float | None = None,
    ) -> None:
        """max_mm berilsa — matn shu kenglikka sig'guncha oxiridan kesiladi.
        Belgi soni bilan cheklash yetarli emas: bir xil uzunlikdagi satrlar
        turlicha keng chiqadi va uzuni qo'shni blok (QR) ostida ko'rinmay qoladi."""
        font = _font(size_mm, bold)
        if max_mm is not None:
            while t and draw.textlength(t, font=font) > max_mm * mm:
                t = t[:-1]
        draw.text((x * mm, y * mm), t, fill="black", font=font, anchor=anchor)

    def edge_field(side: str, key: str) -> str:
        e = d.edges.get(side)
        return str(e.get(key) or "").strip() if e else ""

    # ============ CHAP USTUN (x 5..52) ============
    if not _paste_logo(img, width_mm=22, xy=(3 * mm, 1 * mm)):
        text(5, 1, "MEBELIX", 4, bold=True)

    product_code = d.part_code.split("_", 1)[0]
    text(26, 1.5, "Formatka", 2.8)
    text(26, 4.8, product_code[:7], 3.7, bold=True)
    # Nusxa ID (= QR matni = SCX fayl nomi = Panel ID), QR chap chetigacha sig'diriladi:
    # prisadkachi shu yozuv bilan stanokdagi faylni solishtira oladi (docs/11)
    # ID dumi (nusxa raqami) kesilmasligi shart — sig'guncha kichraytiriladi; 1.6 mm da ham
    # sig'masa BOSHIDAN (buyurtma prefiksidan) qisqartiriladi, QR baribir to'liq satr.
    id_text = d.qr_text
    id_size = next(
        (s for s in (2.7, 2.4, 2.2, 2.0, 1.8, 1.6) if draw.textlength(id_text, font=_font(s)) <= 34 * mm), 1.6
    )
    while len(id_text) > 1 and draw.textlength(id_text, font=_font(id_size)) > 34 * mm:
        id_text = id_text[1:]
    text(5, 9.5, id_text, id_size)

    # Loyiha — QR chap chetigacha (x=40mm) sig'adigan kenglikka kesiladi, 1mm zaxira.
    # Ilgari 26 belgi limiti turardi: u QR'ni hisobga olmasdi va uzun nomning dumi
    # QR ostida ko'rinmay qolardi.
    text(5, 13.5, d.project_name, 3.3, bold=True, max_mm=34)

    # Kromka 2x2 (tagchiziq bilan): chapda uzunlik tomonlari (t/b), o'ngda en (l/r)
    def edge_cell(x: float, y: float, mat: str) -> None:
        if not mat:
            return
        text(x, y, mat[:14], 2.9, bold=True)
        draw.line(
            (int(x * mm), int((y + 3.4) * mm), int((x + 22) * mm), int((y + 3.4) * mm)),
            fill="black",
            width=2,
        )

    edge_cell(5, 19, edge_field("t", "mat"))
    edge_cell(29, 19, edge_field("l", "mat"))
    edge_cell(5, 30, edge_field("b", "mat"))
    edge_cell(29, 30, edge_field("r", "mat"))

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
        # Sverlo ikonkasi Marshrut qatorining o'ngidagi bo'sh zonada (x49.5, y40):
        # ID qatori endi buyurtma prefiksi bilan 37 mm gacha cho'ziladi, eski joy (x35, y9.4) ustiga tushardi
        drill_path = Path(__file__).resolve().parents[1] / "assets" / "label-icon-drill.png"
        isz = int(6 * mm)
        try:
            raw = Image.open(drill_path)
            flat = Image.new("RGB", raw.size, "white")
            flat.paste(raw, mask=raw.getchannel("A") if "A" in raw.getbands() else None)
            icon = flat.convert("L").point(_bw).convert("RGB").resize((isz, isz))
            img.paste(icon, (int(49.5 * mm), int(40 * mm)))
        except OSError:
            text(49.5, 40, "С", 3.2, bold=True)

    # Marshrut — ALOHIDA qator (nomga qo'shilsa 24 belgi kesimida yo'qolardi).
    # Kodlar tsexning "Jarayon uchun kodlar" jadvalidagi raqamlar.
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

    # ====== O'NG USTUN: QR (x 40..56), eskiz (x 58.5..73.5) ======
    # QR tepada — to'liq nusxa kodi (skan oqimi)
    qr = qrcode.make(d.qr_text, box_size=2, border=0)
    qr_px = 16 * mm
    img.paste(qr.get_image().convert("RGB").resize((qr_px, qr_px)), (40 * mm, 1 * mm))

    # Detal eskizi vertikal — Universal.lbl <part> uslubi: ingichka kontur,
    # kromka konturdan 1mm TASHQARIDA qalin chiziq + tomon belgisi; o'lchamlar
    # pastda (en) va o'ng tomonda aylantirilgan (uzunlik)
    if d.length and d.width:
        long_side, short_side = max(d.length, d.width), min(d.length, d.width)
        # Eskiz UZUN tomonni vertikal qilib chizadi. Bu detal 90° BURILGAN
        # degani emas: uzun tomon `length` bo'lsa eskiz burilgan, `width` bo'lsa
        # tabiiy holatda. Ilgari doim burilgan deb hisoblanardi — natijada eni
        # uzunroq detalda (masalan 120x400) kromka, teshik va o'lcham belgilari
        # 90° noto'g'ri tomonga tushardi. Kesish xaritasi to'g'ri ko'rsatar,
        # chek esa yolg'on gapirardi.
        #
        # Detal o'z koordinatasida: x = uzunlik, y = en.
        #   t/b — y qirralari, UZUNLIK bo'ylab ketadi
        #   l/r — x qirralari, EN bo'ylab ketadi
        burilgan = d.length > d.width
        # detal tomoni -> eskizdagi qirra
        # Burilgan eskizda HAQIQIY 90° burilish (x,y)->(y, l-x) — kesish
        # xaritasi va GibSaw bilan bitta konvensiya: lokal `l` qirra (x=0)
        # eskiz PASTIGA, `r` (x=l) TEPAGA tushadi. Ilgari transpose edi (l->tepa,
        # r->past) — bu oyna: kromka va qirra teshiklari qarama-qarshi uchda
        # ko'rsatilardi, arrachi xarita bilan solishtirsa mos kelmasdi.
        qirra = (
            {"t": "chap", "b": "ong", "l": "past", "r": "tepa"}
            if burilgan
            else {"l": "chap", "r": "ong", "t": "tepa", "b": "past"}
        )
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
        draw.rectangle((bx, by, bx + bw, by + bh), outline="black", width=2)

        for tomon, joy in qirra.items():
            if not d.edges.get(tomon):
                continue
            if joy == "chap":
                draw.rectangle((bx - off - bt, by, bx - off, by + bh), fill="black")
            elif joy == "ong":
                draw.rectangle((bx + bw + off, by, bx + bw + off + bt, by + bh), fill="black")
            elif joy == "tepa":
                draw.rectangle((bx, by - off - bt, bx + bw, by - off), fill="black")
            else:
                draw.rectangle((bx, by + bh + off, bx + bw, by + bh + off + bt), fill="black")

        # Tekstura yo'nalishi: 3 ingichka chiziq UZUNLIK (`l` — teksturali
        # materialda birinchi o'lcham, tekstura qulflangan o'q) BO'YLAB.
        # Yo'nalish ESKIZGA ergashadi: `burilgan` (l vertikal) bo'lsa chiziqlar
        # vertikal, aks holda gorizontal. Ilgari doim vertikal chizilardi —
        # 250x832 kabi l < w detalda (eskiz burilmagan, l gorizontal) chek
        # teksturani 90° noto'g'ri ko'rsatib, kesish xaritasi bilan mos kelmasdi;
        # arrachilar aynan shu farqdan shikoyat qilgan. Teshiklardan oldin
        # chiziladi (teshik ustida qolsin).
        if d.texture:
            w2 = 2  # kamida 2px: GDI kichraytirishda 1px yo'qoladi
            if burilgan:
                tl = int(bh * 0.32)
                gap = max(3, bw // 4)
                for xx in (bx + bw // 2 - gap, bx + bw // 2, bx + bw // 2 + gap):
                    draw.line((xx, by + (bh - tl) // 2, xx, by + (bh + tl) // 2), fill="black", width=w2)
            else:
                tl = int(bw * 0.32)
                gap = max(3, bh // 4)
                for yy in (by + bh // 2 - gap, by + bh // 2, by + bh // 2 + gap):
                    draw.line((bx + (bw - tl) // 2, yy, bx + (bw + tl) // 2, yy), fill="black", width=w2)

        # Haqiqiy sverlo o'rinlari (GibSaw'da yo'q — bizda cutmap'dan bor):
        # lokal (x bo'ylab uzunlik, y bo'ylab en) -> vertikal eskiz koordinatalari
        if d.holes and d.holes.get("l") and d.holes.get("w"):
            hl, hw = float(d.holes["l"]), float(d.holes["w"])
            # Qaysi o'lcham qaysi o'qqa tushishi eskiz yo'nalishiga bog'liq
            kx = bw / (hw if burilgan else hl)
            ky = bh / (hl if burilgan else hw)
            for b in d.holes.get("bores", []):
                # burilgan: (x,y)->(y, l-x) — transpose emas (u oyna bo'lardi)
                gor, ver = (b["y"], hl - b["x"]) if burilgan else (b["x"], b["y"])
                cxp = bx + int(float(gor) * kx)
                cyp = by + int(float(ver) * ky)
                r = max(int(0.4 * mm), int(float(b.get("d", 5)) / 2 * min(kx, ky)))
                draw.ellipse((cxp - r, cyp - r, cxp + r, cyp + r), fill="white", outline="black", width=2)
            for b in d.holes.get("edge", []):
                side, pos = b.get("side"), float(b.get("pos", 0))
                dp = min(float(b.get("dp", 12)), 30) * min(kx, ky)
                tick = max(2, int(dp))
                # Vertikal qirradagi teshik `ky` bo'ylab, gorizontaldagisi `kx`
                # bo'ylab joylashadi — yo'nalish `qirra` xaritasidan keladi
                teshik_joyi = qirra.get(side or "")
                # t/b qirradagi pos lokal X bo'ylab: burilgan eskizda u vertikal
                # o'qqa (y, l-x) bilan tushadi; l/r qirradagi pos lokal Y bo'ylab
                # — burilganda gorizontalga o'zgarishsiz o'tadi.
                if teshik_joyi in ("chap", "ong"):
                    yy = by + int((hl - pos if burilgan else pos) * ky)
                    if teshik_joyi == "chap":
                        draw.line((bx, yy, bx + tick, yy), fill="black", width=2)
                    else:
                        draw.line((bx + bw - tick, yy, bx + bw, yy), fill="black", width=2)
                elif teshik_joyi in ("tepa", "past"):
                    xx = bx + int(pos * kx)
                    if teshik_joyi == "tepa":
                        draw.line((xx, by, xx, by + tick), fill="black", width=2)
                    else:
                        draw.line((xx, by + bh - tick, xx, by + bh), fill="black", width=2)

        # O'lchamlar: en pastda gorizontal, uzunlik o'ngda aylantirilgan (Universal size.top/left=false).
        # Har o'lcham yoniga o'sha tomonlar kromka belgilari (xaritadagi "450 B" uslubi):
        # uzunlik <- t/b tomonlar, en <- l/r tomonlar
        # Uzun o'lcham yonida — o'sha o'lcham BO'YLAB ketadigan qirralar belgisi
        uzun_tomonlar = ("t", "b") if burilgan else ("l", "r")
        qisqa_tomonlar = ("l", "r") if burilgan else ("t", "b")
        sym_long = "".join(edge_field(s, "symbol")[:3] for s in uzun_tomonlar)
        sym_short = "".join(edge_field(s, "symbol")[:3] for s in qisqa_tomonlar)
        draw.text(
            (bx + bw // 2, by + bh + off + bt + int(0.6 * mm)),
            f"{_n(short_side)} {sym_short}".strip(),
            fill="black",
            font=_font(3.2, bold=True),
            anchor="ma",
        )
        vt = f"{_n(long_side)} {sym_long}".strip()
        vfont = _font(3.2, bold=True)
        vbb = draw.textbbox((0, 0), vt, font=vfont)
        vimg = Image.new("RGB", (int(vbb[2]) + 2, int(vbb[3]) + 2), "white")
        vdraw = ImageDraw.Draw(vimg)
        vdraw.fontmode = "1"
        vdraw.text((1, 1), vt, fill="black", font=vfont)
        vimg = vimg.rotate(90, expand=True)
        # Keng eskizda yozuv qog'oz chetidan chiqib ketmasin
        vx = min(bx + bw + off + bt + int(0.6 * mm), img.width - vimg.width - 1)
        img.paste(vimg, (vx, by + (bh - vimg.height) // 2))

    return _to_1bit_png(img)


@dataclass
class PachkaLabelData:
    """Qadoq chekining ma'lumoti (TZ Upakovka).

    Detal yorlig'idan farqli: bu yerda eskiz, kromka va teshik yo'q — qadoq
    ichiga qaralmaydi, u yopiq. Skanerlanganda tizim tarkibni ko'rsatadi.
    """

    code: str  # PK-B-2026-014-03 — QR matni ham, ko'rinadigan kod ham
    order_number: str
    project_name: str  # GibLab fayl nomi (3139_Farhod) — bo'sh bo'lishi mumkin
    part_count: int
    printed_at: datetime


def render_pachka_label_png(d: PachkaLabelData) -> bytes:
    """80x60mm qadoq cheki PNG (203 dpi) — detal yorlig'i bilan bir xil o'lcham
    va bir xil printer zanjiri (bridge-agent + GoDEX).

    Maket ataylab siyrak: qadoq TMO da va yuklashda uzoqdan o'qiladi, shuning
    uchun QR katta va kod yirik shriftda. Og'irlik chiqarilmaydi — tizim uni
    faqat qadoqlash ekranida taxminiy ko'rsatadi, chekda aniq raqamdek
    ko'rinib, xato ishonch berardi.
    """
    import qrcode

    img, draw, mm = _canvas()

    def text(x: float, y: float, t: str, size_mm: float, bold: bool = False, anchor: str = "la") -> None:
        draw.text((x * mm, y * mm), t, fill="black", font=_font(size_mm, bold), anchor=anchor)

    if not _paste_logo(img, width_mm=24, xy=(4 * mm, 2 * mm)):
        text(5, 2, "MEBELIX", 4.5, bold=True)

    text(5, 13, "QADOQ", 3.2, bold=True)
    # Kod chap ustunga (x 5..46) sig'ishi kerak — o'ngda QR turibdi. 16 belgili
    # `PK-B-2026-014-03` 4.6 mm da ~40 mm oladi; kattaroq shriftda QR ustiga chiqardi.
    text(5, 17, d.code[:18], 4.6, bold=True)

    # Ajratuvchi chiziq — kod bloki bilan tafsilotlar orasida
    draw.line((int(5 * mm), int(26.5 * mm), int(46 * mm), int(26.5 * mm)), fill="black", width=2)

    text(5, 29, "Buyurtma", 2.9)
    text(5, 32.5, d.order_number[:18], 4.4, bold=True)
    if d.project_name:
        text(5, 39.5, "Loyiha", 2.9)
        text(5, 43, d.project_name[:18], 4.4, bold=True)

    # Pastki bloklar 4 mm zaxirada tugaydi (detal yorlig'idagi qoida): termal
    # chetda yeyilish bo'lgani uchun 55.5 mm dan pastga yozilmaydi.
    text(5, 48, "Detallar soni", 2.9)
    text(5, 51.5, str(d.part_count), 4.4, bold=True)
    text(46, 53, d.printed_at.strftime("%Y.%m.%d %H:%M"), 2.5, anchor="ra")

    # QR o'ngda, katta: TMO va yuklashda uzoqdan skanerlanadi
    qr = qrcode.make(d.code, box_size=2, border=0)
    qr_px = 28 * mm
    img.paste(qr.get_image().convert("RGB").resize((qr_px, qr_px)), (48 * mm, 4 * mm))
    text(62, 34.5, d.code[:22], 2.5, anchor="ma")

    return _to_1bit_png(img)


@dataclass
class WasteLabelData:
    """Foydali atxot cheki (GibLab `business` qoldig'i).

    GibSaw'dagi "Деловой остаток" chekining o'zbekcha muqobili (mebelix.lbl
    shu blok bilan ishlagan). Eskiz yo'q — atxot to'rtburchak, unga chizma
    ortiqcha; asosiysi O'LCHAM (katta), material va QR.
    """

    qr_text: str  # ATX-{buyurtma}-{n}
    order_number: str
    project_name: str
    material: str
    length: float
    width: float
    sheet_no: int
    printed_at: datetime


def render_waste_label_png(d: WasteLabelData) -> bytes:
    """80x60mm foydali-atxot cheki — detal/qadoq cheklari bilan bir xil
    o'lcham va printer zanjiri (bridge-agent + GoDEX)."""
    import qrcode

    img, draw, mm = _canvas()

    def text(x: float, y: float, t: str, size_mm: float, bold: bool = False, anchor: str = "la") -> None:
        draw.text((x * mm, y * mm), t, fill="black", font=_font(size_mm, bold), anchor=anchor)

    if not _paste_logo(img, width_mm=24, xy=(4 * mm, 2 * mm)):
        text(5, 2, "MEBELIX", 4.5, bold=True)

    # Sarlavha atxotligini QICHQIRIB aytadi — omborda detal cheki bilan
    # adashtirilmasin (GibSaw ham "Деловой остаток" ni alohida yozadi)
    # "QOLDIQ" — tsex tili ("foydali atxot" sun'iy jaranglaydi; GibSaw ruschada
    # "Деловой остаток" ishlatgan, o'zbekcha muqobili shu). Sarlavha vazifasi
    # bitta: detal cheki bilan adashtirmaslik.
    text(5, 13, "QOLDIQ", 4.2, bold=True)
    text(5, 17.5, d.qr_text[:18], 4.2, bold=True)

    draw.line((int(5 * mm), int(26 * mm), int(46 * mm), int(26 * mm)), fill="black", width=2)

    # O'lcham — chekning eng muhim raqami: omborchi atxotni shu bo'yicha qidiradi
    text(5, 28.5, "O'lcham", 2.9)
    text(5, 32, f"{_n(d.length)} x {_n(d.width)}", 5.4, bold=True)

    text(5, 41, "Material", 2.9)
    text(5, 44.5, d.material[:20], 3.6, bold=True)

    text(5, 51.5, f"{d.order_number}  ·  {d.project_name[:12]}  ·  list {d.sheet_no}", 2.7)
    text(46, 55.5, d.printed_at.strftime("%Y.%m.%d %H:%M"), 2.5, anchor="ra")

    qr = qrcode.make(d.qr_text, box_size=2, border=0)
    qr_px = 28 * mm
    img.paste(qr.get_image().convert("RGB").resize((qr_px, qr_px)), (48 * mm, 4 * mm))
    text(62, 34.5, d.qr_text[:22], 2.5, anchor="ma")

    return _to_1bit_png(img)


@dataclass
class BadgeLabelData:
    """Hodim beyjigi — 80×60 mm, detal cheki bilan bir xil blank va bir xil zanjir."""

    full_name: str
    position: str  # lavozim; bo'sh bo'lishi mumkin
    badge_id: str  # QR matni (UUID)


def render_badge_png(d: BadgeLabelData) -> bytes:
    """80×60 mm hodim beyjigi PNG (203 dpi).

    Maket: lavozim (kichik) → ism (katta) → QR. QR o'rni QAT'IY — ism bir yoki
    ikki qatorga tushishidan qat'i nazar u bir joyda turadi, ya'ni skaner uchun
    beyjiklar bir xil.
    """
    import qrcode

    img, draw, mm = _canvas()
    W = img.width

    name_font = _font(5.5, bold=True)
    # Ism ikki qatorgacha o'raladi, uchinchisi "…" bilan kesiladi: uzun o'zbek
    # ismlari (F.I.Sh + otasining ismi) 80mm ga sig'maydi.
    max_px = 72 * mm
    lines: list[str] = []
    current = ""
    for word in d.full_name.split():
        trial = f"{current} {word}".strip()
        if not current or draw.textlength(trial, font=name_font) <= max_px:
            current = trial
            continue
        lines.append(current)
        current = word
        if len(lines) == 2:
            break
    if current and len(lines) < 2:
        lines.append(current)
    if not lines:
        lines = [d.full_name[:20]]
    # Uchinchi qatorga tushgan so'zlar tashlangan (bo'shliqlar IKKALA tomonda
    # olib tashlanadi, aks holda qator ichidagi bo'shliqlar qisqa dum
    # tashlanganini yashirib qo'yadi) — qisqartirishdan OLDIN hisoblanadi.
    dropped = len("".join(lines).replace(" ", "")) < len("".join(d.full_name.split()))
    # HAR QATOR alohida kesiladi: birinchi so'zning o'zi 72mm dan uzun bo'lsa
    # o'rash uni baribir qabul qiladi. "…" kesilgan qatorning O'ZIGA qo'shiladi
    # va u bilan birga o'lchanadi — aks holda belgi butun ism kesilgandek ko'rinadi.
    for i, line in enumerate(lines):
        if draw.textlength(line, font=name_font) <= max_px:
            continue
        while len(line) > 1 and draw.textlength(f"{line}…", font=name_font) > max_px:
            line = line[:-1]
        lines[i] = line.rstrip() + "…"
    if dropped and not lines[-1].endswith("…"):
        lines[-1] = lines[-1].rstrip() + "…"

    # Ism bloki PASTGA tekislanadi (y=20mm): bir qatorli ham, ikki qatorli ham
    # QR bilan orasidagi masofa bir xil bo'ladi
    top = 20 - len(lines) * 5.8
    # Lavozim ismning USTIGA yopishadi — ular bitta blok. Qat'iy y da qoldirilsa
    # bir qatorli ismda orada katta bo'shliq qolib, ikkisi ajralib ko'rinardi.
    if d.position:
        draw.text(
            (W // 2, int((top - 4.2) * mm)),
            d.position.upper()[:28],
            fill="black",
            font=_font(3.2, bold=True),
            anchor="ma",
        )
    for i, line in enumerate(lines):
        draw.text((W // 2, int((top + i * 5.8) * mm)), line, fill="black", font=name_font, anchor="ma")

    # QR QAT'IY o'rinda, markazda. 31mm dan KATTA qilinmasin: UUID QR'i 29
    # modul, ya'ni 31mm da modul 1.07mm va atrofdagi 4.5mm oq aynan standart
    # talab qiladigan 4 modul tinch zona. 34mm da tepada 1.7 modul qolib,
    # ism QR'ga yopishardi.
    qr = qrcode.make(d.badge_id, box_size=2, border=0)
    qr_px = 31 * mm
    img.paste(qr.get_image().convert("RGB").resize((qr_px, qr_px)), ((W - qr_px) // 2, int(24.5 * mm)))

    return _to_1bit_png(img)
