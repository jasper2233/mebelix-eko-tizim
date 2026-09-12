"""Parsed .project data structures. Plain dataclasses — no ORM here."""

import re
from dataclasses import dataclass, field
from typing import Any

from app.models.enums import PostCode

# Nusxa ID = `{buyurtma}_{productCode}_{partCode}[_n]` (docs/11). Buyurtma qismi ID'ni
# GLOBAL unikal qiladi: bir .project ikki buyurtmaga yuklansa cheklar bir xil QR olmaydi.
# Uchala funksiya bir joyda — Nanxing Panel ID `-` ni qabul qilmasa `order_token`
# ixchamlanadi (`B2026047`) va ORDER_PREFIX_RE shunga moslanadi, boshqa kod tegmaydi.
ORDER_PREFIX_RE = re.compile(r"^B-\d{4}-\d+_")


def order_token(number: str) -> str:
    return number


def instance_qr(order_number: str, key: str, n: int | None) -> str:
    """Nusxa QR'i: yagona nusxa suffikssiz, takrorlanganda `_n`."""
    return f"{order_token(order_number)}_{key}" + ("" if n is None else f"_{n}")


def strip_order_prefix(qr: str) -> str:
    """Nusxa QR'idan buyurtma prefiksini oladi: `B-2026-047_100701_03_002` -> `100701_03_002`.

    Detal kodi shu yerdan chiqadi (`scanning.py: qr_part_code`) — terminal jadvalida
    «Kod» ustuni prefikssiz ko'rinadi. Prefiks bo'lmasa satr o'zgarmaydi: 2026-09-04
    gacha yuklangan cheklar prefikssiz edi (2026-09-05 da prodda bunday jonli nusxa
    0 ta qoldi — MVP ma'lumotlari tozalandi), lekin shart himoya sifatida qoladi:
    ATX chiqindi yorlig'i va qo'lda kiritilgan kod ham shu yo'ldan o'tadi.
    """
    return ORDER_PREFIX_RE.sub("", qr, count=1)


class ParseError(ValueError):
    """User-facing parse failure; message is shown to the texnolog (Uzbek)."""


def xml_bool(raw: str | None, default: bool = False) -> bool:
    """GibLab mantiqiy qiymatni `true`/`false` ham, `1`/`0` ham yozadi — bitta faylda ikkisi
    birga uchraydi (`csTexture="true"` yonida `cCostByItem="1"`, XNC da `side="1"`). Faqat
    `"true"` ni tekshirish yetmaydi: `enable="0"` bo'lsa GibLab o'chirgan teshik teshilib,
    `av="1"` bo'lsa teshik qatori noto'g'ri yo'nalishda chizilardi."""
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "1")


#: Tsexning "Jarayon uchun kodlar" jadvali: jarayon kodi -> post kodi.
#: Bir nechta jarayon bitta postga tushadi (45° kesish ham arrada, 6 xil
#: stolyarka amali ham bitta postda) — qaysi amal ekanini `PartRoute.process_code`
#: saqlaydi, post kodining o'zi yetarli emas.
PROCESS_POSTS: dict[int, PostCode] = {
    1: PostCode.ARRA,  # Raspil
    2: PostCode.ARRA,  # 45° kesiladigan detallar
    3: PostCode.KROMKA,  # Kromka
    4: PostCode.KROMKA,  # Fasat kromka
    5: PostCode.OVAL,  # Oval kromka
    6: PostCode.PRISADKA,  # Prisadka
    7: PostCode.ROVER,  # Rover
    8: PostCode.BOYOQ,  # Bo'yoq
    9: PostCode.STOLYARKA,  # Baget
    10: PostCode.STOLYARKA,  # Utalshonka
    11: PostCode.STOLYARKA,  # G petlya o'ngdan
    12: PostCode.STOLYARKA,  # G petlya chapdan
    13: PostCode.STOLYARKA,  # V petlya o'ngdan
    14: PostCode.STOLYARKA,  # V petlya chapdan
    #: Qadoqlash tsexning varag'ida yo'q — u jarayon emas, oxirgi bosqich.
    #: Kod kerak, chunki har marshrut qadami `process_code` saqlaydi; texnolog
    #: uni qo'lda tanlamaydi (anketadagi bayroq qo'shadi).
    15: PostCode.UPAKOVKA,  # Qadoqlash
    16: PostCode.TMO,  # TMO qabuli
}

