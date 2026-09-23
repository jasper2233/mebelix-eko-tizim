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
  egallaydi va undan hech narsa kerak emas. Panellar `Undo` dan OLDIN, `Model/Objs`
  ichida keladi (460 faylning hammasida `Undo` — `Document` ning bevosita bolasi).
"""

import math
import struct
import zlib
from typing import Any

from .models import (
    BazisDim,
    BazisEdge,
    BazisFurniture,
    BazisMesh,
    BazisMeshPart,
    BazisPanel,
    BazisParseError,
    ParsedBazis,
)

#: `Obj.Type` — Bazisning o'z raqamlari. 460 faylda o'lchandi (docs/13 §2.4).
#: Panel; profil (cho'zilgan jism: muzlatkich korpusi, relslar); egilgan panel
#: (rakovina kosasi, rels tutqich); furnitura (mesh `FurnList` da: tutqich,
#: oyoq, ilgak, vityajka); aylanma jism; ayirish (`Вычитание тел`).
_PANEL_TURI = 4002
_PROFIL_TURI, _EGIK_TURI = 2004, 999
_FURNITURA_TURI, _AYLANMA_TURI, _AYIRISH_TURI = 3001, 2002, 1004
#: Import qilingan mesh (SketchUp va boshqalar) — `TriData` tugunning o'zida
_IMPORT_TURI = 10000
#: Bazischining o'lcham chizig'i (`Размер`)
_OLCHAM_TURI = 9000
#: `TriData` uchburchagi: 3 uch, 3 uch normali, yuza normali, UV, qirra bayroqlari
_UCHBURCHAK = struct.Struct("<9f9f3f6fI")
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
#: Kontur segmentlari: turi -> uzunligi (tur bayti bilan). 460 faylda o'lchandi:
#: `0x10` chiziq `x1 y1 x2 y2`; `0x12` yoy `cx cy x1 y1 x2 y2` + yo'nalish bayti
#: (1 = soat mili TESKARISI, Bazis `Arc2D.ArcDir`) — MARKAZ BIRINCHI keladi;
#: `0x11` va `0x14` aylana `cx cy r` (`0x14` 7 panelda, hammasi 25 bayt, ichidagi
#: teshik). Noma'lum tur chiqsa kontur shu yerda uziladi va ogohlantirish qaytadi.
_SEGMENT = {0x10: 33, 0x11: 25, 0x12: 50, 0x14: 25}
_CHIZIQ, _YOY = 0x10, 0x12
#: Segment uchlari shu masofada (mm) bo'lsa — bitta nuqta.
_ULASH = 0.05
#: Kontur sonining chegarasi (mm, 1000 km): undan kattasi yoki NaN — buzuq fayl.
_CHEGARA = 1e9
#: Aylanma jism (2002) — har kontur nuqtasi 96 uchburchak beradi: 20 KB kontur
#: 883 ming uchburchak va 3 s CPU edi (sun'iy fayl bilan o'lchandi). Haqiqiy 3 ta
#: jismda 30 nuqta, 2688 uchburchak. Chegaradan oshgani chizilmaydi.
_MAX_AYLANMA_NUQTA = 256
_MAX_AYLANMA_UCH = 50_000
#: Burilish kvaternionining `w` i shundan katta — 1° dan kam burilish (tortma surilishi)
_BURILMAYDI = math.cos(math.radians(0.5))


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
            # Qiymatsiz tugun (0 bayt). Ilgari keyingi 9 bayt "teg + ichki tur" deb
            # o'qilardi — aslida ular KEYINGI tugunning sarlavhasi (kalit, bolalar,
            # tur): korpusdagi 5 355 "teg"ning hammasi haqiqiy kalit nomi chiqdi.
            # O'sha tugun yutilib, daraxt siljirdi va 64/460 faylda panellar 13 m
            # gacha noto'g'ri joyga tushardi. Endi 460/460 daraxt EOF da aniq yopiladi.
            return None
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

    `Shift` — ilgakda o'qning siljishi (Bazis qo'llanmasi: "rotation axis shift
    along the axis that is perpendicular to rotation axis"). Qaysi perpendikulyar
    ekani yozilmagan, O'LCHANDI: 22 namunaning 314 eshigida o'q yerli +Z ga
    `Shift` qadar surilsa, ochilganda boshqa panelga 3 mm dan chuqur kiradigan
    eshiklar 20 (va 4 xona yuzasi) dan 0 ga tushadi; -Z ga surilsa 90.
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
    surish = _son(a, "Shift")
    # Buzuq faylda NaN/cheksiz son butun mahsulotni o'ldirardi: kvaternion NaN
    # bo'lib, brauzerdagi sahna ko'rinmay qolardi, yuklash esa "muvaffaqiyatli"
    # deb qaytardi. Cheksizda esa `math.sin` ValueError berib 500 chiqarardi —
    # modulda boshqa hamma nosozlik o'zbekcha 422 qaytarganda. 460 haqiqiy
    # faylda bunday qiymat YO'Q; bu faqat qalqon.
    if not all(math.isfinite(x) for x in (*p, *v, burchak, surish)):
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
    # O'q nuqtasi atrofida burilish: x' = q*(x - o) + o, ya'ni siljish = o - q*o
    o = (p[0], p[1], p[2] + surish)
    qo = _kvat_burash(q, o)
    return (o[0] - qo[0], o[1] - qo[1], o[2] - qo[2]), q


def _mat(xom: Any) -> tuple[str, str]:
    """Material `"nom\\rkod"` shaklida keladi."""
    if not isinstance(xom, str) or not xom:
        return "", ""
    nom, _, kod = xom.partition("\r")
    return nom.strip(), kod.strip()


Tekis = list[list[float]]
#: Konturning bitta alohida bo'lagi: (chegara, kesmalar, aylana kesmalar, yumaloqmi)
Orol = tuple[Tekis, list[Tekis], Tekis, bool]


def _yoy(cx: float, cy: float, x1: float, y1: float, x2: float, y2: float, teskari: bool) -> Tekis:
    """Yoy nuqtalari boshidan oxirigacha (ikkalasi ham ichida), to'liq aylana 48 bo'lak zichligida."""
    r = (math.hypot(x1 - cx, y1 - cy) + math.hypot(x2 - cx, y2 - cy)) / 2
    a1, a2 = math.atan2(y1 - cy, x1 - cx), math.atan2(y2 - cy, x2 - cx)
    qamrov = (a2 - a1) % (2 * math.pi) if teskari else -((a1 - a2) % (2 * math.pi))
    if abs(qamrov) < 1e-9:  # boshi = oxiri: to'liq aylana
        qamrov = 2 * math.pi if teskari else -2 * math.pi
    n = max(1, math.ceil(abs(qamrov) * _AYLANA_NUQTA / (2 * math.pi)))
    ichki = [[cx + r * math.cos(a1 + qamrov * i / n), cy + r * math.sin(a1 + qamrov * i / n)] for i in range(1, n)]
    return [[x1, y1], *ichki, [x2, y2]]


def _halqalar(bolaklar: list[Tekis]) -> list[Tekis]:
    """Segmentlarni UCHLARI bo'yicha yopiq halqalarga ulaydi.

    Bazis konturi hamma vaqt bitta, tartib bilan yozilgan halqa EMAS: 41 305
    panelning 2166 tasida segmentlar aralash yoki teskari yozilgan, 495 tasida
    bir nechta halqa bor (tashqi chegara + rakovina kabi ichki kesma). Boshlanish
    nuqtalarini yozilish tartibida ulash o'z-o'zini kesadigan "kapalak" berardi.
    Yozilgan tartib iloji boricha saqlanadi: keyingi segment mos kelsa — o'sha olinadi.

    Uchlar `_ULASH` katakli to'rda indekslanadi, ya'ni ulash CHIZIQLI: ro'yxatni har
    qadamda qayta ko'rish kvadratik edi — parser qabul qiladigan 10 000 segmentli
    konturda 3.4 s (tartibli) va 10.7 s (aralash), bitta panel uchun.
    """

    def yaqin(a: list[float], b: list[float]) -> bool:
        return abs(a[0] - b[0]) <= _ULASH and abs(a[1] - b[1]) <= _ULASH

    def katak(p: list[float]) -> tuple[int, int]:
        # `round` emas: u yarmini juftga yaxlitlaydi va _ULASH masofadagi ikki
        # nuqta 2 katak narida tushishi mumkin edi; `floor` da ko'pi bilan 1.
        return math.floor(p[0] / _ULASH), math.floor(p[1] / _ULASH)

    uchlar: dict[tuple[int, int], list[int]] = {}
    for i, b in enumerate(bolaklar):
        for uch in (b[0], b[-1]):
            uchlar.setdefault(katak(uch), []).append(i)

    def nomzodlar(p: list[float]) -> list[int]:
        kx, ky = katak(p)
        return sorted({i for dx in (-1, 0, 1) for dy in (-1, 0, 1) for i in uchlar.get((kx + dx, ky + dy), ())})

    ishlatilgan = [False] * len(bolaklar)
    halqalar: list[Tekis] = []
    for bosh in range(len(bolaklar)):
        if ishlatilgan[bosh]:
            continue
        ishlatilgan[bosh] = True
        joriy = bosh
        halqa = bolaklar[bosh][:-1]
        oxiri = bolaklar[bosh][-1]
        while not yaqin(oxiri, halqa[0]):
            # Avval yozilgan tartibdagi keyingisi, keyin qolganlari tartib raqami bo'yicha
            navbat = [joriy + 1] if joriy + 1 < len(bolaklar) else []
            topildi = None
            for i in navbat + nomzodlar(oxiri):
                if ishlatilgan[i]:
                    continue
                if yaqin(bolaklar[i][0], oxiri):
                    topildi = (i, bolaklar[i])
                    break
                if yaqin(bolaklar[i][-1], oxiri):
                    topildi = (i, bolaklar[i][::-1])
                    break
            if topildi is None:
                break  # ochiq zanjir — shu holicha halqa hisoblanadi
            joriy, bolak = topildi
            ishlatilgan[joriy] = True
            halqa.extend(bolak[:-1])
            oxiri = bolak[-1]
        if len(halqa) >= 3:
            halqalar.append(halqa)
    return halqalar


def _yuza(h: Tekis) -> float:
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(h, h[1:] + h[:1], strict=True))) / 2


def _ichidami(nuqta: list[float], h: Tekis) -> bool:
    x, y = nuqta
    ichida = False
    for (x1, y1), (x2, y2) in zip(h, h[1:] + h[:1], strict=True):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            ichida = not ichida
    return ichida


def _aylana_poly(cx: float, cy: float, r: float) -> Tekis:
    return [
        [cx + r * math.cos(a), cy + r * math.sin(a)]
        for a in (2 * math.pi * i / _AYLANA_NUQTA for i in range(_AYLANA_NUQTA))
    ]


def _yaxlitla(h: Tekis) -> Tekis:
    return [[round(x, 2), round(y, 2)] for x, y in h]


def _kontur(blob: Any) -> tuple[list[Orol], bool]:
    """`Contour` blobi -> (alohida bo'laklar, to'liq o'qildimi).

    Chiziq va yoylar uchlari bo'yicha halqalarga ulanadi; eng katta halqa —
    chegara, uning ichidagilari — kesma (rakovina, plita teshigi). Yoy
    nuqtalarga bo'linadi. Aylanalar `[cx, cy, r]`: chegara ichida bo'lsa
    kesma; chiziq/yoy umuman yo'q bo'lsa eng kattasi bo'lakning O'ZI
    (yumaloq javon), qolganlari uning teshiklari. Bo'laklar — `_orollar`.
    """
    if not isinstance(blob, bytes) or len(blob) < 4:
        return [], False
    (n,) = struct.unpack_from("<I", blob, 0)
    if not 0 < n <= 10_000:
        return [], False
    bolaklar: list[Tekis] = []
    aylanalar: list[list[float]] = []
    toliq = True
    p = 4
    for _ in range(n):
        tur = blob[p] if p < len(blob) else None
        qadam = _SEGMENT.get(tur) if tur is not None else None
        if tur is None or qadam is None or p + qadam > len(blob):
            toliq = False
            break
        # Segment = tur bayti + `double` lar (yoyda oxirida yo'nalish bayti)
        sonlar = struct.unpack_from(f"<{(qadam - 1) // 8}d", blob, p + 1)
        # Buzuq faylda NaN/cheksiz (yoki 1000 km dan katta) koordinata to'rning
        # `math.floor` ida ValueError/OverflowError berib, yuklashni 500 ga
        # aylantirardi — `_anim` dagi qalqon bilan bir xil sabab. 460 haqiqiy
        # faylda bunday qiymat YO'Q; noma'lum segment kabi: kontur to'liq emas.
        if not all(abs(v) < _CHEGARA for v in sonlar):
            toliq = False
            break
        if tur == _CHIZIQ:
            x1, y1, x2, y2 = sonlar
            bolaklar.append([[x1, y1], [x2, y2]])
        elif tur == _YOY:
            cx, cy, x1, y1, x2, y2 = sonlar
            bolaklar.append(_yoy(cx, cy, x1, y1, x2, y2, teskari=blob[p + 49] == 1))
        else:  # 0x11 / 0x14 — aylana
            aylanalar.append(list(sonlar))
        p += qadam

    return _orollar(bolaklar, aylanalar), toliq


def _orollar(bolaklar: list[Tekis], aylanalar: list[list[float]]) -> list[Orol]:
    """Segmentlar va aylanalardan ALOHIDA bo'laklar (kattasi birinchi).

    Juft-toq qoida: halqa (yoki aylana) eng ichki o'rab turgan halqaga qaraydi —
    u bo'lak chegarasi bo'lsa, bu uning kesmasi; kesma bo'lsa yoki hech narsa
    o'rab turmasa, bu YANGI bo'lak. Yumaloq bo'lak — profil ichidagi 14 ta Ø5
    shtift, ikki Ø30 tayoq. Ilgari har ichki halqa tashqi bo'lakning kesmasi
    bo'lardi: `ALLU` panjarasining (ramka ochig'ida 16 reyka, 4 disk) hammasi
    kesma bo'lib, 56 profil deyarli yaxlit plita chiqardi — kesma ichidagi kesmani
    three.js to'g'ri yuzadan 3.4-4 barobar ko'p to'ldiradi. Panel bitta bo'lak
    bo'ladi, profil esa bir nechta bo'lishi mumkin."""
    orollar: list[Orol] = []
    # Joylangan halqalar: (kontur, bo'lak indeksi, kesmami). Yuza bo'yicha
    # kamayib joylanadi, ya'ni o'rab turganlarning OXIRGISI — eng ichkisi.
    joylangan: list[tuple[Tekis, int, bool]] = []
    navbat: list[tuple[float, Tekis, list[float] | None]] = [(_yuza(h), h, None) for h in _halqalar(bolaklar)]
    navbat += [(math.pi * c[2] ** 2, _aylana_poly(*c), c) for c in aylanalar]
    for _, h, aylana in sorted(navbat, key=lambda e: e[0], reverse=True):
        ichki = next((j for j in reversed(joylangan) if _ichidami(aylana[:2] if aylana else h[0], j[0])), None)
        if ichki is None or ichki[2]:
            joylangan.append((h, len(orollar), False))
            orollar.append((h, [], [], aylana is not None))
        else:
            joylangan.append((h, ichki[1], True))
            if aylana:
                orollar[ichki[1]][2].append([round(v, 2) for v in aylana])
            else:
                orollar[ichki[1]][1].append(h)
    return [(_yaxlitla(t), [_yaxlitla(h) for h in k], d, y) for t, k, d, y in orollar]


def _panel(
    n: dict[str, Any], turi: int, pos: Nuqta, quat: Kvat, opos: Nuqta, oquat: Kvat
) -> tuple[list[BazisPanel], bool]:
    """Panel (4002) yoki jism (2004 profil, 999 egilgan panel) -> panellar, to'liqmi.

    Uchalasi ham bir xil geometriya: kontur o'z XY tekisligida, lokal Z bo'ylab
    qalinlikka cho'ziladi (460 faylda o'lchandi: muzlatkich 910 x 1830 x 672.5,
    `BAYFU 400 mm` relsi aynan 400 mm). Farqlari:

    * Jismning qalinligi `Thickness` va ISHORALI — z `0..Thickness` (5091 dan 770
      tasi manfiy). Brauzer musbat qalinlik kutadi, shuning uchun manfiyda
      boshlanish nuqtasi `R·(0,0,Th)` ga suriladi; ishorani tashlab yuborish
      770 dan 335 tasini mahsulotdan tashqariga chiqarardi.
    * Jism bir nechta ALOHIDA bo'lak bo'lishi mumkin (ikki tayoqli profil) —
      har biri o'z panelida. Panel esa bitta bo'lak.
    * Profil uchlari `ClipPlanes` bilan 45° ga kesiladi (163 profil): ramka
      burchaklari ustma-ust emas, aynan ulanadi (308/308 uch).
    """
    mat_nom, mat_kod = _mat(_qiy(n, "Mat"))
    orollar, toliq = _kontur(_qiy(n, "Contour"))
    siljish = 0.0
    if turi == _PANEL_TURI:
        qalin = _son(n, "Thick")
        # Chegaradan TASHQARIDAGI halqa — panelning ikkinchi alohida bo'lagi. 41 305
        # panelda bitta (arxivdagi parta), shuning uchun chizilmaydi, lekin jimgina
        # ham yo'qolmaydi: texnolog "kontur to'liq o'qilmadi" ogohlantirishini ko'radi.
        # Tashqaridagi AYLANA va kesma ICHIDAGI bo'lak (fasaddagi yozuv harfining
        # ko'zi, 2 panel, 11 x 8 mm) esa ogohlantirishsiz chizilmaydi.
        toliq = toliq and all(o[3] or (orollar[0][0] and _ichidami(o[0][0], orollar[0][0])) for o in orollar[1:])
        orollar = orollar[:1] or [([], [], [], False)]
    else:
        th = _son(n, "Thickness")
        qalin, siljish = abs(th), min(0.0, th)
        if siljish:
            pos = _qoy(pos, quat, (0.0, 0.0, siljish))
            opos = _qoy(opos, oquat, (0.0, 0.0, siljish))
    tekisliklar = _bola(n, "ClipPlanes")
    kesuvchi = [
        [
            round(_son(c, "x"), 6),
            round(_son(c, "y"), 6),
            round(_son(c, "z"), 6),
            round(_son(c, "d") + _son(c, "z") * siljish, 3),
        ]
        for c in (tekisliklar["_bolalar"] if tekisliklar else [])
    ]
    butts = _bola(n, "Butts")
    kromkalar = [
        BazisEdge(
            elem=int(_son(b, "Elem", -1)),
            mat=_mat(_qiy(b, "Mat"))[0] or _matn(b, "Sign"),
            thick=_son(b, "Thick"),
            width=_son(b, "Width"),
        )
        for b in (butts["_bolalar"] if butts else [])
    ]
    return [
        BazisPanel(
            des=_matn(n, "Des"),
            name=_matn(n, "Name"),
            mat_name=mat_nom,
            mat_code=mat_kod,
            thick=qalin,
            poly=poly,
            holes=kesmalar,
            circles=aylanalar,
            is_round=yumaloq,
            pos=[round(v, 2) for v in pos],
            quat=[round(v, 6) for v in quat],
            pos_open=[round(v, 2) for v in opos],
            quat_open=[round(v, 6) for v in oquat],
            kind=turi,
            clip=kesuvchi,
            grain_x=_qiy(n, "TexDir") == 1,
            edges=kromkalar,
        )
        for poly, kesmalar, aylanalar, yumaloq in orollar
    ], toliq


def _tridata(blob: Any) -> BazisMesh | None:
    """Furnitura geometriyasi — `FurnList/F{FastID}/TriData`.

    Tuzilishi (460 fayldagi 4193 blob baytma-bayt o'qildi, dumi 0 bayt):
    `u32` qismlar; har qism: `u32 n` + UTF-16 material nomi (`qora rang`,
    `GTV Nikel plated`), 16 `f64` — TEKSTURA matritsasi (uchlarga QO'LLANMAYDI:
    xom uchlar 4193/4193 blobda `MinX..MaxZ` qutisi ichida, qo'llansa tutqich
    ezilardi), `u8`, `u32` uchburchaklar soni va har biri 112 bayt
    (`_UCHBURCHAK`). Indeks bufer yo'q — bir xil uchlar shu yerda
    birlashtiriladi (uch VA normal bir xil bo'lsa: o'tkir qirra saqlanadi).
    Mahkamlagichlarda (`Mix 2.5`, shurup) blob yo'q — ular chizilmaydi ham."""
    if not isinstance(blob, bytes) or len(blob) < 4:
        return None
    mesh = BazisMesh()
    try:
        (qismlar,) = struct.unpack_from("<I", blob, 0)
        p = 4
        for _ in range(min(qismlar, 64)):
            (nch,) = struct.unpack_from("<I", blob, p)
            nom = blob[p + 4 : p + 4 + 2 * nch].decode("utf-16-le", "replace")
            p += 4 + 2 * nch + 128 + 1
            (soni,) = struct.unpack_from("<I", blob, p)
            p += 4
            if p + soni * _UCHBURCHAK.size > len(blob):
                return None
            qism = BazisMeshPart(mat_name=_mat(nom)[0])
            uchlar: dict[tuple[float, ...], int] = {}
            for _ in range(soni):
                r = _UCHBURCHAK.unpack_from(blob, p)
                p += _UCHBURCHAK.size
                for j in range(3):
                    v, nv = r[3 * j : 3 * j + 3], r[9 + 3 * j : 12 + 3 * j]
                    if not all(abs(x) < _CHEGARA for x in v + nv):
                        return None
                    kalit = (*(round(x, 2) for x in v), *(round(x, 3) for x in nv))
                    if kalit not in uchlar:
                        uchlar[kalit] = len(uchlar)
                        qism.positions.extend(v)
                        qism.normals.extend(nv)
                    qism.indices.append(uchlar[kalit])
            if qism.indices:
                mesh.parts.append(qism)
    except (struct.error, UnicodeDecodeError):
        return None
    return mesh if mesh.parts else None


def _aylanma(n: dict[str, Any]) -> BazisMesh | None:
    """`Вращение` (2002) — kontur lokal Z o'qi atrofida 360° aylantiriladi:
    kontur x — radius, y — balandlik. 460 faylda 3 ta (Reginox rakovina kosasi,
    stoleshnitsadagi aylana kesma bilan bir o'qda)."""
    orollar, _ = _kontur(_qiy(n, "Contour"))
    if not orollar or len(orollar[0][0]) > _MAX_AYLANMA_NUQTA:
        return None
    halqa = orollar[0][0]
    qism = BazisMeshPart(mat_name=_mat(_qiy(n, "Mat"))[0])
    burchaklar = [2 * math.pi * j / _AYLANA_NUQTA for j in range(_AYLANA_NUQTA + 1)]
    for (x1, y1), (x2, y2) in zip(halqa, halqa[1:] + halqa[:1], strict=True):
        for t0, t1 in zip(burchaklar, burchaklar[1:], strict=False):
            a = (x1 * math.cos(t0), x1 * math.sin(t0), y1)
            b = (x2 * math.cos(t0), x2 * math.sin(t0), y2)
            c = (x2 * math.cos(t1), x2 * math.sin(t1), y2)
            d = (x1 * math.cos(t1), x1 * math.sin(t1), y1)
            for uch in ((a, b, c), (a, c, d)):
                u = [uch[1][k] - uch[0][k] for k in range(3)]
                w = [uch[2][k] - uch[0][k] for k in range(3)]
                nrm = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
                uzun = math.sqrt(sum(k * k for k in nrm))
                if uzun < 1e-9:
                    continue  # o'qdagi nuqtada uchburchak nolga aylanadi
                for nuqta in uch:
                    qism.indices.append(len(qism.positions) // 3)
                    qism.positions.extend(nuqta)
                    qism.normals.extend(k / uzun for k in nrm)
    return BazisMesh(parts=[qism]) if qism.indices else None


def _olcham(n: dict[str, Any], pos: Nuqta, quat: Kvat, birlik: int | None) -> BazisDim | None:
    """Bazischining o'lchami. Uchlari o'z fazosida (0,0,0) va (Size,0,0): 22 namunada
    254 uchdan 226 tasi panel yuzasidan 1 mm ichida, `Value` 127/127 da `Size` ga
    teng. Chizig'i +Y bo'ylab `Length` ga surilgan — 460 faylda teng bo'lmagan 1905
    holatning 1757 tasida (92%) aynan shu tomon panellardan uzoqroq, ya'ni mahsulotdan
    tashqarida. `TextOffset`, `TextSize`, `Color` o'qilmaydi: ular Bazisning qotgan
    kamerasi uchun, brauzer esa yorliqni har burilishda qayta joylaydi."""
    size, uzun, qiymat = _son(n, "Size"), _son(n, "Length"), _son(n, "Value", _son(n, "Size"))
    if not all(math.isfinite(v) and abs(v) < _CHEGARA for v in (size, uzun, qiymat)) or abs(size) < 1:
        return None
    b = _qoy(pos, quat, (size, 0.0, 0.0))
    o = _kvat_burash(quat, (0.0, uzun, 0.0))
    return BazisDim(
        value=round(abs(qiymat), 1),
        a=[round(v, 1) for v in pos],
        b=[round(v, 1) for v in b],
        o=[round(v, 1) for v in o],
        group=birlik,
    )


def _panellar(
    model: dict[str, Any],
) -> tuple[list[BazisPanel], list[BazisFurniture], list[BazisMesh], list[BazisDim], int]:
    """Daraxtni aylanib, panellar va furniturani DUNYO koordinatalari bilan yig'adi.

    Bazisda joylashuv iyerarxik: har `Obj` otasiga nisbatan siljigan va
    burilgan (460 faylda 9 qavatgacha), shuning uchun yo'l bo'ylab
    ko'paytirib boramiz.

    IKKI zanjir olib boriladi: YOPIQ holat va ochilish animatsiyasi
    qo'llangan OCHIQ holat. Brauzerga iyerarxiya emas, har panelning ikki
    holati beriladi — oraliq holatni u o'zi tiklaydi (eshik ikki holatdan
    topilgan o'q atrofida buriladi, tortma to'g'ri chiziqda — `ilgak.ts`).

    Furnitura (3001) — joyi shu zanjirdan (`dunyo = pos + R·v`, DatumMode ham,
    ParamOffset ham kerak emas: 4007/4011 tutqich eshik yuzasida, 2952/2952
    oyoq polda, 43/43 vityajka stoleshnitsadan 680-810 mm yuqorida), meshi esa
    `FurnList` dan, FastID bo'yicha BIR MARTA. Eshikdagi tutqich eshik bilan
    birga ochiladi — birligi eshikniki.
    """
    panellar: list[BazisPanel] = []
    furnitura: list[BazisFurniture] = []
    meshlar: list[BazisMesh] = []
    furn_list = _bola(model, "FurnList")
    furn_yozuv = {c["_nom"]: c for c in (furn_list["_bolalar"] if furn_list else [])}
    #: FastID -> `meshlar` dagi indeks (meshsiz — mahkamlagich — `None`)
    furn_mesh: dict[Any, int | None] = {}
    chala = 0
    #: Fayldagi aylanma jismlar uchburchaklari — `_MAX_AYLANMA_UCH` gacha
    aylanma_uch = 0
    #: Import qilingan mesh (10000): blob -> `meshlar` indeksi; `furnitura` dagi o'rinlari
    import_mesh: dict[bytes | None, int | None] = {}
    importlar: list[int] = []
    olchamlar: list[BazisDim] = []
    #: Yig'ma (eng yaqin `Obj` ajdod) -> uning ichidagi birliklar va harakati
    yigmalar: dict[int, list[tuple[Kvat, Nuqta, int]]] = {}
    birliklar = 0
    bir = (0.0, 0.0, 0.0, 1.0)
    nol = (0.0, 0.0, 0.0)
    stek: list[tuple[dict[str, Any], Nuqta, Kvat, Nuqta, Kvat, int | None, int, bool]] = [
        (model, nol, bir, nol, bir, None, 0, False)
    ]
    while stek:
        n, ota_pos, ota_quat, ota_opos, ota_oquat, birlik, yigma, yashirin = stek.pop()
        # `Vis` (qiymatsiz kalit) — obyekt Bazisda YASHIRILGAN, bolalari bilan. GibLab
        # eksporti ham yashiringanni tashlaydi (`GibLabExport_V1.861.js:1033`
        # `if (!node.Visible) return;`). Hozircha faqat o'lchamga qo'llanadi.
        yashirin = yashirin or (n["_nom"] == "Obj" and _bola(n, "Vis") is not None)
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
            # Harakat birligi — ENG TASHQI harakatlanuvchi ajdod: ichma-ich
            # animatsiyada (460 faylda 17 ta, tortma ichidagi eshik) ichkisi
            # tashqisi bilan birga ochiladi, aks holda harakat paytida ajralardi.
            # Bitta yig'mada AYNAN bir xil harakatlanadigan aka-ukalar ham bitta
            # birlik: Bazis tortmaning qutisi (`yashik`) va fasadiga alohida
            # `Anim` yozadi — alohida bo'lsa kaskadda ular bir-biridan ajralardi.
            # Ikki eshikli shkafning eshiklari esa har xil buriladi — alohida.
            if birlik is None:
                r, t = _harakat(pos, quat, opos, oquat)
                aka = yigmalar.setdefault(yigma, [])
                birlik = next((b for r2, t2, b in aka if _bir_xil(r, t, r2, t2)), None)
                if birlik is None:
                    birlik = birliklar
                    birliklar += 1
                    aka.append((r, t, birlik))
        turi = _qiy(n, "Type") if n["_nom"] == "Obj" else None
        mesh: int | None = None
        if turi in (_PANEL_TURI, _PROFIL_TURI, _EGIK_TURI):
            yangi, toliq = _panel(n, turi, pos, quat, opos, oquat)
            for panel in yangi:
                panel.group = birlik
            panellar.extend(yangi)
            chala += not toliq
        elif turi == _FURNITURA_TURI:
            fast = _qiy(n, "FastID")
            if fast not in furn_mesh:
                yozuv = furn_yozuv.get(f"F{fast}")
                geo = _tridata(_qiy(yozuv, "TriData")) if yozuv else None
                furn_mesh[fast] = len(meshlar) if geo else None
                if geo:
                    meshlar.append(geo)
            mesh = furn_mesh[fast]
        elif turi == _AYLANMA_TURI and aylanma_uch < _MAX_AYLANMA_UCH:
            geo = _aylanma(n)
            if geo:
                aylanma_uch += len(geo.parts[0].indices) // 3
                mesh = len(meshlar)
                meshlar.append(geo)
        elif turi == _IMPORT_TURI:
            # Blob bo'yicha BIR MARTA: `2-Oshxona` da 44 ta rels va qulf nusxasi
            blob = _qiy(n, "TriData")
            kalit = blob if isinstance(blob, bytes) else None
            if kalit not in import_mesh:
                geo = _tridata(blob)
                import_mesh[kalit] = len(meshlar) if geo else None
                if geo:
                    meshlar.append(geo)
            mesh = import_mesh[kalit]
            if mesh is not None:
                importlar.append(len(furnitura))
        elif turi == _OLCHAM_TURI and not yashirin:
            olcham = _olcham(n, pos, quat, birlik)
            if olcham:
                olchamlar.append(olcham)
        if mesh is not None:
            furnitura.append(
                BazisFurniture(
                    name=_mat(_qiy(n, "Name"))[0],
                    mesh=mesh,
                    pos=[round(v, 2) for v in pos],
                    quat=[round(v, 6) for v in quat],
                    pos_open=[round(v, 2) for v in opos],
                    quat_open=[round(v, 6) for v in oquat],
                    group=birlik,
                )
            )
        ichki_yigma = id(n) if n["_nom"] == "Obj" else yigma
        for c in n["_bolalar"]:
            if turi == _AYIRISH_TURI and c["_nom"] == "Objs":
                # `Вычитание тел`: birinchi jismdan IKKINCHISI ayiriladi (Bazis
                # qo'llanmasi: "The second object will be subtracted from the
                # first one"). Ikkinchisi — kesuvchi asbob, detal emas: ilgari u
                # 58 faylda duxovka tagida qora 320x115x50 blok bo'lib chizilardi.
                c = {**c, "_bolalar": [o for o in c["_bolalar"] if o["_nom"] == "Obj"][:1]}
            stek.append((c, pos, quat, opos, oquat, birlik, ichki_yigma, yashirin))
    _eshikka_bogla(panellar, furnitura, meshlar)
    furnitura = _import_sarala(panellar, furnitura, meshlar, importlar)
    return panellar, furnitura, meshlar, olchamlar, chala


def _quti(nuqtalar: list[Nuqta]) -> tuple[Nuqta, Nuqta]:
    return (
        (min(p[0] for p in nuqtalar), min(p[1] for p in nuqtalar), min(p[2] for p in nuqtalar)),
        (max(p[0] for p in nuqtalar), max(p[1] for p in nuqtalar), max(p[2] for p in nuqtalar)),
    )


def _uch(v: list[float]) -> Nuqta:
    return (v[0], v[1], v[2])


def _tort(v: list[float]) -> Kvat:
    return (v[0], v[1], v[2], v[3])


def _dunyo_qutisi(pos: list[float], quat: list[float], past: Nuqta, yuqori: Nuqta) -> tuple[Nuqta, Nuqta]:
    """Yerli qutining 8 burchagi dunyoda -> dunyo qutisi (AABB)."""
    return _quti(
        [
            _qoy(_uch(pos), _tort(quat), (x, y, z))
            for x in (past[0], yuqori[0])
            for y in (past[1], yuqori[1])
            for z in (past[2], yuqori[2])
        ]
    )


def _import_sarala(
    panellar: list[BazisPanel], furnitura: list[BazisFurniture], meshlar: list[BazisMesh], importlar: list[int]
) -> list[BazisFurniture]:
    """Import qilingan meshlar (10000) — mahsulotning o'zimi yoki yonidagi nusxami.

    460 faylda 5 tasida bor (276 ta), hammasi o'qiladi. `2-Oshxona` da tortma
    relslari va qulflari (`TANDEM с интегр. BLUMOTION`, 44 ta) — hammasi mahsulot
    ichida, ilgari ko'rinmasdi. `SP KUBO STANDART` (173) va `2 qavcatlik spalniy`
    (30) da esa HAMMASI mahsulotdan tashqarida — SketchUp'dan olingan, 1-2 m
    chetga qo'yilgan nusxa: chizilsa yonida ikkinchi mebel paydo bo'lardi. Shuning
    uchun fayldagi importlarning birortasi ham mahsulot qutisi (panellar, 50 mm
    zaxira) ichida bo'lmasa — hammasi tashlanadi, aks holda hammasi chiziladi."""
    if not importlar:
        return furnitura
    burchaklar: list[Nuqta] = []
    for p in panellar:
        if p.poly:
            xs, ys = [q[0] for q in p.poly], [q[1] for q in p.poly]
            burchaklar += list(_dunyo_qutisi(p.pos, p.quat, (min(xs), min(ys), 0.0), (max(xs), max(ys), p.thick)))
    if burchaklar:
        q0, q1 = _quti(burchaklar)
        for i in importlar:
            f = furnitura[i]
            uchlar = [
                _uch(q.positions[k : k + 3]) for q in meshlar[f.mesh].parts for k in range(0, len(q.positions), 3)
            ]
            a0, a1 = _dunyo_qutisi(f.pos, f.quat, *_quti(uchlar))
            if all(q0[j] - 50 <= (a0[j] + a1[j]) / 2 <= q1[j] + 50 for j in range(3)):
                return furnitura
    tashla = set(importlar)
    qolgan = [f for i, f in enumerate(furnitura) if i not in tashla]
    # Tashlanganlarning meshi JSON'ga tushmasin (`SP KUBO` da 20 ming uchburchak)
    ishlatilgan = sorted({f.mesh for f in qolgan})
    yangi = {eski: i for i, eski in enumerate(ishlatilgan)}
    meshlar[:] = [meshlar[i] for i in ishlatilgan]
    for f in qolgan:
        f.mesh = yangi[f.mesh]
    return qolgan


def _eshikka_bogla(panellar: list[BazisPanel], furnitura: list[BazisFurniture], meshlar: list[BazisMesh]) -> None:
    """Eshikka o'rnatilgan furniturani eshikka QATTIQ bog'laydi.

    Bazis ilgak kosasiga eshikdan ALOHIDA `Anim` yozadi — eshik yig'masida emas,
    yonidagi ilgak yig'masida (`Petlya ROBUST` > `Chashka`). Burilishi eshiknikiga
    aynan teng, lekin `Shift` boshqa yerli fazoda (kosada o'q teskari) va
    ochilganda kosa eshikdan ~45 mm chetda qolardi; birligi ham boshqa edi —
    bitta eshik ochilganda kosalari joyida qolardi. 460 faylda o'lchandi: o'z
    birligidagi 8894 kosadan 8871 tasi, 2023 `Фурнитура#` dan 2007 tasi va 312
    `Фиксатор на фасад` dan 311 tasi yopiq holatda harakatlanuvchi panelga tegib
    turadi (1 mm) va u bilan AYNAN bir xil buriladi.

    Shunday furnitura panelning birligini va harakatini oladi. Burilmaydigan
    harakat (tortma) tegmaydi: `DONGA` relsi tortmaga tegadi, lekin o'z
    harakati bor (teleskop). Gaz lift shtoki eshikka tegmaydi — o'z harakatida."""
    eshiklar = []
    for p in panellar:
        if p.group is None or not p.poly:
            continue
        r, t = _harakat(_uch(p.pos), _tort(p.quat), _uch(p.pos_open), _tort(p.quat_open))
        if r[3] > _BURILMAYDI:
            continue
        xs, ys = [q[0] for q in p.poly], [q[1] for q in p.poly]
        qut = _dunyo_qutisi(p.pos, p.quat, (min(xs), min(ys), 0.0), (max(xs), max(ys), p.thick))
        eshiklar.append((qut, r, t, p.group))
    if not eshiklar:
        return
    panel_birlik = {e[3] for e in eshiklar}
    mesh_qutisi: dict[int, tuple[Nuqta, Nuqta] | None] = {}
    for f in furnitura:
        if f.group is None or f.group in panel_birlik:
            continue
        if f.mesh not in mesh_qutisi:
            uchlar = [
                _uch(q.positions[i : i + 3]) for q in meshlar[f.mesh].parts for i in range(0, len(q.positions), 3)
            ]
            mesh_qutisi[f.mesh] = _quti(uchlar) if uchlar else None
        yerli = mesh_qutisi[f.mesh]
        if yerli is None:
            continue
        (a0, a1) = _dunyo_qutisi(f.pos, f.quat, *yerli)
        rf, _ = _harakat(_uch(f.pos), _tort(f.quat), _uch(f.pos_open), _tort(f.quat_open))
        mos = [
            e
            for e in eshiklar
            if all(a0[i] - 1.0 <= e[0][1][i] and e[0][0][i] - 1.0 <= a1[i] for i in range(3))
            and all(abs(x - y) < 1e-3 for x, y in zip(rf, e[1], strict=True))
        ]
        if not mos:
            continue
        # Ikki eshikka tegsa (fiksator ikki fasad chegarasida, 4 ta) — markazi yaqinrog'i
        markaz = tuple((a0[i] + a1[i]) / 2 for i in range(3))
        _, r, t, birlik = min(
            mos,
            key=lambda e: sum(max(e[0][0][i] - markaz[i], 0.0, markaz[i] - e[0][1][i]) ** 2 for i in range(3)),
        )
        rp = _kvat_burash(r, _uch(f.pos))
        f.pos_open = [round(rp[i] + t[i], 2) for i in range(3)]
        f.quat_open = [round(v, 6) for v in _kvat_kopaytir(r, _tort(f.quat))]
        f.group = birlik


def _harakat(pos: Nuqta, quat: Kvat, opos: Nuqta, oquat: Kvat) -> tuple[Kvat, Nuqta]:
    """Yopiqdan ochiqqa DUNYODAGI qattiq harakat: burilish `r` va siljish `t`."""
    r = _kvat_kopaytir(oquat, (-quat[0], -quat[1], -quat[2], quat[3]))
    if r[3] < 0:  # q va -q — bitta burilish
        r = (-r[0], -r[1], -r[2], -r[3])
    rp = _kvat_burash(r, pos)
    return r, (opos[0] - rp[0], opos[1] - rp[1], opos[2] - rp[2])


def _bir_xil(r1: Kvat, t1: Nuqta, r2: Kvat, t2: Nuqta) -> bool:
    return all(abs(a - b) < 1e-4 for a, b in zip(r1, r2, strict=True)) and all(
        abs(a - b) < 0.1 for a, b in zip(t1, t2, strict=True)
    )


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
    panellar, furnitura, meshlar, olchamlar, chala = _panellar(model.daraxt(_TOXTASH))
    if chala:
        model.warnings.append(f"{chala} ta detal konturi to'liq o'qilmadi")

    return ParsedBazis(
        code=_matn(maqola, "Code"),
        name=_matn(maqola, "Name"),
        order_name=_matn(maqola, "OrderName"),
        thumbnail=eskiz if isinstance(eskiz, bytes) else b"",
        panels=panellar,
        meshes=meshlar,
        furniture=furnitura,
        dims=olchamlar,
        warnings=model.warnings,
    )
