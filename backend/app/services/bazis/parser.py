"""Bazis `.b3d` o'quvchi.

Format teskari muhandislik bilan aniqlangan (hujjat yo'q), 22 namunada
tekshirilgan. Fayl = `BZ85` + bo'limlar; har bo'lim `01 00 00 FF` ajratgichi va
siqilganlik bayrog'i bilan boshlanadi. Birinchi bo'lim — siqilmagan sarlavha
(mahsulot kodi, nomi, 256x256 PNG eskiz), ikkinchisi — zlib bilan siqilgan
model. Ikkala bo'lim ham bir xil o'zini tavsiflovchi daraxt kodlashida:

    kalitlar jadvali | kalit:u32 | bolalar:u32 | tur:u8 | qiymat

Ikki ishlab chiqarish qarori:

* **Iterativ**, rekursiv emas. Prototip 64 MB stek va `setrecursionlimit(10**6)`
  talab qilardi — daraxt 32 MB gacha chiqadi. Web ishchisida bu yaramaydi.
* **`Undo` da to'xtaymiz.** Tahrirlash tarixi fayl hajmining 13-90% ini
  egallaydi, undan hech narsa kerak emas, va 22 namunadan 6 tasida uning ichki
  tuzilmasi o'qilmaydi — to'xtamasak, o'sha 6 tasi buzilgan hisoblanardi.
  Panellar `Undo` dan OLDIN, `Model/Objs` ichida keladi.
"""

import math
import struct
import zlib
from typing import Any

from .models import BazisEdge, BazisPanel, BazisParseError, ParsedBazis

#: `Obj.Type` — panel. Bazisning o'z raqami.
_PANEL_TURI = 4002
#: Bo'lim boshi: ajratgich + siqilganlik bayrog'i (`00` xom, `01` zlib).
_AJRATGICH = b"\x01\x00\x00\xff"
#: Himoya: buzuq faylda cheksiz aylanmaslik uchun tugun chegarasi.
_MAX_TUGUN = 20_000_000
#: Ochilgan model uchun tom chegara. Namunalardagi eng kattasi 32 MB; zlib esa
#: nolli bufer bilan 1000:1 siqiladi, ya'ni chegarasiz 40 MB lik fayl 40 GB ga
#: ochilib butun backendni xotirasiz qoldirishi mumkin edi.
_MAX_OCHILGAN = 256 * 1024 * 1024
#: Model daraxtida bundan narisi kerak emas.
_TOXTASH = "Undo"
#: Yumaloq panelni taqribiy chizadigan ko'pburchak nuqtalari soni.
_AYLANA_NUQTA = 48
#: `Anim.AnimType`: 1 — ilgak (o'q atrofida burilish), 2 — surma (o'q bo'ylab siljish).
_ANIM_ILGAK, _ANIM_SURMA = 1, 2
#: Kontur segmentlari: turi -> uzunligi. 22 namunaning 2285 panelidagi 9675
#: segmentda o'lchandi: chiziq 9555 (98.8%), yoy 110 (1.1%), aylana 9 (0.09%).
#: `0x14` BIR marta uchradi (0.01%) va uzunligi noma'lum — shunday segment
#: chiqsa kontur shu yerda uziladi va ogohlantirish qaytadi.
_SEGMENT = {0x10: 33, 0x11: 25, 0x12: 50}
_AYLANA = 0x11


def _ochish(buf: bytes, pos: int) -> tuple[bytes, int]:
    """`pos` dagi bo'limni ochadi -> (tana, tanadagi boshlanish ofseti).

    Xom bo'limda tana — faylning o'zi (nusxa olinmaydi), shuning uchun ofset
    qaytariladi; siqilganida tana yangi bufer bo'ladi va ofset nol.
    """
    if buf[pos : pos + 4] != _AJRATGICH:
        raise BazisParseError("Bazis fayli tanilmadi (bo'lim ajratgichi topilmadi).")
    if not buf[pos + 4]:
        return buf, pos + 5
    try:
        ochuvchi = zlib.decompressobj()
        tana = ochuvchi.decompress(buf[pos + 5 :], _MAX_OCHILGAN)
    except zlib.error as e:
        raise BazisParseError("Bazis fayli buzilgan (model ochilmadi).") from e
    if ochuvchi.unconsumed_tail:
        raise BazisParseError(f"Bazis fayli juda katta (modeli {_MAX_OCHILGAN // 1024**2} MB dan oshdi).")
    return tana, 0


