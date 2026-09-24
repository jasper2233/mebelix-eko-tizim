"""Brend aktivlarining YAGONA manbasi — `design/` (logolar `design/logo/`, chek
ikonkasi `design/label-icons/`). Qolgan hamma nusxa shundan.

NEGA. Backend image, frontend image va bridge-agent `.exe` alohida quriladi va har
biri faqat o'z papkasini ko'radi (`.dockerignore` da `design`, frontend konteksti
`./frontend`, agent onefile). Ya'ni ishlaydigan nusxa o'sha qurilmaning ICHIDA
turishi shart. Lekin ular qo'lda ko'chirilganda masterdan jimgina ajralardi:
`label-logo.png` 16% siqilib qolgan edi, `logo-navy.png` "ishlatilmaydi" deb
o'chirilib, keyin qaytarilgan edi. Endi nusxalar QO'LDA TAHRIRLANMAYDI —
`frontend/src/client/**` kabi, shu skript bilan yasaladi.

    cd backend && uv run python ../scripts/brand-assets.py --check   # CI: farq bo'lsa exit 1
    cd backend && uv run python ../scripts/brand-assets.py --write   # master o'zgargach

`backend/` dan: Pillow faqat o'sha muhitda (repo ildizida `pyproject.toml` yo'q).

Nusxa ikki xil:

* ODDIY NUSXA — masterning bayt-baytiga o'zi. Tekshiruv — baytlar.
* HOSILA — boshqa format: PWA ikonkasi (tilla belgi navy plitada), favicon,
  `.ico`, agent ichidagi base64. Tekshiruv — dekodlangan PIKSELLAR, aynan. Baytlar
  emas: PNG/ICO siqilishi OS'ga qarab farq qiladi, piksellar esa yo'q (o'lchangan,
  Pillow 12.3.0, Windows va Linux: 8 faylning 8 tasida bayt boshqa, 14 chiqishning
  14 tasida piksel bir xil). Pillow yangilanib piksellar o'zgarsa — `--write`.

PWA retsepti ikonkalarni yaratgan commitlardan olingan (`a2d4b26`, `997ec37`,
`60c270b`): fon `#2F496E` -> `#16233A` vertikal gradient, belgi `any`/apple da
eni 78 %, `maskable` da 66 % (Android'ning 80 % xavfsiz zonasi ichida), `any` ning
burchagi yumaloq.
"""

import argparse
import base64
import io
import re
import sys
from collections.abc import Callable
from functools import partial
from pathlib import Path

from PIL import IcoImagePlugin, Image, ImageChops, ImageDraw

R = Path(__file__).resolve().parents[1]
MASTER = R / "design" / "logo"

NAVY_TEPA = (0x2F, 0x49, 0x6E)
NAVY_PAST = (0x16, 0x23, 0x3A)
#: `any` ikonkaning burchak radiusi — mavjud ikonkadan o'lchangan (512 da 92 px).
RADIUS = 0.18
ICO_OLCHAMLAR = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
#: Agent oynasi va tray uchun balandlik (`agent.py` shuni kutadi).
AGENT_BALANDLIK = 112

#: nusxa -> master (bayt-baytiga), ikkalasi ham repo ildizidan
NUSXALAR = {
    "frontend/public/assets/logo/logo-gold.png": "design/logo/logo-gold.png",
    "frontend/public/assets/logo/logo-navy.png": "design/logo/logo-navy.png",
    "frontend/public/assets/logo/icon-navy.png": "design/logo/icon-navy.png",
    "backend/app/assets/logo-black.png": "design/logo/logo-black.png",
    # Chekdagi sverlo ikonkasi — termoprinterning 1-bit quvuri uchun QAYTA chizilgan
    # 281x268 (asl 40x40 `drill.png` 48 px da shashkaga aylanib kul rang bosilardi)
    "backend/app/assets/label-icon-drill.png": "design/label-icons/drill-hires.png",
}


def _master(nom: str) -> Image.Image:
    return Image.open(MASTER / nom).convert("RGBA")


def _belgi(nom: str, eni: int) -> Image.Image:
    im = _master(nom)
    return im.resize((eni, round(eni * im.height / im.width)), Image.Resampling.LANCZOS)