#: Marshrut DUMI — texnolog tanlamaydigan, tizim qo'shadigan qadamlar.
#: Ular saqlangan marshrutga kirmaydi: qayta yuklashda qaytadan qo'shiladi
#: (aks holda har yuklashda ikkilanib borardi).
TAIL_CODES = (15, 16)

#: Jarayon nomlari — xato matnlarida raqam o'rniga amal nomi chiqishi uchun
#: ("«Utalshonka» yo'q" — texnolog qaysi tugmani bosishini biladi). Frontenddagi
#: `PROCESS_OPS` bilan bir xil ro'yxat.
PROCESS_NAMES: dict[int, str] = {
    1: "Raspil",
    2: "45° kesish",
    3: "Kromka",
    4: "Fasat kromka",
    5: "Oval kromka",
    6: "Prisadka",
    7: "Rover",
    8: "Bo'yoq",
    9: "Baget",
    10: "Utalshonka",
    11: "G petlya o'ngdan",
    12: "G petlya chapdan",
    13: "V petlya o'ngdan",
    14: "V petlya chapdan",
    15: "Qadoqlash",
    16: "TMO qabuli",
}

#: Post -> shu postning ODATDAGI jarayon kodi. Bitta postda bir necha amal bo'lgani uchun
#: (STOLYARKA da 6 ta, KROMKA da 2 ta) faqat post nomidan kod tiklab bo'lmaydi — bu jadval
#: aniq amal tanlanmagan holat uchun zaxira qiymat beradi.
DEFAULT_PROCESS_CODE: dict[PostCode, int] = {}
for _code, _post in PROCESS_POSTS.items():
    DEFAULT_PROCESS_CODE.setdefault(_post, _code)


@dataclass
class ParsedMaterial:
    kind: str  # "sheet" | "band" | "hardware"
    name: str
    code: str | None = None
    thickness: float | None = None
    count: float | None = None  # sheets used / band meters bought


#: Paz/freza qirraga «tegdi» deb sanaladigan masofa (mm). Qirra profili asbobi qirraning
#: O'ZIDA yuradi (markaz radius qadar ichkarida), 12 mm — 16 mm li frezaning yarmi + zaxira.
#: Ilgari 25 mm edi va qirradan 18 mm ichkaridagi DVP pazini ham «qirra» deb belgilardi.
_QIRRA_TASMASI = 12.0
#: Qirra ishlangan deb sanalishi uchun eng kam qamrov: o'lchamning yarmi, LEKIN 300 mm dan
#: ko'p emas. Ulush yolg'iz bo'lsa uzun detalda yiqiladi — 2170 mm li detalning qirrasidagi
#: 514 mm falts 0.24 ulush bilan tushib qolardi (prodda o'lchangan).
_QIRRA_ULUSHI = 0.5
_QIRRA_MIN_MM = 300.0


