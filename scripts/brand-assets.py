"""Brend aktivlarining YAGONA manbasi — `design/logo/`. Qolgan hamma nusxa shundan.

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
  `.ico`, agent ichidagi base64. Tekshiruv — KO'RINISH: PNG baytlari Pillow/zlib
  versiyasiga qarab o'zgaradi, ko'rinish esa yo'q. Chidam (`_CHIDAM`) sub-piksel
  resample farqini o'tkazadi, rang/o'lcham/joy o'zgarishini ushlaydi.

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
from pathlib import Path

from PIL import IcoImagePlugin, Image, ImageChops, ImageDraw, ImageFilter

R = Path(__file__).resolve().parents[1]
MASTER = R / "design" / "logo"

NAVY_TEPA = (0x2F, 0x49, 0x6E)
NAVY_PAST = (0x16, 0x23, 0x3A)
#: `any` ikonkaning burchak radiusi — mavjud ikonkadan o'lchangan (512 da 92 px).
RADIUS = 0.18
ICO_OLCHAMLAR = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
#: Agent oynasi va tray uchun balandlik (`agent.py` shuni kutadi).
AGENT_BALANDLIK = 112
#: Ko'rinish farqi chidami — ikkala rasm 1 px Gauss bilan yumshatilgach kanal farqining
#: O'RTACHASI va 99.5-PERSENTILI. Kalibrlangan: hozirgi hosilalar o'rtacha <= 2.0,
#: p99.5 <= 49 (asl PWA ikonkalar boshqa vositada yasalgan, belgi cheti sub-piksel
#: siljigan — ko'z ilg'amaydi). Sun'iy buzilishlar: belgi 5% katta, 4 px siljigan,
#: rangi boshqa, fon yassi, burchak yumaloqmas — o'rtacha >= 6.4, p99.5 >= 162; eng
#: yengili, BUTUN ikonka 16% siqilgani — o'rtacha 2.9, lekin p99.5 108. Shuning uchun
#: p99.5 chegarasi 49 bilan 108 ning o'rtasida.
_CHIDAM = (4.0, 80)

#: nusxa -> master (bayt-baytiga)
NUSXALAR = {
    "frontend/public/assets/logo/logo-gold.png": "logo-gold.png",
    "frontend/public/assets/logo/logo-navy.png": "logo-navy.png",
    "frontend/public/assets/logo/icon-navy.png": "icon-navy.png",
    "backend/app/assets/logo-black.png": "logo-black.png",
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


def _farq(a: Image.Image, b: Image.Image) -> str | None:
    """Ko'rinish farqi chidamdan oshsa — sababi, aks holda None."""
    a, b = a.convert("RGBA"), b.convert("RGBA")
    if a.size != b.size:
        return f"o'lcham {b.size}, kutilgan {a.size}"
    d = ImageChops.difference(a.filter(ImageFilter.GaussianBlur(1)), b.filter(ImageFilter.GaussianBlur(1)))
    r, g, k, al = d.split()
    # har piksel uchun to'rt kanal farqining eng kattasi, so'ng uning taqsimoti
    hist = ImageChops.lighter(ImageChops.lighter(r, g), ImageChops.lighter(k, al)).histogram()
    jami = sum(hist)
    ortacha = sum(i * n for i, n in enumerate(hist)) / jami
    yigindi, p995 = 0, 255
    for i, n in enumerate(hist):
        yigindi += n
        if yigindi >= jami * 0.995:
            p995 = i
            break
    if ortacha >= _CHIDAM[0] or p995 >= _CHIDAM[1]:
        return f"ko'rinish farqi: o'rtacha {ortacha:.1f}, p99.5 {p995} (chidam {_CHIDAM[0]} / {_CHIDAM[1]})"
    return None


def _agent_b64() -> str:
    m = _B64_BLOK.search((R / AGENT).read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"{AGENT}: `_LOGO_B64 = (...)` bloki topilmadi")
    return "".join(re.findall(r'"([^"]*)"', m.group(2)))


def tekshir() -> list[str]:
    xatolar: list[str] = []
    for nusxa, master in NUSXALAR.items():
        if (R / nusxa).read_bytes() != (MASTER / master).read_bytes():
            xatolar.append(f"{nusxa}: design/logo/{master} dan farq qiladi")
    for yol, yasa in HOSILALAR.items():
        sabab = _farq(yasa(), Image.open(R / yol))
        if sabab:
            xatolar.append(f"{yol}: {sabab}")
    buf = io.BytesIO()
    _markazda("icon-navy.png", 256).save(buf, format="ICO", sizes=ICO_OLCHAMLAR)
    buf.seek(0)
    kutilgan = IcoImagePlugin.IcoFile(buf)
    with (R / ICO).open("rb") as f:
        ico = IcoImagePlugin.IcoFile(f)
        if sorted(ico.sizes()) != ICO_OLCHAMLAR:
            xatolar.append(f"{ICO}: o'lchamlar {sorted(ico.sizes())}")
        else:
            # HAR KADR: faqat 256 solishtirilsa, Explorer'dagi 16x16 ni kimdir o'zgartirsa
            # sezilmasdi. Kutilgani — generatorning o'zi yozadigan ICO ning shu kadri
            # (kichik kadrlarni Pillow 256 dan yasaydi). Mavjud fayl hamma kadrda chidam
            # ichida: o'rtacha <= 2.7, p99.5 <= 43.
            for olcham in ICO_OLCHAMLAR:
                sabab = _farq(kutilgan.getimage(olcham), ico.getimage(olcham))
                if sabab:
                    xatolar.append(f"{ICO} ({olcham[0]}px): {sabab}")
    sabab = _farq(_agent_logo(), Image.open(io.BytesIO(base64.b64decode(_agent_b64()))))
    if sabab:
        xatolar.append(f"{AGENT} _LOGO_B64: {sabab}")
    return xatolar


def yoz() -> None:
    for nusxa, master in NUSXALAR.items():
        (R / nusxa).write_bytes((MASTER / master).read_bytes())
    for yol, yasa in HOSILALAR.items():
        (R / yol).write_bytes(_png(yasa()))
    _markazda("icon-navy.png", 256).save(R / ICO, format="ICO", sizes=ICO_OLCHAMLAR)
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
    g.add_argument("--write", action="store_true", help="hamma nusxani masterdan qayta yasaydi")
    if p.parse_args().write:
        yoz()
    xatolar = tekshir()
    for x in xatolar:
        print(f"  FARQ  {x}")
    jami = len(NUSXALAR) + len(HOSILALAR) + 2
    print(f"{jami - len(xatolar)}/{jami} brend aktivi masterga mos")
    if xatolar:
        print("Tuzatish: `cd backend && uv run python ../scripts/brand-assets.py --write` (design/logo/ o'zgargach)")
    return 1 if xatolar else 0


if __name__ == "__main__":
    sys.exit(main())
