"""Bazis katalogidan material -> HAQIQIY rang va tekstura jadvalini yasaydi.

Chiqish: `frontend/src/components/Bazis/matRang.gen.ts` (qo'lda tahrirlanmaydi)
va `frontend/public/assets/tex/*.jpg` (teksturalar, 512-1024 px).

TEKSTURA. Rasmida naqsh bor HAR material (yog'och tolasi, marmar tomiri,
shagren, beton) rasmning o'zi bilan chiziladi; tekis rasm (`Benzin`, `Кашемир`
— qo'shni piksellar farqi ~0) o'rtacha rangi bilan. Katalogda rang belgilangan
(`UseColor = 1`) material — tekstura nomi yozilgan bo'lsa ham — RANG bilan:
`LMDF BIR TOMON GOLI` oq, `110011.jpg` o'rtachasi emas (ΔE 12). Katalogda yo'q
nom uchun papkada dekor nomi AYNAN mos rasm qidiriladi (`_fayl_nomidan`).

Rasmlarning ko'pi ulanuvchan tayl EMAS, oddiy foto: takrorlanganda tayl
chegarasida qattiq chiziq qoladi. Har o'q alohida o'lchanadi (`ULANUVCHAN`) va
chokli o'qda brauzer rasmni ko'zgu kabi aks ettirib ulaydi (`scene.ts`).

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
from typing import NamedTuple

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
#: Tekstura rasmlari shu yerga (nginx ularni o'zgarmas statik aktiv sifatida beradi)
TEX_PAPKA = "frontend/public/assets/tex"
#: Rasmning eng uzun tomoni, px: aniq naqshli (yog'och tolasi, marmar — L* std
#: >= `NAQSH`) — 1024, qolgani (shagren, beton) — 512. 1000 mm taylda 512 px ~2 mm
#: ga bir piksel: eshik yaqindan ko'rilganda tola yuvilib ketardi.
TEX_PX, TEX_PX_MAYDA, NAQSH = 1024, 512, 4.0
#: Qo'shni piksellarning o'rtacha farqi (256 px nusxada, kulrang 0-255). Undan
#: past rasm TEKIS — dispersiyasi bo'lsa ham u fotoning yorug'lik dog'idan
#: (`Фон Мокко` std 1.4, farq 0.1): takrorlansa har taylda dog' chiqardi, rang
#: yetarli. Tekislari 0.0-0.5, eng nozik naqsh (`Мрамор Оникс`, shagren) 0.9 dan.
NAQSH_FARQ = 0.7
#: Shundan ingichka tayl (mm) — kromka lentasi (1000x20): u chizilmaydi.
MIN_TAYL = 50
#: Chok nisbati — qarama-qarshi chetlar farqi / qo'shni piksellar farqi, har o'q
#: uchun alohida. Shundan past o'q ULANADI (`*_diffuseOriginal.png` 0.9-1.6),
#: yuqorisi — oddiy FOTO (`110026` dub vatan bo'yiga 4.2, `110042` 7.8): takrorlanganda
#: tayl chegarasida qattiq chiziq qolardi. Bunday o'qda rasm KO'ZGU kabi aks
#: ettirib ulanadi — chet o'zi bilan tutashadi, tola uzilmaydi.
ULANUVCHAN = 1.8


class Yozuv(NamedTuple):
    """Katalogdagi material: o'rtacha rang va (naqshi bo'lsa) tekstura
    `[fayl, tayl U mm, tayl V mm, burchak°, tola U bo'ylab, U aks, V aks]`."""

    rang: str
    tex: tuple[str, float, float, float, int, int, int] | None


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


def _tex_yol(tex: str, ildiz: str, fayllar: dict[str, str]) -> str | None:
    """Katalogdagi yo'l (`AKRIL\\mokriy.jpg`, tekstura papkasiga nisbatan) —
    avval TO'LIQ yo'l bilan, topilmasa nomi bilan (9 ta nom ikki papkada bor)."""
    toliq = os.path.join(ildiz, *tex.replace("\\", "/").split("/"))
    if os.path.isfile(toliq):
        return toliq
    nom = os.path.basename(tex.replace("\\", "/")).lower()
    return fayllar.get(nom) or fayllar.get(os.path.splitext(nom)[0])


class Rasm(NamedTuple):
    rang: str
    #: Naqsh kuchi — L* std
    std: float
    #: Qo'shni piksellar farqi (kattasi) — `NAQSH_FARQ` bilan solishtiriladi
    farq: float
    #: Chok nisbati: chap-o'ng chetlar (U o'qi) va past-yuqori chetlar (V o'qi)
    chok_u: float
    chok_v: float
    #: Tola rasm ENI (U) bo'ylab — stoleshnitsa fotolari yotiq; aks holda bo'yi (V)
    tola_u: bool
    eni: int
    boyi: int


def _tex_rang(yol: str) -> Rasm | None:
    """Tekstura rasmining o'lchovlari: o'rtacha rang, naqsh kuchi, ulanuvchanligi
    va tola yo'nalishi. Tola — gradient energiyasidan: tik tolali yog'ochda
    gorizontal farqlar katta (`110026`: 8.2 ga 3.3), yotiq stoleshnitsada teskari
    (`N 111 Дуб Вотан`: 3.2 ga 7.1)."""
    from PIL import Image, ImageStat

    try:
        asl = Image.open(yol)
        eni, boyi = asl.size
        im = asl.convert("RGB")
        im.thumbnail((256, 256))
    except Exception:
        return None
    r, g, b = ImageStat.Stat(im).mean

    def yorqinlik(px: tuple[int, int, int]) -> float:
        lin = [(c / 255) / 12.92 if c <= 10 else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in px]
        y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
        return 116 * (y ** (1 / 3) if y > 0.008856 else 7.787 * y + 16 / 116) - 16

    rgb = im.tobytes()
    ls = [yorqinlik((rgb[i], rgb[i + 1], rgb[i + 2])) for i in range(0, len(rgb), 3)]
    ortacha = sum(ls) / len(ls)
    std = (sum((v - ortacha) ** 2 for v in ls) / len(ls)) ** 0.5

    kul = im.convert("L")
    w, h = kul.size
    px = kul.tobytes()

    def p(x: int, y: int) -> int:
        return px[y * w + x]

    gx = sum(abs(p(x + 1, y) - p(x, y)) for y in range(h) for x in range(w - 1)) / (h * (w - 1))
    gy = sum(abs(p(x, y + 1) - p(x, y)) for y in range(h - 1) for x in range(w)) / ((h - 1) * w)
    chok_u = sum(abs(p(w - 1, y) - p(0, y)) for y in range(h)) / h / max(gx, 1e-6)
    chok_v = sum(abs(p(x, h - 1) - p(x, 0)) for x in range(w)) / w / max(gy, 1e-6)
    rang = f"#{round(r):02x}{round(g):02x}{round(b):02x}"
    return Rasm(rang, std, max(gx, gy), chok_u, chok_v, gy > 1.3 * gx, eni, boyi)


def _tekstura(
    yol: str, o: Rasm, tayl: tuple[float, float], burchak: float
) -> tuple[str, float, float, float, int, int, int]:
    """MAT_TEX yozuvi. Tayl KATTALASHTIRILMAYDI: rasm butun varaqqa (2800 mm)
    yoyilsa chok yo'qolardi, lekin `110026` (600x800 px) dagi 5-6 taxta chizig'i
    ~380 mm li bo'lib, tola 2.8 barobar yo'g'on chiqardi. Uzun tomoni katalogdagi
    taylniki, qisqasi rasm nisbatidan: katalogda 215/240 yozuvda o'lcham andozaviy
    1000x1000 — rasmga qaralmagan, nisbatsiz 600x800 rasm eniga 1.33 barobar cho'zilardi."""
    k = max(tayl) / max(o.eni, o.boyi)
    px = TEX_PX if o.std >= NAQSH else TEX_PX_MAYDA
    return (
        _tex_fayl(yol, px),
        round(o.eni * k, 1),
        round(o.boyi * k, 1),
        burchak,
        int(o.tola_u),
        int(o.chok_u > ULANUVCHAN),
        int(o.chok_v > ULANUVCHAN),
    )


