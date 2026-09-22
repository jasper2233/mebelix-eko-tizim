"""Bazis katalogidan material -> HAQIQIY rang jadvalini yasaydi.

Chiqish: `frontend/src/components/Bazis/matRang.gen.ts` (qo'lda tahrirlanmaydi).

NEGA KERAK. Rang ilgari faqat material NOMIDAN, regex jadvali bilan taxmin
qilinardi. 460 ta haqiqiy modelda o'lchandi: teksturasi bor materiallarning
28% i sezilarli xato rang olardi — `LDSP INTERNO ZOLOTA` oltin chiqardi
(aslida oq marmar), `LDSP KASPIY TYOMNIY` jigarrang chiqardi (aslida ko'kish
kulrang), `LMDF AZIYA` kulrang chiqardi (aslida to'q qizil-jigar).

RANG QAYERDAN. Birinchi navbatda teksturaning o'rtacha rangi; teksturasiz
yozuvlarda katalogdagi `PARAM_1` (Delphi `TColor`, past bayt — QIZIL).
`PARAM_1 = 8369910` ANDOZA: 108 yozuvdan 107 tasida tekstura ham bor, ya'ni
qiymatning o'zi hech narsa anglatmaydi. 0 (qora) va 16777215 (oq) esa
HAQIQIY — teksturasiz yozuvlarda ularning hammasi rostdan qora yoki oq buyum
(`1-19 qora`, `LDSP OQ GLYANETS`).

NOM MOSLASHI. Texnolog Bazisda plita o'lchamini va yetkazuvchini nomga
qo'shadi (`LDSP DUB VOTAN 5.03 kv.  Khatdekor`), katalogda esa `LDSP DUB
VATAN MATIVIY` turadi. Shuning uchun nom normallashtiriladi va topilmagani
so'zlar kesishuvi bo'yicha moslanadi — natija SHU YERDA, generatsiya paytida
hal qilinadi, brauzerda taxminiy moslash yo'q.

ISHLATISH (katalog o'zgarganda QO'LDA):

    FBCLIENT_DLL=".../BazisFirebird 2.5/bin/fbclient.dll" uv run \\
        --python cpython-3.12-windows-x86 --with fdb --with pillow \\
        python scripts/bazis-material-colors.py "<BAZA.FDB>" "<textura/>" ["<b3d/>"]

32 bitli Python SHART: `fbclient.dll` Firebird 2.5 bilan keladi va u 32 bitli.
Uchinchi argument — haqiqiy `.b3d` fayllar papkasi; berilsa, katalogda AYNAN
topilmagan nomlar ham moslanadi va qamrov o'lchanadi.
"""

import collections
import glob
import json
import os
import re
import sys
from pathlib import Path

#: Nomdagi "shovqin": plita kvadraturasi, gabarit, qalinlik, yetkazuvchi.
SHOVQIN = [
    r"\d+[.,]\d+\s*kv\.?",
    r"\d{3,4}\s*[xх*]\s*\d{3,4}(\s*[xх*]\s*\d+)?(\s*mm)?",
    r"\(\s*\d+\s*mm\s*\)",
    r"\b\d+\s*mm\b",
    r"khatde[ck]or",
    r"kronospan",
    r"xitoy",
    r"mestniy",
    r"местный",
    r"\bagt\b",
    r"\bbir tomon\b",
]
#: Bir xil dekorning ikki xil yozilishi (haqiqiy ma'lumotdan olingan).
ALMASH = [
    (r"votan", "vatan"),
    (r"mokrik", "mokriy"),
    (r"beliy?", "beli"),
    (r"tiilla", "tilla"),
    (r"glyans", "glyanets"),
    (r"mativiy", "matviy"),
]
#: "Rang belgilanmagan" andozasi.
ANDOZA = 8369910
#: Shundan past moslik ishonchsiz — jadvalga kirmaydi.
BOSAGA = 0.55

CHIQISH = "frontend/src/components/Bazis/matRang.gen.ts"


