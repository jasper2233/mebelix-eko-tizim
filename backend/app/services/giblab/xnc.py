"""XNC program parsing (TZ 5.5): the `program` attribute is an escaped inner XML document."""

import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import Any

from .models import ParseError, XncOp, xml_bool

# Safe arithmetic: numbers, identifiers (dz, throughBoreDepth...), + - * / ( ) . and spaces only.
_EXPR_RE = re.compile(r"^[\w\s+\-*/().]+$")
_NAME_DIGITS = re.compile(r"(\d+(?:\.\d+)?)")

_EDGE_TAGS = {"bt": "t", "bb": "b", "bl": "l", "br": "r"}

# GibLab spetsifikatsiyasi (help/format_ru.html) XNC dasturi uchun shu teglarni beradi:
# program, tool, bf, bl, br, bt, bb, ms, ml, ma, mac, gr, xy (+ real fayllarda var, oq, oh).
# Biz `ma` (yoy bo'ylab frezalash) va `xy` (koordinata boshi) ni HISOBLAMAYMIZ — korpusdagi
# 8 faylda ular umuman uchramaydi. Uchrasa quyidagi `else` shoxi ularni yig'adi va parser
# ogohlantiradi, ya'ni jimgina buzilmaydi.


def _eval_expr(expr: str, env: dict[str, float]) -> float:
    """Evaluate a coordinate/depth expression like 'dz+3' or 'dx-34' against dx/dy/dz + vars."""
    expr = expr.strip()
    try:
        return float(expr)
    except ValueError:
        pass
    # `**` charset'dan o'tadi ("* *") — 9**9**9 kabi ifoda eval'da workerni
    # osiltirib qo'yardi (DoS). Arifmetikada daraja ishlatilmaydi — taqiq.
    if not _EXPR_RE.match(expr) or "**" in expr:
        raise ParseError(f"XNC ifodasi xavfsiz emas: {expr!r}")
    try:
        return float(eval(expr, {"__builtins__": {}}, env))  # noqa: S307 — charset-whitelisted arithmetic
    except Exception as exc:
        raise ParseError(f"XNC ifodasini hisoblab bo'lmadi: {expr!r}") from exc


def _tool_diameter(name: str | None, tools: dict[str, float]) -> float | None:
    """The <tool> table's d attribute is the primary source; the digits in the name match it 100%
    in the corpus (TZ 5.6.4) and serve as fallback."""
    if not name:
        return None
    if name in tools:
        return tools[name]
    m = _NAME_DIGITS.search(name)
    return float(m.group(1)) if m else None


_Num = Callable[..., float]


def _hole_array(el: ET.Element, num: _Num) -> tuple[int, float, bool]:
    """`ac` (soni), `as` (qadam), `av` (vertikal=true) — bitta element teshik QATORINI
    bildiradi; 32 mm javon teshiklari aynan shunday beriladi. Qadam bo'lmasa qator yo'q.
    Korpusda `ac` doim 1 (3382 holat), lekin qator ishlatilsa ilgari bitta teshik
    chizilardi va SCX'ga ham bittasi tushardi."""
    count = int(num(el, "ac", 1))
    step = num(el, "as", 0.0)
    if count < 2 or step <= 0:
        return 1, 0.0, False
    return count, step, xml_bool(el.get("av"))


def _add_face_bores(el: ET.Element, op: XncOp, num: _Num, tools: dict[str, float], dz: float) -> None:
    dp = num(el, "dp")
    bx, by = num(el, "x"), num(el, "y")
    n_holes, step, vertical = _hole_array(el, num)
    d = _tool_diameter(el.get("name"), tools) or 0.0
    for i in range(n_holes):
        shift = step * i
        op.bores.append(
            {
                "x": bx + (0.0 if vertical else shift),
                "y": by + (shift if vertical else 0.0),
                "d": d,
                "dp": dp,
                "thru": dp >= dz,
            }
        )


def _add_edge_bores(el: ET.Element, side: str, op: XncOp, num: _Num, tools: dict[str, float], dz: float) -> None:
    # bt/bb carry x; bl/br carry y — only the along-edge coordinate exists (TZ 5.5)
    pos = num(el, "x") if side in ("t", "b") else num(el, "y")
    dp = num(el, "dp")
    # `m` (Середина по Z, default true): true -> teshik qalinlik MARKAZIDA, `z` e'tiborsiz;
    # false -> `z` absolyut balandlik. 205-korpus buni bir ma'noda ko'rsatadi: `m=false` faqat
    # markazdan chetlashganda yoziladi (z=7.5/8.5/10...), `m=true` da esa `z=16 dz=16` (yuzada —
    # imkonsiz) ham uchraydi, ya'ni GibLab uni o'qimaydi. Ilgari `z` doim absolyut olinardi —
    # 32 mm qo'shqavat plitada (310 teshik) markaz o'rniga 8 mm da burg'ulanardi.
    z_raw = num(el, "z", dz / 2)  # meros zanjiri uchun baribir o'qiymiz
    z = dz / 2 if xml_bool(el.get("m"), True) else z_raw
    d = _tool_diameter(el.get("name"), tools) or 0.0
    n_holes, step, _vertical = _hole_array(el, num)
    for i in range(n_holes):
        # Chetda yagona o'q bor — qator shu o'q bo'ylab ketadi
        op.edge_bores.append({"side": side, "pos": pos + step * i, "z": z, "d": d, "dp": dp, "thru": False})


