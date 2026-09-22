"""`.b3d` dan brauzer uchun model JSON'i.

Yuklashda BIR MARTA yasaladi va diskda saqlanadi: ochiq sahifa uni o'qib
beradi, xolos. Har so'rovda qayta o'qish mumkin emas edi — eng katta fayl
~2 soniya CPU oladi, ochiq (autentifikatsiyasiz) bir necha so'rov butun sexni
sekinlashtirardi.

Kalitlar qisqa (`p`, `q`, `o`): 268 panelli mahsulotda uzun nomlar JSON'ni
kattalashtiradi, sahifa esa asosan planshet va telefonda ochiladi.
"""

import io
import json
from typing import Any

from PIL import Image, ImageDraw, ImageFilter

from .models import BazisPanel, ParsedBazis

#: Model versiyasi. Frontend eskirgan faylni shundan taniydi.
VERSION = 1
#: Eskiz fonini to'kishdagi rang chidamliligi. 10 da ichkaridagi OQ panel
#: saqlanib qoladi; 30 da to'kish ichkariga sizib o'tib, oq fasadni ham
#: yeb qo'yadi (4 namunada o'lchandi).
_FON_CHIDAM = 10
#: Shundan tor eskiz ikki barobar kattalashtiriladi. Bazis eskizi 256x256, uning
#: ichida mahsulot ~240x140 joy egallaydi, kartochkada esa u ~500 px kenglikda
#: ko'rsatiladi: kattalashtirishni brauzerga qoldirsak chiziqlar xiralashadi.
_KENG_CHEK = 480


def thumbnail_png(xom: bytes) -> bytes:
    """Bazis eskizini kartochkaga yaroqli holga keltiradi.

    Uch amal, uchalasi ham O'LCHANGAN kamchilikka javob beradi:

    1. OQ FON SHAFFOF. Bazis oq fonga chizadi; oq kvadrat oq kartochka ustida
       chegarasiz va hajmsiz ko'rinardi. To'kish CHETDAN boshlanadi, global
       rang almashtirish emas — aks holda modelning ichidagi oq panel ham
       yo'qolardi.
    2. CHETLARI KESILADI. 256x256 ning ichida mahsulot atigi ~240x140 (namunada
       34-60% i quruq fon edi). Kesilgach u kartochkani to'ldiradi — «xira»
       taassurotining asosiy sababi aynan shu bo'sh hoshiya edi.
    3. IKKI BAROBAR KATTALASHTIRISH + yengil keskinlashtirish. Kartochkadagi
       joy ~500 px: kattalashtirish baribir bo'ladi, faqat Lanczos brauzernikidan
       yaxshiroq qiladi. Natija 256 rangli palitraga o'tkaziladi — CAD renderida
       ranglar oz, kartochkada farq ko'rinmaydi, hajm esa 206 KB dan 46 KB ga
       tushadi (telefonda uchta kartochka birdan yuklanadi).

    Rangga tegilmaydi: kontrastni oshirish yog'ochni sarg'aytirib, materialni
    boshqacha ko'rsatib qo'yardi.
    """
    try:
        im = Image.open(io.BytesIO(xom)).convert("RGBA")
    except Exception:
        return xom
    w, h = im.size
    for burchak in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        px = im.getpixel(burchak)
        if not isinstance(px, tuple) or px[3] == 0:
            continue
        ImageDraw.floodfill(im, burchak, (255, 255, 255, 0), thresh=_FON_CHIDAM)
    quti = im.getchannel("A").getbbox()
    if not quti:
        # Eskizning O'ZI bo'm-bo'sh (75 namunadan bittasi shunday: Bazis oq
        # kvadrat chizib qo'ygan). Kesadigan narsa yo'q — aslini qaytaramiz.
        return xom
    im = im.crop(quti)
    if im.width < _KENG_CHEK:
        im = im.resize((im.width * 2, im.height * 2), Image.Resampling.LANCZOS)
        rang = Image.merge("RGB", im.split()[:3]).filter(ImageFilter.UnsharpMask(radius=1.0, percent=80, threshold=2))
        im = Image.merge("RGBA", (*rang.split(), im.getchannel("A")))
    chiqish = io.BytesIO()
    # FASTOCTREE — RGBA ni qo'llab-quvvatlaydigan yagona usul; shaffoflik
    # palitradagi bitta indeksga aylanadi (bizda alfa baribir 0 yoki 255).
    im.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).save(
        chiqish, "PNG", optimize=True
    )
    return chiqish.getvalue()


def _yumaloq(qatorlar: list[list[float]], xona: int) -> list[list[float]]:
    return [[round(v, xona) for v in q] for q in qatorlar]


def _panel(p: BazisPanel, mat: dict[str, int]) -> dict[str, Any]:
    eni, boyi = p.size
    out: dict[str, Any] = {
        "id": p.des,
        "n": p.name,
        "m": mat[p.mat_name],
        "t": round(p.thick, 1),
        "s": [eni, boyi],
        "p": [round(v, 1) for v in p.pos],
        "q": [round(v, 5) for v in p.quat],
        "o": _yumaloq(p.poly, 1),
    }
    if p.circles:
        out["c"] = _yumaloq(p.circles, 1)
    if p.animated:
        # Ochilgan holat FAQAT harakatlanadigan panelda: 2285 paneldan 570 tasi
        # (eshik, tortma, yuqoriga ochiladigan qopqoq). Qolgani uchun bu ikki
        # maydon `p`/`q` ning nusxasi bo'lardi va JSON'ni bekorga shishirardi.
        out["po"] = [round(v, 1) for v in p.pos_open]
        out["qo"] = [round(v, 5) for v in p.quat_open]
    if p.is_round:
        # Konturi aylana: `o` — taqribiy ko'pburchak.
        out["rd"] = 1
    return out


def build_model(parsed: ParsedBazis) -> dict[str, Any]:
    """Mahsulotning brauzerga tayyor tavsifi."""
    nomlar: list[str] = []
    mat: dict[str, int] = {}
    for p in parsed.panels:
        # FAQAT panel materiali. Kromka materiali ham shu ro'yxatda edi, lekin
        # brauzer uni ishlatmaydi (§3.1) va `mats` ni bekorga uzaytirardi.
        if p.mat_name not in mat:
            mat[p.mat_name] = len(nomlar)
            nomlar.append(p.mat_name)
    return {
        "v": VERSION,
        "code": parsed.code,
        "name": parsed.name,
        "mats": nomlar,
        "panels": [_panel(p, mat) for p in parsed.panels],
    }


def dump_model(parsed: ParsedBazis) -> bytes:
    """Diskka yoziladigan ko'rinish — bo'shliqsiz, UTF-8 saqlangan holda."""
    return json.dumps(build_model(parsed), ensure_ascii=False, separators=(",", ":")).encode()