def _kalitlar(buf: bytes, pos: int) -> tuple[list[str], int]:
    try:
        (n,) = struct.unpack_from("<I", buf, pos)
        pos += 4
        if n > 100_000:
            raise BazisParseError("Bazis fayli tanilmadi (kalitlar jadvali buzuq).")
        keys: list[str] = []
        for _ in range(n):
            (ln,) = struct.unpack_from("<I", buf, pos)
            pos += 4
            keys.append(buf[pos : pos + ln].decode("latin-1"))
            pos += ln
    except struct.error as e:
        raise BazisParseError("Bazis fayli tanilmadi (kalitlar jadvali buzuq).") from e
    return keys, pos


class _Oqim:
    """Bo'lim tanasini daraxtga aylantiradi."""

    def __init__(self, buf: bytes, pos: int = 0) -> None:
        self.keys, self.pos = _kalitlar(buf, pos)
        self.buf = buf
        self.warnings: list[str] = []

    def _qiymat(self, t: int) -> Any:
        b, p = self.buf, self.pos
        if t in (0, 1, 2):
            return None
        if t == 3:
            self.pos += 1
            return struct.unpack_from("<b", b, p)[0]
        if t == 4:
            self.pos += 4
            return struct.unpack_from("<i", b, p)[0]
        if t == 5:
            self.pos += 8
            return struct.unpack_from("<d", b, p)[0]
        if t == 6:
            (n,) = struct.unpack_from("<I", b, p)
            self.pos = p + 4 + 2 * n
            return b[p + 4 : p + 4 + 2 * n].decode("utf-16-le", "replace")
        if t == 7:
            (n,) = struct.unpack_from("<I", b, p)
            self.pos = p + 4 + n
            return bytes(b[p + 4 : p + 4 + n])
        if t == 8:
            # Teglangan qiymat: 2 ta u32 teg, keyin ichki tur va uning qiymati.
            # Bolalar TASHQI `nch` dan olinadi, shuning uchun bu yerda faqat qiymat.
            self.pos = p + 9
            return self._qiymat(b[p + 8])
        if t == 9:
            self.pos += 8
            return struct.unpack_from("<q", b, p)[0]
        if t == 10:
            self.pos += 4
            return struct.unpack_from("<f", b, p)[0]
        if t == 11:
            self.pos += 2
            return struct.unpack_from("<h", b, p)[0]
        raise BazisParseError(f"Bazis fayli tanilmadi (noma'lum qiymat turi {t}).")

    def daraxt(self, toxtash: str = "") -> dict[str, Any]:
        """Ildiz tugunni `{"_nom","_qiymat","_bolalar"}` lug'ati qilib qaytaradi.

        `toxtash` berilsa, shu nomli tugunga yetganda o'qish tugaydi va ochiq
        qolgan tugunlar ogohlantirish hisoblanmaydi — ataylab to'xtatdik.
        """
        ildiz: dict[str, Any] | None = None
        # Har element: [tugun, qolgan bola]
        stek: list[list[Any]] = []

        for _ in range(_MAX_TUGUN):
            if self.pos >= len(self.buf):
                break
            bosh = self.pos
            try:
                k, nch = struct.unpack_from("<II", self.buf, self.pos)
                self.pos += 8
                t = self.buf[self.pos]
                self.pos += 1
                qiymat = self._qiymat(t)
            except (struct.error, IndexError):
                self.warnings.append(f"fayl {bosh}-baytda tugab qoldi")
                break

            nom = self.keys[k] if k < len(self.keys) else f"?{k}"
            if nom == toxtash and ildiz is not None:
                return ildiz

            tugun: dict[str, Any] = {"_nom": nom, "_qiymat": qiymat, "_bolalar": []}
            if stek:
                stek[-1][0]["_bolalar"].append(tugun)
            elif ildiz is None:
                ildiz = tugun

            if nch:
                stek.append([tugun, nch])
                continue
            # Bargdan yuqoriga chiqamiz
            while stek:
                stek[-1][1] -= 1
                if stek[-1][1] > 0:
                    break
                stek.pop()
            if not stek:
                break

        if stek:
            self.warnings.append(f"{len(stek)} ta tugun to'liq o'qilmadi")
        if ildiz is None:
            raise BazisParseError("Bazis faylida model topilmadi.")
        return ildiz