def norm(s: str) -> str:
    """`model.ts` dagi `normMat` bilan QO'LDA oynalangan — birini
    o'zgartirsang ikkinchisini ham."""
    s = s.lower().strip()
    for naqsh in SHOVQIN:
        s = re.sub(naqsh, " ", s)
    for a, b in ALMASH:
        s = re.sub(a, b, s)
    s = re.sub(r"[^a-z0-9а-яё ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tex_rang(tex: str, fayllar: dict[str, str]) -> str | None:
    from PIL import Image, ImageStat

    nom = os.path.basename(tex).lower()
    yol = fayllar.get(nom) or fayllar.get(os.path.splitext(nom)[0])
    if not yol:
        return None
    try:
        im = Image.open(yol).convert("RGB")
        im.thumbnail((96, 96))
        r, g, b = ImageStat.Stat(im).mean
    except Exception:
        return None
    return f"#{round(r):02x}{round(g):02x}{round(b):02x}"


def _param_rang(v: object) -> str | None:
    if v is None:
        return None
    n = int(v)  # type: ignore[call-overload]
    if n == ANDOZA or n < 0:
        return None
    return f"#{n & 255:02x}{(n >> 8) & 255:02x}{(n >> 16) & 255:02x}"


def _katalog(fdb_yol: str, tex_yol: str) -> dict[str, str]:
    import fdb

    fayllar: dict[str, str] = {}
    for p in glob.glob(os.path.join(tex_yol, "**", "*"), recursive=True):
        if os.path.isfile(p):
            nom = os.path.basename(p).lower()
            fayllar.setdefault(nom, p)
            fayllar.setdefault(os.path.splitext(nom)[0], p)

    con = fdb.connect(
        database=fdb_yol,
        user="SYSDBA",
        password="masterkey",
        fb_library_name=os.environ.get("FBCLIENT_DLL") or None,
        charset="UTF8",
    )
    cur = con.cursor()
    cur.execute("select m.NAME_MAT, t.PARAM_1, t.NAME_TEXTURE from MATERIAL m join PARAM_TEXTURE t on t.ID_M=m.ID_M")
    kat: dict[str, str] = {}
    for nom, param, tex in cur.fetchall():
        k = norm(str(nom))
        if not k or k in kat:
            continue
        rang = _tex_rang(str(tex).strip(), fayllar) if (tex or "").strip() else None
        rang = rang or _param_rang(param)
        if rang:
            kat[k] = rang
    return kat


def _ishlatilish(b3d_yol: str) -> collections.Counter[str]:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from app.services.bazis.parser import read_b3d

    ish: collections.Counter[str] = collections.Counter()
    for f in glob.glob(os.path.join(b3d_yol, "**", "*.b3d"), recursive=True):
        try:
            parsed = read_b3d(Path(f).read_bytes())
        except Exception:
            continue
        for p in parsed.panels:
            if p.mat_name:
                ish[p.mat_name] += 1
    return ish


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    kat = _katalog(sys.argv[1], sys.argv[2])
    jadval = dict(kat)
    hisob: collections.Counter[str] = collections.Counter()

    if len(sys.argv) > 3:
        for nom, n in _ishlatilish(sys.argv[3]).items():
            k = norm(nom)
            if k in jadval:
                hisob["aniq"] += n
                continue
            a = set(k.split())
            eng, ball = None, 0.0
            for kk, rang in kat.items():
                b = set(kk.split())
                if not (a and b):
                    continue
                j = len(a & b) / len(a | b)
                if b <= a and len(b) >= 2:
                    j += 0.35
                if j > ball:
                    eng, ball = rang, j
            if eng and ball >= BOSAGA:
                jadval[k] = eng
                hisob["taxminiy"] += n
            else:
                hisob["topilmadi"] += n

    qamrov = ""
    if hisob:
        jami = sum(hisob.values())
        qopl = hisob["aniq"] + hisob["taxminiy"]
        qamrov = (
            " *\n"
            f" * Qamrov (o'lchangan): {qopl} / {jami} panel = {qopl * 100 // jami}%"
            f" — {hisob['aniq']} aniq,\n"
            f" * {hisob['taxminiy']} taxminiy moslik. Qolgani `RANGLAR` regex jadvaliga\n"
            " * tushadi: asosan `zamena material` kabi katalogda umuman yo'q nomlar.\n"
        )
    satrlar = "\n".join(f"  {json.dumps(k, ensure_ascii=False)}: {json.dumps(v)}," for k, v in sorted(jadval.items()))
    chiqish = Path(__file__).resolve().parents[1] / CHIQISH
    chiqish.write_text(
        "/** GENERATSIYA QILINGAN — QO'LDA TAHRIRLANMAYDI.\n"
        " *\n"
        " * Manba: Bazis katalogi (`BAZA 1.FDB`) + tekstura rasmlari.\n"
        " * Yangilash: `scripts/bazis-material-colors.py` — nega va qanday, o'sha yerda.\n"
        " * Kalit — normallashtirilgan material nomi (`model.ts: normMat`).\n"
        f"{qamrov}"
        " */\n\n"
        "export const MAT_RANG: Record<string, string> = {\n"
        f"{satrlar}\n"
        "}\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{len(jadval)} yozuv -> {CHIQISH}")
    for k, v in hisob.most_common():
        print(f"  {k:10} {v:6} panel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