def _tex_fayl(yol: str, px: int) -> str:
    """Rasmni brauzerga tayyorlaydi: eng uzun tomoni `px`, JPEG q80, nomi —
    mazmunining xeshi (Kirill nomlar va kesh muammosisiz). Asllari 1200-4096 px,
    ba'zilari 3-5 MB li PNG — ularni hech qachon jo'natmaymiz."""
    import hashlib
    import io

    from PIL import Image

    im = Image.open(yol).convert("RGB")
    im.thumbnail((px, px), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=80, optimize=True, progressive=True)
    data = buf.getvalue()
    nom = hashlib.sha1(data).hexdigest()[:12] + ".jpg"
    papka = Path(__file__).resolve().parents[1] / TEX_PAPKA
    papka.mkdir(parents=True, exist_ok=True)
    (papka / nom).write_bytes(data)
    return nom


def _param_rang(v: object) -> str | None:
    if v is None:
        return None
    n = int(v)  # type: ignore[call-overload]
    if n == ANDOZA or n < 0:
        return None
    return f"#{n & 255:02x}{(n >> 8) & 255:02x}{(n >> 16) & 255:02x}"


def _katalog(fdb_yol: str, tex_yol: str) -> dict[str, Yozuv]:
    """`PARAM_n` ma'nosi fayllarning Undo'sidagi Bazis `Mt` yozuvlari bilan
    solishtirib aniqlangan: 1 — rang (Delphi TColor), 2 — `UseColor` (1 bo'lsa
    tekstura EMAS, rang chiziladi), 12 x 13 — bitta tayl, mm (215/240 yozuvda
    1000 x 1000, stoleshnitsada 600 x 3000), 14 — burchak, gradus."""
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
    cur.execute(
        "select m.NAME_MAT, t.PARAM_1, t.PARAM_2, t.NAME_TEXTURE, t.PARAM_12, t.PARAM_13, t.PARAM_14, tm.NAME_TYPE"
        " from MATERIAL m join PARAM_TEXTURE t on t.ID_M=m.ID_M"
        " left join GROUP_MATERIAL g on g.ID_GRM=m.ID_GRM left join TYPE_MATERIAL tm on tm.ID_TM=g.ID_TM"
    )
    kat: dict[str, Yozuv] = {}
    for nom, param, faqat_rang, tex, eni, boyi, burchak, turi in cur.fetchall():
        k = norm(str(nom))
        if not k or k in kat:
            continue
        tex = (tex or "").strip()
        yol = _tex_yol(tex, tex_yol, fayllar) if tex and not faqat_rang else None
        olcham = _tex_rang(yol) if yol else None
        rang = olcham.rang if olcham else _param_rang(param)
        if not rang:
            continue
        tayl = (float(eni or 1000), float(boyi or 1000))
        # Kromka (katalogda `Кромочный материал`, 33 ta) panel sifatida chizilmaydi —
        # uning rasmi faqat bekorga yuklanardi. Rangi qoladi.
        kromka = "кромоч" in str(turi).lower()
        if yol and olcham and olcham.farq >= NAQSH_FARQ and min(tayl) >= MIN_TAYL and not kromka:
            kat[k] = Yozuv(rang, _tekstura(yol, olcham, tayl, float(burchak or 0)))
        else:
            kat[k] = Yozuv(rang, None)
    return kat