def _bola(n: dict[str, Any], nom: str) -> dict[str, Any] | None:
    bolalar: list[dict[str, Any]] = n["_bolalar"]
    for c in bolalar:
        if c["_nom"] == nom:
            return c
    return None


def _qiy(n: dict[str, Any], nom: str) -> Any:
    c = _bola(n, nom)
    return None if c is None else c["_qiymat"]


def _matn(n: dict[str, Any], nom: str) -> str:
    q = _qiy(n, nom)
    return q.strip() if isinstance(q, str) else ""


def _son(n: dict[str, Any], nom: str, sukut: float = 0.0) -> float:
    q = _qiy(n, nom)
    return float(q) if isinstance(q, int | float) else sukut


Kvat = tuple[float, float, float, float]
Nuqta = tuple[float, float, float]


def _kvat_kopaytir(a: Kvat, b: Kvat) -> Kvat:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def _kvat_burash(q: Kvat, v: Nuqta) -> Nuqta:
    x, y, z, w = q
    vx, vy, vz = v
    tx, ty, tz = 2 * (y * vz - z * vy), 2 * (z * vx - x * vz), 2 * (x * vy - y * vx)
    return (vx + w * tx + y * tz - z * ty, vy + w * ty + z * tx - x * tz, vz + w * tz + x * ty - y * tx)


def _qoy(pos: Nuqta, quat: Kvat, yerli: Nuqta) -> Nuqta:
    """`pos` ramkasida `yerli` siljishni qo'llash."""
    b = _kvat_burash(quat, yerli)
    return (pos[0] + b[0], pos[1] + b[1], pos[2] + b[2])


def _yerli(n: dict[str, Any]) -> tuple[Nuqta, Kvat]:
    """Tugunning OTASIGA nisbatan siljishi va burilishi."""
    t = _bola(n, "Trans")
    if t is None:
        return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)
    return (
        (_son(t, "X"), _son(t, "Y"), _son(t, "Z")),
        (_son(t, "Rx"), _son(t, "Ry"), _son(t, "Rz"), _son(t, "Rw", 1.0)),
    )


def _anim(n: dict[str, Any]) -> tuple[Nuqta, Kvat] | None:
    """Tugunning OCHILISH o'zgarishi — uning O'Z (bolalar) fazosida.

    Bazis eshik va tortmaning harakatini faylda saqlaydi: `AxisStart`/`AxisEnd`
    o'q kesmasi, `AnimType` turi, `Limit` esa burilish burchagi (gradus).
    O'q koordinatalari animatsiyali tugunning ICHKI fazosida — namunada
    ilgak o'qi `x = -310.5`, eshik konturi esa `x = -309..17`, ya'ni o'q
    panelning chap chetiga tegib turibdi (o'lchab tasdiqlandi).

    Burilish yo'nalishi o'qning YO'NALISHIDAN kelib chiqadi (o'ng qo'l qoidasi):
    bir xil shkafning chap va o'ng eshigida o'q qarama-qarshi tomonga yozilgan.
    """
    a = _bola(n, "Anim")
    if a is None:
        return None
    bosh, oxir = _bola(a, "AxisStart"), _bola(a, "AxisEnd")
    if bosh is None or oxir is None:
        return None
    p = (_son(bosh, "x"), _son(bosh, "y"), _son(bosh, "z"))
    v = (_son(oxir, "x") - p[0], _son(oxir, "y") - p[1], _son(oxir, "z") - p[2])
    burchak = math.radians(_son(a, "Limit")) if math.isfinite(_son(a, "Limit")) else math.nan
    # Buzuq faylda NaN/cheksiz son butun mahsulotni o'ldirardi: kvaternion NaN
    # bo'lib, brauzerdagi sahna ko'rinmay qolardi, yuklash esa "muvaffaqiyatli"
    # deb qaytardi. Cheksizda esa `math.sin` ValueError berib 500 chiqarardi —
    # modulda boshqa hamma nosozlik o'zbekcha 422 qaytarganda. 437 haqiqiy
    # faylda bunday qiymat YO'Q; bu faqat qalqon.
    if not all(math.isfinite(x) for x in (*p, *v, burchak)):
        return None
    uzunlik = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    if uzunlik < 1e-6:
        return None
    if _qiy(a, "AnimType") == _ANIM_SURMA:
        # Tortma: o'q kesmasining O'ZI harakat (yo'nalish va uzunlik)
        return v, (0.0, 0.0, 0.0, 1.0)
    if abs(burchak) < 1e-4:
        # Gaz lift va shunga o'xshash furnitura: o'qi bor, lekin harakati yo'q
        return None
    yarim = burchak / 2
    sin = math.sin(yarim) / uzunlik
    q = (v[0] * sin, v[1] * sin, v[2] * sin, math.cos(yarim))
    # `p` nuqtasi atrofida burilish: x' = q*(x - p) + p, ya'ni siljish = p - q*p
    qp = _kvat_burash(q, p)
    return (p[0] - qp[0], p[1] - qp[1], p[2] - qp[2]), q


