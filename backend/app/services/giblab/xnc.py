"""XNC program parsing (TZ 5.5): the `program` attribute is an escaped inner XML document."""

import re
import xml.etree.ElementTree as ET
from typing import Any

from .models import ParseError, XncOp

# Safe arithmetic: numbers, identifiers (dz, throughBoreDepth...), + - * / ( ) . and spaces only.
_EXPR_RE = re.compile(r"^[\w\s+\-*/().]+$")
_NAME_DIGITS = re.compile(r"(\d+(?:\.\d+)?)")

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
    if not _EXPR_RE.match(expr):
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


def parse_xnc_program(code: str, program_xml: str) -> XncOp:
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
    op = XncOp(code=code, side2=code.endswith("_2"), dx=dx, dy=dy, dz=dz)
    current_contour: list[dict[str, Any]] = []

    def num(el: ET.Element, attr: str, default: float | None = None) -> float:
        raw = el.get(attr)
        if raw is None:
            if default is None:
                raise ParseError(f"XNC ({code}): <{el.tag}> da {attr} yo'q")
            return default
        return _eval_expr(raw, env)

    for el in root:
        tag = el.tag
        if tag == "tool":
            name, d = el.get("name"), el.get("d")
            if name and d:
                tools[name] = float(d)
        elif tag == "var":
            name, expr = el.get("name"), el.get("expr")
            if name and expr:
                env[name] = _eval_expr(expr, env)
        elif tag == "bf":
            dp = num(el, "dp")
            op.bores.append(
                {
                    "x": num(el, "x"),
                    "y": num(el, "y"),
                    "d": _tool_diameter(el.get("name"), tools) or 0.0,
                    "dp": dp,
                    "thru": dp >= dz,
                }
            )
        elif tag in ("bt", "bb", "bl", "br"):
            side = {"bt": "t", "bb": "b", "bl": "l", "br": "r"}[tag]
            # bt/bb carry x; bl/br carry y — only the along-edge coordinate exists (TZ 5.5)
            pos = num(el, "x") if tag in ("bt", "bb") else num(el, "y")
            dp = num(el, "dp")
            op.edge_bores.append(
                {
                    "side": side,
                    "pos": pos,
                    "z": num(el, "z", dz / 2),
                    "d": _tool_diameter(el.get("name"), tools) or 0.0,
                    "dp": dp,
                    "thru": False,
                }
            )
        elif tag == "gr":
            op.grooves.append(
                {
                    "x1": num(el, "x1"),
                    "y1": num(el, "y1"),
                    "x2": num(el, "x2"),
                    "y2": num(el, "y2"),
                    "dp": num(el, "dp"),
                    "t": num(el, "t", 4),
                }
            )
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
                        "dir": el.get("dir") == "true",
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


def merge_xnc_ops(ops: list[XncOp]) -> list[XncOp]:
    """A part may carry at most TWO XNC operations (325 corpus cases) — both must be kept;
    'last one wins' is a forbidden bug (TZ 5.2.7). Order: base side first, then _2."""
    if len(ops) > 2:
        raise ParseError(f"Detalda {len(ops)} ta XNC operatsiya — ko'pi bilan 2 bo'lishi kerak")
    return sorted(ops, key=lambda o: o.side2)