def _plita(olcham: int, ulush: float, yumaloq: bool) -> Image.Image:
    """Tilla belgi navy gradient plita markazida."""
    fon = Image.new("RGBA", (olcham, olcham))
    chiz = ImageDraw.Draw(fon)
    for y in range(olcham):
        t = y / olcham
        chiz.line(
            [(0, y), (olcham, y)],
            fill=tuple(int(a + (b - a) * t) for a, b in zip(NAVY_TEPA, NAVY_PAST, strict=True)) + (255,),
        )
    belgi = _belgi("icon-gold.png", round(olcham * ulush))
    fon.alpha_composite(belgi, ((olcham - belgi.width) // 2, (olcham - belgi.height) // 2))
    if yumaloq:
        # 4x katta chizib kichraytiriladi — burchak qirrasi silliq chiqsin
        mask = Image.new("L", (olcham * 4, olcham * 4), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, olcham * 4 - 1, olcham * 4 - 1), radius=round(olcham * 4 * RADIUS), fill=255
        )
        fon.putalpha(mask.resize((olcham, olcham), Image.Resampling.LANCZOS))
    return fon


def _markazda(nom: str, olcham: int) -> Image.Image:
    """Belgi shaffof kvadratning butun enida, vertikal markazda."""
    fon = Image.new("RGBA", (olcham, olcham), (0, 0, 0, 0))
    belgi = _belgi(nom, olcham)
    fon.alpha_composite(belgi, (0, (olcham - belgi.height) // 2))
    return fon


def _agent_logo() -> Image.Image:
    im = _master("icon-navy.png")
    return im.resize((round(AGENT_BALANDLIK * im.width / im.height), AGENT_BALANDLIK), Image.Resampling.LANCZOS)


#: hosila fayl -> uni yasaydigan funksiya
HOSILALAR: dict[str, Callable[[], Image.Image]] = {
    "frontend/src/icons/icon-192.png": lambda: _plita(192, 0.78, yumaloq=True),
    "frontend/src/icons/icon-512.png": lambda: _plita(512, 0.78, yumaloq=True),
    "frontend/src/icons/icon-192-maskable.png": lambda: _plita(192, 0.66, yumaloq=False),
    "frontend/src/icons/icon-512-maskable.png": lambda: _plita(512, 0.66, yumaloq=False),
    "frontend/src/icons/apple-touch-icon.png": lambda: _plita(180, 0.78, yumaloq=False),
    "frontend/public/assets/images/favicon.png": lambda: _markazda("icon-gold.png", 256),
}
ICO = "bridge-agent/mebelix.ico"
AGENT = "bridge-agent/agent.py"
_B64_BLOK = re.compile(r"(_LOGO_B64 = \(\n)(.*?)(\n\))", re.S)


def _png(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _farq(kutilgan: Image.Image, bor: Image.Image) -> str | None:
    """Dekodlangan RGBA piksellar aynan teng bo'lmasa — sababi, aks holda None."""
    a, b = kutilgan.convert("RGBA"), bor.convert("RGBA")
    if a.size != b.size:
        return f"o'lcham {b.size}, kutilgan {a.size}"
    if a.tobytes() == b.tobytes():
        return None
    # `alpha_only=False`: sukut bo'yicha RGBA da faqat alfa qaraladi va shaffofligi
    # bir xil, rangi boshqa piksel sohadan tushib qolardi (hukm yuqorida baribir baytda)
    return f"piksellar farq qiladi, soha {ImageChops.difference(a, b).getbbox(alpha_only=False)}"


def _agent_b64() -> str:
    m = _B64_BLOK.search((R / AGENT).read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"{AGENT}: `_LOGO_B64 = (...)` bloki topilmadi")
    return "".join(re.findall(r'"([^"]*)"', m.group(2)))


def _ico() -> Image.Image:
    return _markazda("icon-navy.png", 256)


def _ico_farq() -> str | None:
    if not (R / ICO).exists():
        return "fayl yo'q"
    buf = io.BytesIO()
    _ico().save(buf, format="ICO", sizes=ICO_OLCHAMLAR)
    buf.seek(0)
    kutilgan = IcoImagePlugin.IcoFile(buf)
    with (R / ICO).open("rb") as f:
        ico = IcoImagePlugin.IcoFile(f)
        if sorted(ico.sizes()) != ICO_OLCHAMLAR:
            return f"o'lchamlar {sorted(ico.sizes())}"
        # HAR KADR: faqat 256 solishtirilsa, Explorer'dagi 16x16 ni kimdir o'zgartirsa
        # sezilmasdi. Kutilgani — generatorning o'zi yozadigan ICO ning shu kadri
        # (kichik kadrlarni Pillow 256 dan yasaydi).
        farqli = [f"{o[0]}px" for o in ICO_OLCHAMLAR if _farq(kutilgan.getimage(o), ico.getimage(o))]
    return f"{', '.join(farqli)} kadrida piksellar farq qiladi" if farqli else None


def _nusxa_farq(nusxa: str, master: str) -> str | None:
    if (R / nusxa).exists() and (R / nusxa).read_bytes() == (R / master).read_bytes():
        return None
    return f"{master} dan farq qiladi"


def _hosila_farq(yol: str, yasa: Callable[[], Image.Image]) -> str | None:
    return _farq(yasa(), Image.open(R / yol)) if (R / yol).exists() else "fayl yo'q"


def _agent_farq() -> str | None:
    sabab = _farq(_agent_logo(), Image.open(io.BytesIO(base64.b64decode(_agent_b64()))))
    return f"_LOGO_B64: {sabab}" if sabab else None


def farqlar() -> dict[str, str]:
    """Masterga mos KELMAGAN aktivlar: yo'l -> sabab. Bittasi bitta qator."""
    tekshiruvlar: list[tuple[str, Callable[[], str | None]]] = [
        *((n, partial(_nusxa_farq, n, m)) for n, m in NUSXALAR.items()),
        *((y, partial(_hosila_farq, y, f)) for y, f in HOSILALAR.items()),
        (ICO, _ico_farq),
        (AGENT, _agent_farq),
    ]
    out: dict[str, str] = {}
    for yol, tekshir in tekshiruvlar:
        try:
            sabab = tekshir()
        except (OSError, SyntaxError, ValueError) as e:
            # Buzuq fayl ham FARQ: `--write` uni qayta yozib tuzatishi kerak, yiqilmasligi.
            # Pillow'da o'qilmaydigan/kesilgan rasm — OSError, ICO emas — SyntaxError,
            # base64 buzuq — binascii.Error (ValueError).
            sabab = f"o'qib bo'lmadi ({e})"
        if sabab:
            out[yol] = sabab
    return out


def yoz(farqli: set[str]) -> None:
    """Faqat farq qilganini yozadi: piksellari bir xil faylni boshqa OS'da qayta
    kodlash baytlarni o'zgartirib, ko'rinishi bir xil diff qoldirardi."""
    for nusxa, master in NUSXALAR.items():
        if nusxa in farqli:
            (R / nusxa).write_bytes((R / master).read_bytes())
    for yol, yasa in HOSILALAR.items():
        if yol in farqli:
            (R / yol).write_bytes(_png(yasa()))
    if ICO in farqli:
        _ico().save(R / ICO, format="ICO", sizes=ICO_OLCHAMLAR)
    if AGENT in farqli:
        b64 = base64.b64encode(_png(_agent_logo())).decode()
        satrlar = "\n".join(f'    "{b64[i : i + 96]}"' for i in range(0, len(b64), 96))
        manba = (R / AGENT).read_text(encoding="utf-8")
        # `newline="\n"`: Windows'da sukut bo'yicha butun fayl CRLF bo'lib yozilardi,
        # repo siyosati esa LF (`.gitattributes: * text=auto eol=lf`)
        (R / AGENT).write_text(
            _B64_BLOK.sub(lambda m: m.group(1) + satrlar + m.group(3), manba), encoding="utf-8", newline="\n"
        )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="nusxalar masterga mosmi (CI)")
    g.add_argument("--write", action="store_true", help="masterdan farq qilgan nusxalarni qayta yasaydi")
    yozilsin = p.parse_args().write
    farq = farqlar()
    if yozilsin and farq:
        yoz(set(farq))
        farq = farqlar()
    for yol, sabab in farq.items():
        print(f"  FARQ  {yol}: {sabab}")
    jami = len(NUSXALAR) + len(HOSILALAR) + 2
    print(f"{jami - len(farq)}/{jami} brend aktivi masterga mos")
    if farq:
        print("Tuzatish: `cd backend && uv run python ../scripts/brand-assets.py --write` (design/ o'zgargach)")
    return 1 if farq else 0


if __name__ == "__main__":
    sys.exit(main())