def _mat(xom: Any) -> tuple[str, str]:
    """Material `"nom\\rkod"` shaklida keladi."""
    if not isinstance(xom, str) or not xom:
        return "", ""
    nom, _, kod = xom.partition("\r")
    return nom.strip(), kod.strip()


def _kontur(blob: Any) -> tuple[list[list[float]], list[list[float]], bool]:
    """`Contour` blobi -> (ko'pburchak, aylanalar, to'liqmi).

    Ko'pburchak — segmentlar boshlanish nuqtalari; yoy vatar bilan
    almashtiriladi (yig'uv ko'rinishida farqi sezilmaydi). Aylanalar —
    paneldagi kesmalar (rozetka, rakovina), `[cx, cy, r]` ko'rinishida.
    """
    if not isinstance(blob, bytes) or len(blob) < 4:
        return [], [], False
    (n,) = struct.unpack_from("<I", blob, 0)
    if not 0 < n <= 10_000:
        return [], [], False
    poly: list[list[float]] = []
    aylanalar: list[list[float]] = []
    p = 4
    for _ in range(n):
        qadam = _SEGMENT.get(blob[p]) if p < len(blob) else None
        if qadam is None or p + qadam > len(blob):
            return poly, aylanalar, False
        if blob[p] == _AYLANA:
            cx, cy, r = struct.unpack_from("<ddd", blob, p + 1)
            aylanalar.append([round(cx, 2), round(cy, 2), round(r, 2)])
        else:
            x, y = struct.unpack_from("<dd", blob, p + 1)
            poly.append([round(x, 2), round(y, 2)])
        p += qadam
    return poly, aylanalar, True


def _panel(n: dict[str, Any], pos: Nuqta, quat: Kvat, opos: Nuqta, oquat: Kvat) -> tuple[BazisPanel, bool]:
    mat_nom, mat_kod = _mat(_qiy(n, "Mat"))
    poly, aylanalar, toliq = _kontur(_qiy(n, "Contour"))
    # Yumaloq javon: konturning o'zi aylana, ya'ni u kesma emas. Ilgari bu
    # yerda to'rtburchak qo'yilardi va javon KVADRAT bo'lib chizilardi.
    yumaloq = not poly and len(aylanalar) == 1
    if yumaloq:
        cx, cy, r = aylanalar.pop()
        poly = [
            [round(cx + r * math.cos(a), 2), round(cy + r * math.sin(a), 2)]
            for a in (2 * math.pi * i / _AYLANA_NUQTA for i in range(_AYLANA_NUQTA))
        ]
    butts = _bola(n, "Butts")
    return (
        BazisPanel(
            des=_matn(n, "Des"),
            name=_matn(n, "Name"),
            mat_name=mat_nom,
            mat_code=mat_kod,
            thick=_son(n, "Thick"),
            poly=poly,
            circles=aylanalar,
            is_round=yumaloq,
            pos=[round(v, 2) for v in pos],
            quat=[round(v, 6) for v in quat],
            pos_open=[round(v, 2) for v in opos],
            quat_open=[round(v, 6) for v in oquat],
            edges=[
                BazisEdge(
                    elem=int(_son(b, "Elem", -1)),
                    mat=_mat(_qiy(b, "Mat"))[0] or _matn(b, "Sign"),
                    thick=_son(b, "Thick"),
                    width=_son(b, "Width"),
                )
                for b in (butts["_bolalar"] if butts else [])
            ],
        ),
        toliq,
    )


