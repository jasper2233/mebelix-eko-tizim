"""`.b3d` dan brauzer uchun model JSON'i.

Yuklashda BIR MARTA yasaladi va diskda saqlanadi: ochiq sahifa uni o'qib
beradi, xolos. Har so'rovda qayta o'qish mumkin emas edi — eng og'ir fayl
1.7 s CPU oladi (460 faylda o'lchandi), ochiq (autentifikatsiyasiz) bir
necha so'rov butun sexni sekinlashtirardi.

Kalitlar qisqa (`p`, `q`, `o`): 268 panelli mahsulotda uzun nomlar JSON'ni
kattalashtiradi, sahifa esa asosan planshet va telefonda ochiladi.
"""

import io
import json
from typing import Any

from PIL import Image, ImageDraw, ImageFilter

from .models import BazisDim, BazisFurniture, BazisMesh, BazisPanel, ParsedBazis

#: Model versiyasi. JSON yuklashda bir marta yoziladi, shuning uchun shakli
#: o'zgarsa eski fayl diskda qoladi: frontend (`model.ts: MODEL_VERSIYA`) boshqa
#: versiyani chizmaydi va "texnolog modelni qayta yuklasin" deydi. 2 — `h`
#: (chiziqdan chizilgan kesmalar), `g` (harakat birligi), `cp`/`r` (profil
#: kesimi, tekstura tolasi), `meshes`/`furn` (furnitura va texnika) qo'shildi,
#: kontur uchlari bo'yicha ulanadi. Keyinroq ixtiyoriy `d` (bazischining
#: o'lchamlari) qo'shildi — versiya OSHIRILMADI: kaliti yo'q eski model ham to'g'ri
#: chiziladi (faqat o'lchamsiz), oshirilsa frontend saqlangan hamma modelni
#: "eskirgan" deb rad etardi (`3d.$token.tsx` qat'iy tenglik bilan solishtiradi).
VERSION = 2
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
    if p.holes:
        # Rakovina, plita kabi to'g'ri chiziqli kesmalar: 41 305 paneldan 494 tasida.
        out["h"] = [_yumaloq(h, 1) for h in p.holes]
    if p.circles:
        out["c"] = _yumaloq(p.circles, 1)
    if p.animated:
        # Ochilgan holat FAQAT harakatlanadigan panelda: 2285 paneldan 570 tasi
        # (eshik, tortma, yuqoriga ochiladigan qopqoq). Qolgani uchun bu ikki
        # maydon `p`/`q` ning nusxasi bo'lardi va JSON'ni bekorga shishirardi.
        out["po"] = [round(v, 1) for v in p.pos_open]
        out["qo"] = [round(v, 5) for v in p.quat_open]
        # Harakat birligi: tortmaning 5 paneli birga ochilishi kerak. Brauzer
        # buni harakatdan taxmin qila olmaydi — bir ilgak chizig'idagi ustma-ust
        # eshiklar ham, bir ustundagi tortmalar ham AYNAN bir xil harakatlanadi.
        if p.group is not None:
            out["g"] = p.group
    if p.is_round:
        # Konturi aylana: `o` — taqribiy ko'pburchak.
        out["rd"] = 1
    if p.clip:
        # Profil uchidagi 45° kesimlar (163 profil) — busiz ramka burchaklari ustma-ust
        out["cp"] = p.clip
    if p.grain_x:
        # Tekstura tolasi kontur X bo'ylab (Bazis `TexDir = 1`); sukut — Y bo'ylab
        out["r"] = 1
    return out


def _mesh(m: BazisMesh, mat: dict[str, int]) -> list[list[Any]]:
    """Qismlar: `[material, uchlar, normallar, uchburchak indekslari]`. Uch 0.1 mm,
    normal 0.001 aniqlikda — tutqich/ilgak uchun yetarli, JSON esa ikki barobar kichik."""
    return [
        [mat[q.mat_name], [round(v, 1) for v in q.positions], [round(v, 3) for v in q.normals], q.indices]
        for q in m.parts
    ]


def _furnitura(f: BazisFurniture) -> dict[str, Any]:
    out: dict[str, Any] = {
        "k": f.mesh,
        "n": f.name,
        "p": [round(v, 1) for v in f.pos],
        "q": [round(v, 5) for v in f.quat],
    }
    if f.animated:
        # Eshikdagi tutqich eshik bilan birga ochiladi — birligi ham eshikniki
        out["po"] = [round(v, 1) for v in f.pos_open]
        out["qo"] = [round(v, 5) for v in f.quat_open]
        if f.group is not None:
            out["g"] = f.group
    return out


def _olcham(d: BazisDim) -> dict[str, Any]:
    """`{v, a, b, o, g?}` — qiymat, o'lchangan ikki nuqta va chiziqning surilishi."""
    out: dict[str, Any] = {"v": d.value, "a": d.a, "b": d.b, "o": d.o}
    if d.group is not None:
        out["g"] = d.group
    return out


def build_model(parsed: ParsedBazis) -> dict[str, Any]:
    """Mahsulotning brauzerga tayyor tavsifi."""
    nomlar: list[str] = []
    mat: dict[str, int] = {}
    # FAQAT panel va furnitura qismlarining materiali. Kromka materiali ham shu
    # ro'yxatda edi, lekin brauzer uni ishlatmaydi (docs/13 §4, «Model JSON») va `mats` ni bekorga uzaytirardi.
    for nom in [p.mat_name for p in parsed.panels] + [q.mat_name for m in parsed.meshes for q in m.parts]:
        if nom not in mat:
            mat[nom] = len(nomlar)
            nomlar.append(nom)
    out: dict[str, Any] = {
        "v": VERSION,
        "code": parsed.code,
        "name": parsed.name,
        "mats": nomlar,
        "panels": [_panel(p, mat) for p in parsed.panels],
        "meshes": [_mesh(m, mat) for m in parsed.meshes],
        "furn": [_furnitura(f) for f in parsed.furniture],
    }
    if parsed.dims:
        out["d"] = [_olcham(d) for d in parsed.dims]
    return out


def dump_model(parsed: ParsedBazis) -> bytes:
    """Diskka yoziladigan ko'rinish — bo'shliqsiz, UTF-8 saqlangan holda.

    Buzuq faylda son NaN/cheksiz bo'lsa `ValueError`: `json.dumps` sukut bo'yicha
    `NaN` yozadi, brauzerning `JSON.parse` esa uni rad etadi — yuklash
    "muvaffaqiyatli" bo'lib, ochiq sahifa model chiza olmay qolardi.
    """
    return json.dumps(build_model(parsed), ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