def _groove(el: ET.Element, num: _Num) -> dict[str, Any]:
    """Paz. `x2`/`y2` yozilmasa SHU elementning `x1`/`y1` i olinadi (spetsifikatsiya) —
    bu umumiy "oldingi element" merosidan farq qiladi, shuning uchun atribut borligini
    o'zimiz tekshiramiz: aks holda oldingi pazning oxiri olinib paz noto'g'ri chizilardi."""
    x1, y1 = num(el, "x1"), num(el, "y1")
    return {
        "x1": x1,
        "y1": y1,
        "x2": num(el, "x2") if el.get("x2") is not None else x1,
        "y2": num(el, "y2") if el.get("y2") is not None else y1,
        "dp": num(el, "dp"),
        # `c` (korreksiya) korpusda doim 0 = markaz bo'yicha; 1/2 bo'lsa paz t/2 ga suriladi
        "t": num(el, "t", 4),
    }


def parse_xnc_program(code: str, program_xml: str, side: str | None = None) -> XncOp:
    try:
        root = ET.fromstring(program_xml)
    except ET.ParseError as exc:
        raise ParseError(f"XNC dasturi buzilgan ({code}): {exc}") from exc

    # Old generation uses l/w/thick, new uses dx/dy/dz (corpus has both).
    dx = float(root.get("dx") or root.get("l") or 0)
    dy = float(root.get("dy") or root.get("w") or 0)
    dz = float(root.get("dz") or root.get("thick") or 0)
    # GibLab standart konstantalari. Yangi eksport ularni <var> bilan e'lon qiladi, eski
    # (version 21052101) esa e'lonsiz ishlatadi — o'shanda dastur hisoblanmay qolardi.
    # Qiymatlar korpusdagi barcha e'lonlardan olingan va bir xil: throughBoreDepth/
    # throughCutDepth = dz+3.00, contMillDepth = dz. <var> bo'lsa u baribir ustun keladi.
    env: dict[str, float] = {
        "dx": dx,
        "dy": dy,
        "dz": dz,
        "throughBoreDepth": dz + 3.0,
        "throughCutDepth": dz + 3.0,
        "contMillDepth": dz,
    }

    tools: dict[str, float] = {}
    # Tomonning YAGONA ishonchli manbasi — operatsiyaning `side` atributi (spetsifikatsiya:
    # default true = litsevaya). Eski eksport uni `1`/`0` deb yozadi. Kod suffiksi endi faqat
    # zaxira: korpusda `2001_Nukriddin` orqa tomonni `x2` bilan tugatadi (`_2` emas), ya'ni 26
    # dastur old tomon deb belgilanardi; `3052_Hikmat` da esa old va orqa dasturning kodi AYNAN
    # bir xil bo'lib, ikkalasi bitta SCX nomiga yozilib biri o'chib ketardi.
    side2 = not xml_bool(side, True) if side is not None else code.endswith("_2")
    op = XncOp(code=code, side2=side2, dx=dx, dy=dy, dz=dz)
    current_contour: list[dict[str, Any]] = []

    # Spetsifikatsiya (help/format_ru.html, "XNC программа"): dp/ac/as/z/x/y kabi
    # atribut YOZILMASA "oldingi qiymat" olinadi. Meros TEG bo'yicha yuritiladi —
    # aks holda pazning chuqurligi keyingi teshikka o'tib ketardi. Korpusda meros
    # ishlatilmagan (burg'ulashda dp/x/y doim yozilgan), lekin ilgali bu yerda
    # ParseError bor edi: merosli fayl BUTUNLAY rad etilardi.
    last: dict[tuple[str, str], float] = {}

    def num(el: ET.Element, attr: str, default: float | None = None) -> float:
        raw = el.get(attr)
        if raw is None:
            if (el.tag, attr) in last:
                return last[(el.tag, attr)]
            if default is None:
                raise ParseError(f"XNC ({code}): <{el.tag}> da {attr} yo'q")
            return default
        value = _eval_expr(raw, env)
        last[(el.tag, attr)] = value
        return value

    for el in root:
        tag = el.tag
        # `enable="false"` — element o'chirilgan (default true). Uni bajarsak GibLab
        # ataylab o'chirgan teshik/pazni chizib, SCX'ga ham qo'shib qo'yardik.
        if not xml_bool(el.get("enable"), True):
            continue
        if tag == "tool":
            name, d = el.get("name"), el.get("d")
            if name and d:
                tools[name] = float(d)
        elif tag == "var":
            name, expr = el.get("name"), el.get("expr")
            if name and expr:
                env[name] = _eval_expr(expr, env)
        elif tag == "bf":
            _add_face_bores(el, op, num, tools, dz)
        elif tag in _EDGE_TAGS:
            _add_edge_bores(el, _EDGE_TAGS[tag], op, num, tools, dz)
        elif tag == "gr":
            op.grooves.append(_groove(el, num))
        elif tag == "ms":
            current_contour = [
                {
                    "op": "ms",
                    "x": num(el, "x"),
                    "y": num(el, "y"),
                    "dp": num(el, "dp", dz),
                    "c": el.get("c"),
                    "d": _tool_diameter(el.get("name"), tools) or 0.0,
                }
            ]
            op.mills.append(current_contour)
        elif tag == "ml":
            if not current_contour:
                current_contour = [{"op": "ms", "x": 0.0, "y": 0.0, "dp": dz, "c": None, "d": 0.0}]
                op.mills.append(current_contour)
            current_contour.append({"op": "ml", "x": num(el, "x"), "y": num(el, "y")})
        elif tag == "mac":
            if current_contour:
                current_contour.append(
                    {
                        "op": "mac",
                        "x": num(el, "x"),
                        "y": num(el, "y"),
                        "cx": num(el, "cx"),
                        "cy": num(el, "cy"),
                        "dir": xml_bool(el.get("dir")),
                    }
                )
        # oq/oh (saw/groove tools of old generation) intentionally map to grooves too
        elif tag in ("oq", "oh"):
            op.grooves.append(
                {
                    "x1": num(el, "x1", 0),
                    "y1": num(el, "y1", 0),
                    "x2": num(el, "x2", 0),
                    "y2": num(el, "y2", 0),
                    "dp": num(el, "dp", 0),
                    "t": num(el, "t", 4),
                }
            )
        else:
            # Bilmagan tegni jimgina tashlash xavfli: masalan <xy> (koordinata boshi)
            # e'tiborsiz qolsa undan keyingi BARCHA teshik joylari xato hisoblanadi.
            # Yig'ib olamiz, parser bir marta ogohlantiradi.
            op.unknown_tags.add(tag)

    return op