def _panellar(model: dict[str, Any]) -> tuple[list[BazisPanel], int]:
    """Daraxtni aylanib, panellarni DUNYO koordinatalari bilan yig'adi.

    Bazisda joylashuv iyerarxik: har `Obj` otasiga nisbatan siljigan va
    burilgan (namunalarda 25 qavatgacha), shuning uchun yo'l bo'ylab
    ko'paytirib boramiz.

    IKKI zanjir olib boriladi: YOPIQ holat va ochilish animatsiyasi
    qo'llangan OCHIQ holat. Brauzerga iyerarxiya emas, har panelning ikki
    holati beriladi — u faqat ikkisi orasida interpolyatsiya qiladi.
    """
    panellar: list[BazisPanel] = []
    chala = 0
    bir = (0.0, 0.0, 0.0, 1.0)
    nol = (0.0, 0.0, 0.0)
    stek: list[tuple[dict[str, Any], Nuqta, Kvat, Nuqta, Kvat]] = [(model, nol, bir, nol, bir)]
    while stek:
        n, ota_pos, ota_quat, ota_opos, ota_oquat = stek.pop()
        yerli_pos, yerli_quat = _yerli(n)
        pos = _qoy(ota_pos, ota_quat, yerli_pos)
        quat = _kvat_kopaytir(ota_quat, yerli_quat)
        opos = _qoy(ota_opos, ota_oquat, yerli_pos)
        oquat = _kvat_kopaytir(ota_oquat, yerli_quat)
        anim = _anim(n)
        if anim is not None:
            anim_pos, anim_quat = anim
            opos = _qoy(opos, oquat, anim_pos)
            oquat = _kvat_kopaytir(oquat, anim_quat)
        if n["_nom"] == "Obj" and _qiy(n, "Type") == _PANEL_TURI:
            panel, toliq = _panel(n, pos, quat, opos, oquat)
            panellar.append(panel)
            chala += not toliq
        for c in n["_bolalar"]:
            stek.append((c, pos, quat, opos, oquat))
    return panellar, chala


def read_b3d(content: bytes) -> ParsedBazis:
    """`.b3d` baytlaridan bitta mahsulot modelini o'qiydi.

    Fayl tanilmasa `BazisParseError`; qisman o'qilsa natija `warnings` bilan
    qaytadi — texnologga ko'rsatish uchun.
    """
    if not content.startswith(b"BZ85"):
        raise BazisParseError("Bu Bazis fayli emas (sarlavha `BZ85` emas).")

    xom, boshi = _ochish(content, 4)
    sarlavha = _Oqim(xom, boshi)
    ildiz = sarlavha.daraxt()
    maqola = _bola(ildiz, "Article") or ildiz
    eskiz = _qiy(ildiz, "Thumbnail")

    tana, m_boshi = _ochish(content, sarlavha.pos)
    model = _Oqim(tana, m_boshi)
    panellar, chala = _panellar(model.daraxt(_TOXTASH))
    if chala:
        model.warnings.append(f"{chala} ta detal konturi to'liq o'qilmadi")

    return ParsedBazis(
        code=_matn(maqola, "Code"),
        name=_matn(maqola, "Name"),
        order_name=_matn(maqola, "OrderName"),
        thumbnail=eskiz if isinstance(eskiz, bytes) else b"",
        panels=panellar,
        warnings=model.warnings,
    )