@dataclass
class XncOp:
    """One <operation typeId="XNC"> after program XML is parsed. Usually two (front + back), but
    GibLab writes more (XNC1..XNC5) — `merge_xnc_ops` keeps them all, `parser` only warns."""

    code: str
    side2: bool  # back side — `side` attribute of the operation, code suffix only as fallback
    dx: float
    dy: float
    dz: float
    bores: list[dict[str, Any]] = field(default_factory=list)  # {x, y, d, dp, thru}
    edge_bores: list[dict[str, Any]] = field(default_factory=list)  # {side, pos, z, d, dp, thru}
    grooves: list[dict[str, Any]] = field(default_factory=list)  # {x1, y1, x2, y2, dp, t}
    mills: list[list[dict[str, Any]]] = field(default_factory=list)  # contours: [{op, x, y, cx, cy, dir, dp}]
    unknown_tags: set[str] = field(default_factory=set)  # dasturda o'qilmagan teglar (ogohlantirish uchun)

    def machined_sides(self, length: float | None, width: float | None) -> list[str]:
        """Paz/freza QAYSI QIRRA bo'ylab ketadi — `l`/`r`/`t`/`b`, tartiblangan.

        .project faylida tomon ATRIBUT sifatida yo'q (`<gr>` da faqat x1/y1/x2/y2,
        frezada esa kontur nuqtalari) — lekin geometriyadan kelib chiqadi.

        Qoida KESMALAR bo'yicha: kesmaning IKKALA uchi ham qirradan `_QIRRA_TASMASI`
        mm ichida bo'lsa, uning qirra bo'ylab uzunligi qo'shiladi; yig'indi
        `_QIRRA_ULUSHI` ulushiga (lekin ko'pi bilan `_QIRRA_MIN_MM`) yetsa — qirra
        ishlanadi. NUQTALAR bulutini olish YARAMAYDI: konturning kirish nuqtasi
        (lead-in, masalan y=-10) tasmaga tushib, o'sha qirra bo'ylab hech qanday yo'l
        bo'lmasa ham uni «ishlangan» qilib yuborardi — prodda 1200x350 detalda to'rt
        qirraning to'rtalasi ham belgilanib ketgan edi (aslida uchtasi).

        Asbob qirradan TASHQARIGA chiqadi (radius va kirish-chiqish), shuning uchun
        tashqi chegara qo'yilmaydi: 170 mm li detalda kontur X=174 bo'lishi normal.

        O'q konvensiyasi `scx.py` dagi bilan bir xil: dasturda `y=0` — `t` qirrasi,
        `y=width` — `b` (shu sabab `scx.py` t ni `Y=Width` ga flip qiladi).

        Qirradan uzoqdagi paz (detal o'rtasidagi ariq, DVP uchun 18 mm ichkaridagi
        yiv) ro'yxatga tushmaydi — u kromkachining ishi emas.
        """
        if not length or not width:
            return []
        # Tasma detal o'lchamidan kelib chiqib CHEKLANADI: eni 50 mm dan tor plankada
        # qat'iy 25 mm ikkala uzun qirradan ham ichkariga tushib, O'RTADAGI pazni
        # ikkala qirraga ham yozib qo'yardi (o'lchangan). Uchdan bir — tasma hech
        # qachon detalning yarmidan oshmaydi, ya'ni ikki qirra kesishmaydi.
        tasma_x = min(_QIRRA_TASMASI, length / 3)
        tasma_y = min(_QIRRA_TASMASI, width / 3)
        kesmalar: list[tuple[float, float, float, float]] = []
        for g in self.grooves:
            kesmalar.append((g["x1"], g["y1"], g["x2"], g["y2"]))
        for contour in self.mills:
            nuqta = [(q["x"], q["y"]) for q in contour if q.get("x") is not None and q.get("y") is not None]
            kesmalar += [(a[0], a[1], b[0], b[1]) for a, b in zip(nuqta, nuqta[1:], strict=False)]

        topildi: list[str] = []
        for tomon, yaqinmi, boylab, olcham in (
            ("l", lambda x, y: x <= tasma_x, lambda x, y: y, width),
            ("r", lambda x, y: x >= length - tasma_x, lambda x, y: y, width),
            ("t", lambda x, y: y <= tasma_y, lambda x, y: x, length),
            ("b", lambda x, y: y >= width - tasma_y, lambda x, y: x, length),
        ):
            qoplam = sum(
                abs(boylab(x2, y2) - boylab(x1, y1))
                for x1, y1, x2, y2 in kesmalar
                if yaqinmi(x1, y1) and yaqinmi(x2, y2)
            )
            if qoplam >= min(olcham * _QIRRA_ULUSHI, _QIRRA_MIN_MM):
                topildi.append(tomon)
        return topildi