def apply_mirror(op: XncOp, mir_hor: bool, mir_vert: bool) -> None:
    """Operatsiyadagi mirHor/mirVert ni geometriyaga QO'LLAYDI (TZ 5.6.4).

    GibLab bunday dasturni eksportda aks ettirib chiqaradi — biz ham parse
    bosqichida normallashtiramiz, shunda SCX, yorliq va kesish xaritasi
    teshiklari bir xil (to'g'ri) koordinatada bo'ladi. mirHor: x' = dx − x,
    qirralar l↔r; mirVert: y' = dy − y, qirralar t↔b; yoy yo'nalishi har
    aks ettirishda teskarilanadi.
    """
    if not (mir_hor or mir_vert):
        return
    L, W = op.dx, op.dy

    def mx(x: float) -> float:
        return L - x if mir_hor else x

    def my(y: float) -> float:
        return W - y if mir_vert else y

    for b in op.bores:
        b["x"], b["y"] = mx(b["x"]), my(b["y"])
    side_map: dict[str, str] = {}
    if mir_hor:
        side_map.update({"l": "r", "r": "l"})
    if mir_vert:
        side_map.update({"t": "b", "b": "t"})
    for b in op.edge_bores:
        side = b["side"]
        b["side"] = side_map.get(side, side)
        # pos o'qi: l/r uchun y bo'ylab, t/b uchun x bo'ylab
        if side in ("t", "b"):
            b["pos"] = mx(b["pos"])
        else:
            b["pos"] = my(b["pos"])
    for g in op.grooves:
        g["x1"], g["x2"] = mx(g["x1"]), mx(g["x2"])
        g["y1"], g["y2"] = my(g["y1"]), my(g["y2"])
    flip_dir = mir_hor != mir_vert  # bitta aks ettirish orientatsiyani teskarilaydi
    for contour in op.mills:
        for seg in contour:
            if "x" in seg:
                seg["x"], seg["y"] = mx(seg["x"]), my(seg["y"])
            if seg.get("op") == "mac":
                seg["cx"], seg["cy"] = mx(seg["cx"]), my(seg["cy"])
                if flip_dir:
                    seg["dir"] = not bool(seg["dir"])


def merge_xnc_ops(ops: list[XncOp]) -> list[XncOp]:
    """Detalning BARCHA XNC operatsiyalari saqlanadi; 'oxirgisi yutadi' — taqiqlangan
    xato (TZ 5.2.7). Tartib: asosiy tomon, keyin _2.

    Korpusda ko'pi bilan ikkita uchraydi, lekin GibLab ko'proq beradi: yorliq shabloni
    XNC1..XNC5 maydonlarini taklif qiladi (help/labels_ru.html). Ilgari bu yerda ikkitadan
    ko'pi uchun ParseError bor edi — ya'ni uch tomoni ishlanadigan detal bo'lsa BUTUN fayl
    import bo'lmasdi. Cheklov TZ talabi emas, korpus kuzatuvidan qotib qolgan edi.
    `stage_sides()` N ta operatsiyani baribir to'g'ri sanaydi (har biri +1 skan).
    """
    return sorted(ops, key=lambda o: (o.side2, o.code))