#: Fayl nomi bo'yicha moslashda e'tiborga olinmaydigan so'zlar — plita turi, dekor emas
_TUR_SOZI = frozenset({"ldsp", "lmdf", "mdf", "akril", "лдсп", "лмдф", "мдф", "акрил"})


def _dekor(nom: str) -> frozenset[str]:
    return frozenset(norm(nom).split()) - _TUR_SOZI


def _fayl_indeksi(tex_yol: str) -> dict[frozenset[str], str]:
    """Rasm fayllari dekor so'zlari bo'yicha (kromka papkasisiz)."""
    ind: dict[frozenset[str], str] = {}
    for p in sorted(glob.glob(os.path.join(tex_yol, "**", "*"), recursive=True)):
        if "kromka" in p.lower() or os.path.splitext(p)[1].lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        if d := _dekor(Path(p).stem):
            ind.setdefault(d, p)
    return ind


def _fayl_nomidan(nom: str, indeks: dict[frozenset[str], str]) -> Yozuv | None:
    """Katalogda YO'Q material uchun tekstura — papkada dekor nomi AYNAN mos
    fayl bo'lsa (`LDSP dub beliy` -> `dub beliy.jpg`). Qisman moslik olinmaydi:
    `ASTANA MATIVIY` -> `sosna astana` kabi taxmin boshqa dekorni chizardi.
    Tayl andozaviy 1000 mm — katalogdagi 215/240 yozuvdagidek."""
    p = indeks.get(_dekor(nom))
    o = _tex_rang(p) if p else None
    if not (p and o):
        return None
    return Yozuv(o.rang, _tekstura(p, o, (1000.0, 1000.0), 0.0) if o.farq >= NAQSH_FARQ else None)


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
    # Windows konsoli cp1252: Kirill material nomi chop etilganda yiqilardi
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    kat = _katalog(sys.argv[1], sys.argv[2])
    jadval = dict(kat)
    hisob: collections.Counter[str] = collections.Counter()

    if len(sys.argv) > 3:
        indeks = _fayl_indeksi(sys.argv[2])
        for nom, n in _ishlatilish(sys.argv[3]).items():
            k = norm(nom)
            if k in jadval:
                hisob["aniq"] += n
                continue
            a = set(k.split())
            eng, ball = None, 0.0
            for kk, yozuv in kat.items():
                b = set(kk.split())
                if not (a and b):
                    continue
                j = len(a & b) / len(a | b)
                if b <= a and len(b) >= 2:
                    j += 0.35
                if j > ball:
                    eng, ball = yozuv, j
            if eng and ball >= BOSAGA:
                jadval[k] = eng
                hisob["taxminiy"] += n
            elif fayl := _fayl_nomidan(nom, indeks):
                jadval[k] = fayl
                hisob["fayl nomi"] += n
                print(f"  fayl nomidan: {nom!r} ({n} panel)")
            else:
                hisob["topilmadi"] += n

    qamrov = ""
    if hisob:
        jami = sum(hisob.values())
        qopl = jami - hisob["topilmadi"]
        qamrov = (
            " *\n"
            f" * Qamrov (o'lchangan): {qopl} / {jami} panel = {qopl * 100 // jami}%"
            f" — {hisob['aniq']} aniq,\n"
            f" * {hisob['taxminiy']} taxminiy moslik, {hisob['fayl nomi']} rasm fayli nomidan. Qolgani\n"
            " * `RANGLAR` regex jadvaliga tushadi: asosan `zamena material` kabi katalogda\n"
            " * umuman yo'q nomlar.\n"
        )
    satrlar = "\n".join(
        f"  {json.dumps(k, ensure_ascii=False)}: {json.dumps(v.rang)}," for k, v in sorted(jadval.items())
    )
    tex_satrlar = "\n".join(
        f"  {json.dumps(k, ensure_ascii=False)}: {json.dumps(list(v.tex))}," for k, v in sorted(jadval.items()) if v.tex
    )
    # Papka generatorniki: jadvalda qolmagan rasm o'chiriladi, aks holda eskisi
    # repoda va nginx obrazida abadiy qolardi.
    kerak = {v.tex[0] for v in jadval.values() if v.tex}
    for f in (Path(__file__).resolve().parents[1] / TEX_PAPKA).glob("*.jpg"):
        if f.name not in kerak:
            f.unlink()
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
        "}\n\n"
        "/** Naqshli materialning teksturasi: `[fayl, tayl eni mm, tayl bo'yi mm, burchak°,\n"
        " * tola eni bo'ylab, eni bo'ylab aks, bo'yi bo'ylab aks]` (0/1). Fayl —\n"
        f" * `{TEX_PAPKA.removeprefix('frontend/public')}/` ichida. Tekisi (qo'shni piksel farqi < {NAQSH_FARQ:g})\n"
        " * bu yerda yo'q: unga `MAT_RANG` dagi o'rtacha rang yetarli. */\n"
        "export const MAT_TEX: Record<\n"
        "  string,\n"
        "  [string, number, number, number, number, number, number]\n"
        "> = {\n"
        f"{tex_satrlar}\n"
        "}\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"{len(jadval)} yozuv ({len(kerak)} tekstura) -> {CHIQISH}")
    for k, v in hisob.most_common():
        print(f"  {k:10} {v:6} panel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