@dataclass
class ParsedPart:
    file_part_id: int  # NOT stable across files — only for intra-file references
    product_code: str
    code: str
    name: str
    count: int
    length: float | None  # l (finished)
    width: float | None  # w
    thickness: float | None  # sheet t
    txt: bool
    material_name: str | None  # sheet good name
    edges: dict[str, dict[str, Any]]  # side(l/r/t/b) -> {"mat": name, "symbol": A}
    label_num: int | None = None  # CS stub order, file-global 1-based
    # `usedCount="0"` -> GibLab detalni ataylab joylashtirmagan (material yetmagan yoki
    # dizayner chiqarib tashlagan). Ro'yxatda turishi joylashtirilganini bildirmaydi (docs/10 §3.1).
    placed: bool = True
    xnc_ops: list[XncOp] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.product_code}_{self.code}"

    @property
    def qr_texts(self) -> list[str]:
        """Fayl darajasidagi nusxa kalitlari (buyurtmasiz): faqat fayl ichidagi to'qnashuv tekshiruvi uchun."""
        return [self.key] if self.count == 1 else [f"{self.key}_{n}" for n in range(1, self.count + 1)]

    def serial_qrs(self, order_number: str) -> list[str]:
        """Haqiqiy nusxa QR'lari — chek, QR, SCX fayl nomi va Panel ID bir xil satr."""
        if self.count == 1:
            return [instance_qr(order_number, self.key, None)]
        return [instance_qr(order_number, self.key, n) for n in range(1, self.count + 1)]

    @property
    def kromka_sides(self) -> int:
        return len(self.edges)

    def merged_machining(self) -> XncOp | None:
        """Union of ALL XNC ops (not just two) for the holes overlay; duplicate bores removed."""
        if not self.xnc_ops:
            return None
        base = XncOp(code=self.key, side2=False, dx=self.xnc_ops[0].dx, dy=self.xnc_ops[0].dy, dz=self.xnc_ops[0].dz)
        seen_bores: set[tuple[float, float, float, bool]] = set()
        seen_edge: set[tuple[str, float, float, float, float]] = set()
        for op in self.xnc_ops:
            for b in op.bores:
                sig = (round(b["x"], 2), round(b["y"], 2), b["d"], b["thru"])
                if sig not in seen_bores:
                    seen_bores.add(sig)
                    base.bores.append(b)
            for b in op.edge_bores:
                #: `z` imzoda SHART: qo'shqavat plitada bir tomonda bir xil pos/d/dp li,
                #: lekin turli balandlikdagi teshiklar real — z'siz ikkinchisi yo'qolardi.
                esig = (b["side"], round(b["pos"], 2), b["d"], round(b["dp"], 2), round(b["z"], 2))
                if esig not in seen_edge:
                    seen_edge.add(esig)
                    base.edge_bores.append(b)
            base.grooves.extend(op.grooves)
            base.mills.extend(op.mills)
        return base

    def prisadka_passes(self) -> int:
        """PRISADKA qadami bormi: 1 — bitta skan (ikki yuzli ham), 0 — qadam yo'q (7.3.3).

        FAQAT PRISADKA — ROVER bosqichi ataylab yaratilmaydi: roverdan chiqqan detal
        keyin bo'yalishi ham mumkin, ya'ni QOLGAN marshrutni fayldan chiqarib
        bo'lmaydi. Uni texnolog chizadi.

        Qadam HAR QANDAY ishlov uchun ochiladi: teshik, paz yoki freza. Ilgari
        faqat TESHIK hisobga olinardi va paz/freza-only detal marshrutsiz qolardi:
        SCX fayli yaratilar, lekin uni bajaradigan post yo'q edi — detal
        ARRA -> TMO bo'ylab ishlov KO'RMASDAN o'tib ketardi va buni hech kim
        sezmasdi. 3152 buyurtmasida shunday ikki detal bor edi (har birida 7 paz).
        """
        # BITTA skan — yuzlar soni emas: SCX ikkala yuzni (old + orqa `_2`) bitta faylga
        # birlashtiradi (scx.py, Face="6"), stanok bitta yurgizishda ag'darib ishlaydi. Ilgari
        # old+orqa = 2 talab qilinar, prisadkachi bitta detalni «0/2 — 2 ta detal» deb ko'rardi.
        return int(any(op.bores or op.edge_bores or op.grooves or any(op.mills) for op in self.xnc_ops))


@dataclass
class ParsedProduct:
    code: str
    name: str
    count: int
    parts: list[ParsedPart] = field(default_factory=list)


@dataclass
class CutOperation:
    """CS operation: one per sheet material."""

    op_id: int
    material_name: str
    thickness: float | None
    kerf: float  # tool.cutting swSawthick — the ONLY source
    trim_l: float
    trim_w: float
    stats: dict[str, float]  # cPartCount, cMaterialCount, cWasteAmount, ... (GibSaw indicators)
    data_blob: str | None  # base64; None on TEMPLATE files
    waste_parts: dict[int, dict[str, float]] = field(default_factory=dict)  # waste part defs by id


@dataclass
class ParsedProject:
    uuid: str | None
    name: str | None
    generation: str  # "processed" | "template"
    products: list[ParsedProduct] = field(default_factory=list)
    materials: list[ParsedMaterial] = field(default_factory=list)
    cut_ops: list[CutOperation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def all_parts(self) -> list[ParsedPart]:
        return [p for product in self.products for p in product.parts]
