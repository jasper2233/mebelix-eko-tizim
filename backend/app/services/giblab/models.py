"""Parsed .project data structures (TZ 5). Plain dataclasses — no ORM here."""

from dataclasses import dataclass, field
from typing import Any


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


@dataclass
class ParsedMaterial:
    good_id: int
    kind: str  # "sheet" | "band" | "hardware"
    name: str
    code: str | None = None
    thickness: float | None = None
    width: float | None = None
    length: float | None = None
    count: float | None = None  # sheets used / band meters bought


@dataclass
class XncOp:
    """One <operation typeId="XNC"> after program XML is parsed. A part has at most two (TZ 5.2.7)."""

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
    # Ogohlantirish uchun: qirra teshigi qalinlik markazida emas yoki butun dastur
    # aylantirilgan/aks ettirilgan (`turn`/`mirHor`/`mirVert`) — ikkisi ham geometriyani o'zgartiradi.
    notes: set[str] = field(default_factory=set)


@dataclass
class ParsedPart:
    file_part_id: int  # NOT stable across files — only for intra-file references (TZ 5.1.2)
    product_code: str
    code: str
    name: str
    count: int
    length: float | None  # l (finished)
    width: float | None  # w
    saw_length: float | None  # jl
    saw_width: float | None  # jw
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
    def kromka_sides(self) -> int:
        return len(self.edges)

    def merged_machining(self) -> XncOp | None:
        """Union of both XNC sides for the holes overlay; duplicate bores removed (TZ 5.7.5)."""
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

    def stage_sides(self) -> dict[str, int]:
        """post_code -> per-instance scan count for XNC stages (TZ 5.4.3, 7.3.3)."""
        result: dict[str, int] = {}
        for op in self.xnc_ops:
            if op.bores or op.edge_bores:
                result["PRISADKA"] = result.get("PRISADKA", 0) + 1
            if op.grooves:
                result["PAZ"] = result.get("PAZ", 0) + 1
            if op.mills:
                result["ROVER"] = result.get("ROVER", 0) + 1
        return result


@dataclass
class ParsedProduct:
    file_good_id: int
    code: str
    name: str
    count: int
    import_source: str | None
    parts: list[ParsedPart] = field(default_factory=list)


@dataclass
class CutOperation:
    """CS operation: one per sheet material (TZ 5.2.5)."""

    op_id: int
    material_good_id: int
    material_name: str
    thickness: float | None
    kerf: float  # tool.cutting swSawthick — the ONLY source (TZ 5.3.4)
    trim_l: float
    trim_w: float
    stats: dict[str, float]  # cPartCount, cMaterialCount, cWasteAmount, ... (GibSaw indicators)
    data_blob: str | None  # base64; None on TEMPLATE files
    stub_part_ids: list[int] = field(default_factory=list)  # order = label number
    waste_parts: dict[int, dict[str, float]] = field(default_factory=dict)  # waste part defs by id
    stock_parts: dict[int, dict[str, float]] = field(default_factory=dict)


@dataclass
class ParsedProject:
    uuid: str | None
    name: str | None
    generation: str  # "processed" | "template"
    currency: str | None
    version: str | None
    products: list[ParsedProduct] = field(default_factory=list)
    materials: list[ParsedMaterial] = field(default_factory=list)
    cut_ops: list[CutOperation] = field(default_factory=list)
    edge_rest_side: float = 30.0  # tool.edgeline elRestSide
    warnings: list[str] = field(default_factory=list)

    @property
    def all_parts(self) -> list[ParsedPart]:
        return [p for product in self.products for p in product.parts]
