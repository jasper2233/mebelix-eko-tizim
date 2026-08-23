"""Parsed .project data structures (TZ 5). Plain dataclasses — no ORM here."""

from dataclasses import dataclass, field
from typing import Any

from app.models.enums import PostCode


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
    width: float | None = None
    length: float | None = None
    count: float | None = None  # sheets used / band meters bought


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


@dataclass
class ParsedPart:
    file_part_id: int  # NOT stable across files — only for intra-file references (TZ 5.1.2)
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
    xnc_ops: list[XncOp] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.product_code}_{self.code}"

    @property
    def qr_texts(self) -> list[str]:
        """Nusxa QR'lari (TZ 5.8): yagona nusxa suffikssiz — chekdagi kod, QR va SCX fayl
        nomi bir xil bo'ladi (Nanxing skan mosligi); takrorlanganda _1.._n."""
        return [self.key] if self.count == 1 else [f"{self.key}_{n}" for n in range(1, self.count + 1)]

    @property
    def kromka_sides(self) -> int:
        return len(self.edges)

    def merged_machining(self) -> XncOp | None:
        """Union of ALL XNC ops (not just two) for the holes overlay; duplicate bores removed (TZ 5.7.5)."""
        if not self.xnc_ops:
            return None
        base = XncOp(code=self.key, side2=False, dx=self.xnc_ops[0].dx, dy=self.xnc_ops[0].dy, dz=self.xnc_ops[0].dz)
        seen_bores: set[tuple[float, float, float, bool]] = set()
        seen_edge: set[tuple[str, float, float, float]] = set()
        for op in self.xnc_ops:
            for b in op.bores:
                sig = (round(b["x"], 2), round(b["y"], 2), b["d"], b["thru"])
                if sig not in seen_bores:
                    seen_bores.add(sig)
                    base.bores.append(b)
            for b in op.edge_bores:
                sig = (b["side"], round(b["pos"], 2), b["d"], round(b["dp"], 2))
                if sig not in seen_edge:
                    seen_edge.add(sig)
                    base.edge_bores.append(b)
            base.grooves.extend(op.grooves)
            base.mills.extend(op.mills)
        return base

    def stage_sides(self) -> dict[PostCode, int]:
        """post_code -> per-instance scan count for XNC stages (TZ 5.4.3, 7.3.3).

        FAQAT PRISADKA — ROVER bosqichi ataylab yaratilmaydi: roverdan chiqqan detal
        keyin bo'yalishi ham mumkin, ya'ni QOLGAN marshrutni fayldan chiqarib
        bo'lmaydi. Uni texnolog chizadi.

        Qadam HAR QANDAY ishlov uchun ochiladi: teshik, paz yoki freza. Ilgari
        faqat TESHIK hisobga olinardi va paz/freza-only detal marshrutsiz qolardi:
        SCX fayli yaratilar, lekin uni bajaradigan post yo'q edi — detal
        ARRA -> TMO bo'ylab ishlov KO'RMASDAN o'tib ketardi va buni hech kim
        sezmasdi. 3152 buyurtmasida shunday ikki detal bor edi (har birida 7 paz).
        """
        result: dict[PostCode, int] = {}
        for op in self.xnc_ops:
            if op.bores or op.edge_bores or op.grooves or any(op.mills):
                result[PostCode.PRISADKA] = result.get(PostCode.PRISADKA, 0) + 1
        return result


@dataclass
class ParsedProduct:
    code: str
    name: str
    count: int
    parts: list[ParsedPart] = field(default_factory=list)


@dataclass
class CutOperation:
    """CS operation: one per sheet material (TZ 5.2.5)."""

    op_id: int
    material_name: str
    thickness: float | None
    kerf: float  # tool.cutting swSawthick — the ONLY source (TZ 5.3.4)
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
