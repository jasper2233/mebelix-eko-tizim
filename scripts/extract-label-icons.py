"""GibSaw yorliq shablonidagi (`*.lbl`) ichki rasmlarni ajratib oladi.

`mebelix.lbl` — XML, rasmlari `imgdata="data:image/png;base64,…"` sifatida
ICHIGA yozilgan. `backend/app/assets/label-logo.png` va `label-icon-drill.png`
o'sha yerdan olingan, lekin qanday olingani hech qayerda qolmagan edi — bu
skript shu bo'shliqni yopadi va qolganini ham chiqaradi.

NOMLASH. Har rasm `<if condition="…">` ichida turadi va shart uning MA'NOSI:

    groove  — Пазование        paz
    drill   — Сверление        teshik (MESda ishlatiladi)
    mill    — Фрезерование     freza / radius
    rabbet  — chorak (falts)
    part.twodetails            detal ikki bo'lakdan

Shartsiz turgan rasm tartib raqami bilan yoziladi (`image-6.png` — yorliqdagi
monoxrom logotip).

ISHLATISH:

    uv run --with pillow python scripts/extract-label-icons.py \\
        "<mebelix.lbl>" design/label-icons

Chiqish papkasi ATAYLAB `design/` ostida: hozircha faqat `drill` ishlatiladi,
qolganiga ma'lumot manbai yo'q (`rabbet`, `twodetails`) yoki chekda allaqachon
boshqacha ko'rsatilgan (`groove`/`mill` — eskizdagi chiziq uslubi bilan).
Kerak bo'lganda shu yerdan `backend/app/assets/` ga ko'chiriladi.
"""

import base64
import re
import sys
from pathlib import Path

#: `<image …>` va undan OLDINGI eng yaqin `<if condition="…">`.
_RASM = re.compile(r'<image\b(?P<atr>[^>]*?)imgdata="data:image/(?P<tur>png|jpeg);base64,(?P<b64>[^"]+)"[^>]*>')
_SHART = re.compile(r'<if\b[^>]*?condition="(?P<nom>[^"]+)"[^>]*>')


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    lbl = Path(sys.argv[1])
    chiqish = Path(sys.argv[2])
    chiqish.mkdir(parents=True, exist_ok=True)
    matn = lbl.read_text(encoding="utf-8", errors="replace")

    from PIL import Image

    n = 0
    for i, m in enumerate(_RASM.finditer(matn), 1):
        # O'CHIRILGAN rasm shablonning o'zida chizilmaydi — `mebelix.lbl` da
        # bunday bitta bor va u BOSHQA firmaning belgisi (shablon qayerdandir
        # ko'chirilgan). Uni repoga olib kelishning ma'nosi yo'q.
        if 'enable="false"' in m.group("atr"):
            continue
        # Eng yaqin ochilgan shart — rasmning ma'nosi. `grafic_images` butun
        # blokni o'rab turadi, ya'ni u ma'no emas: undan oldingisi olinadi.
        shartlar = [s.group("nom") for s in _SHART.finditer(matn, 0, m.start())]
        shart = next((s for s in reversed(shartlar) if s != "grafic_images"), "")
        nom = re.sub(r"[^a-z0-9]+", "-", shart.lower()).strip("-") or f"image-{i}"
        kengaytma = "png" if m.group("tur") == "png" else "jpg"
        yol = chiqish / f"{nom}.{kengaytma}"
        xom = base64.b64decode(m.group("b64"))
        yol.write_bytes(xom)
        with Image.open(yol) as im:
            olcham = im.size
        print(f"  {yol.name:20} {str(olcham):12} {len(xom) // 1024:4} KB   <- if({shart or '—'})")
        n += 1
    print(f"{n} rasm -> {chiqish}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
