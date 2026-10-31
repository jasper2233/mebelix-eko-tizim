"""MX Kroy paketi v1 → MES ingest tuzilmalari (EKO 3c, K2; shartnoma `MebeliX_Kroy/docs/mebelix/MES_PAKET_V1.md`).

Paket `.project` faylining o'rnini bosadi: kroy MX da qilinadi, natija shu JSON bilan keladi. Bu modul uni
`ingest_project` tushunadigan shaklga o'giradi — ikkinchi ingest YO'Q:

- `products[]`, `parts[]` → `ParsedProduct` / `ParsedPart` (kalit `{mahsulot}_{detal}`, QR MES qoidasi bilan)
- `cut_maps[]` → `CutmapResult` (MES `order.cutmap` modeli) va nusxa ↔ katak bog'lanishi
- `remnants[]` → `WasteItem` (`ATX-…` ID MX dan, har jismoniy qoldiq alohida)
- `consumption[]` → `ParsedMaterial` → `order.material_usage` (rezerv shundan, katalog kodi bilan)
- `postprocessor_files[]` → stanok fayllari (sha256 tekshiriladi); CNC fayli kelgan XNC detalga PRISADKA qadami

Qat'iy tekshiruvlar (`ParseError`, o'zbekcha): format/versiya, buyurtma raqami shu buyurtmaniki, har nusxa QR
MES qoidasiga mos (chek = QR = SCX nomi — bitta satr), nusxa soni detal soniga teng, fayl summasi.
"""

import base64
import hashlib
from dataclasses import dataclass, field
from typing import Any

from .cutmap import CutmapResult, InstanceCell
from .models import ParsedMaterial, ParsedPart, ParsedProduct, ParsedProject, ParseError

FORMAT = "mebelix.kroy.mes-package"
VERSION = 1

#: Sarf turi (`consumption[].type`) → material turi (`order.material_usage[].kind`)
_KIND = {"CS": "sheet", "CN": "sheet", "EL": "band", "CL": "linear"}


@dataclass
class StanokFayl:
    format_id: str
    machine_key: str
    machine_name: str
    group: str
    file_name: str
    content: bytes
    sha256: str
    part_keys: list[str] = field(default_factory=list)


@dataclass
class MxPaket:
    project: ParsedProject
    cutmap: CutmapResult
    waste_items: list[dict[str, Any]]
    files: list[StanokFayl]
    project_id: str
    project_number: str
    project_name: str


def _fayllar(pkg: dict[str, Any]) -> list[StanokFayl]:
    """Stanok fayllari: mazmun base64 da, sha256 tekshiriladi."""
    files: list[StanokFayl] = []
    for f in pkg.get("postprocessor_files") or []:
        if f.get("content_base64") is None:
            raise ParseError(f"{f.get('file_name')}: fayl mazmuni yo'q (paket `files=inline` bilan olinishi kerak).")
        raw = base64.b64decode(f["content_base64"])
        if hashlib.sha256(raw).hexdigest() != f.get("sha256"):
            raise ParseError(f"{f.get('file_name')}: nazorat summasi (sha256) mos emas — fayl buzilgan.")
        m = f.get("machine") or {}
        files.append(
            StanokFayl(
                format_id=str(f.get("format_id") or ""),
                machine_key=str(m.get("key") or ""),
                machine_name=str(m.get("label") or m.get("name") or ""),
                group=str(m.get("group") or ""),
                file_name=str(f.get("file_name") or "fayl"),
                content=raw,
                sha256=str(f.get("sha256")),
                part_keys=list(f.get("part_keys") or []),
            )
        )
    return files


def _atx_belgila(model: dict[str, Any], remnants: list[dict[str, Any]]) -> None:
    """Arra terminali qoldiq chekini katakdagi `atx` raqami orqali topadi (`CutmapView`: qr `…-{atx}` + sheet_no)."""
    for r in remnants:
        if not r.get("id") or int(r.get("sheet_copy") or 1) != 1:
            continue
        for mat in model["materials"]:
            for sh in mat["sheets"]:
                if sh["no"] != r.get("sheet_no"):
                    continue
                for cell in sh["parts"]:
                    if cell.get("waste") and cell.get("business") and "atx" not in cell:
                        cw, ch = float(cell["w"]), float(cell["h"])
                        rl, rw = float(r.get("length") or 0), float(r.get("width") or 0)
                        if (abs(cw - rl) <= 1 and abs(ch - rw) <= 1) or (abs(cw - rw) <= 1 and abs(ch - rl) <= 1):
                            cell["atx"] = int(r["n"])
                            break


def parse_package(pkg: dict[str, Any], order_number: str) -> MxPaket:
    head = pkg.get("package") or {}
    if head.get("format") != FORMAT or head.get("version") != VERSION:
        raise ParseError(f"Noma'lum paket: {head.get('format')} v{head.get('version')} (kutilgan {FORMAT} v{VERSION}).")
    src = pkg.get("source") or {}
    if src.get("mes_order_number") != order_number:
        raise ParseError(
            f"Paket {src.get('mes_order_number') or '—'} buyurtmasiniki, bu buyurtma {order_number}. "
            "MX da loyihaning MES buyurtmasi to'g'ri tanlanganini tekshiring."
        )
    mats = {m["ref"]: m for m in pkg.get("materials") or []}
    edges = {e["ref"]: e for e in pkg.get("edge_bands") or []}
    warnings = [str(w) for w in pkg.get("warnings") or []]

    files = _fayllar(pkg)
    cnc_keys = {k for f in files if f.group == "cnc" for k in f.part_keys}

    products: dict[str, ParsedProduct] = {}
    for p in pkg.get("products") or []:
        products[str(p["mx_id"])] = ParsedProduct(
            code=str(p.get("code") or p.get("name") or ""), name=str(p["name"]), count=int(p.get("qty") or 1)
        )
    bindings: list[InstanceCell] = []
    for d in pkg.get("parts") or []:
        product = products.get(str(d.get("product_mx_id")))
        if product is None:
            raise ParseError(f"{d.get('key')}: mahsuloti paketda yo'q.")
        # Yagona nusxada MX `n` yubormaydi (QR suffikssiz, `MES_PAKET_V1` §4.5) — MES da u 1-nusxa
        inst = sorted(d.get("instances") or [], key=lambda i: int(i.get("n") or 1))
        mat = mats.get(d.get("material_ref") or "")
        pp = ParsedPart(
            file_part_id=int(d["mx_uid"]),
            product_code=str(d.get("product_code") or product.code),
            code=str(d["code"]),
            name=str(d.get("name") or ""),
            count=len(inst),
            length=float(d["length"]) if d.get("length") is not None else None,
            width=float(d["width"]) if d.get("width") is not None else None,
            thickness=float(d["thickness"]) if d.get("thickness") is not None else None,
            txt=bool(d.get("grain")),
            material_name=str(mat["name"]) if mat else None,
            edges={
                side: {
                    "mat": str(e.get("name") or edges.get(e.get("ref") or "", {}).get("name") or ""),
                    "symbol": e.get("symbol"),
                }
                for side, e in (d.get("edges") or {}).items()
                if e
            },
            label_num=int(d["mx_uid"]),
            placed=any(i.get("pattern_no") is not None for i in inst),
            forced_passes=1 if d.get("xnc_refs") and d["key"] in cnc_keys else 0,
        )
        if pp.key != d.get("key"):
            raise ParseError(f"{d.get('key')}: detal kaliti {pp.key} ga mos emas.")
        if pp.count == 0:
            warnings.append(f"{pp.key} ({pp.name}): hammasi omborda tayyor — kesilmaydi.")
            continue
        qrs = pp.serial_qrs(order_number)
        for i, want in zip(inst, qrs, strict=True):
            if i.get("qr") != want:
                raise ParseError(f"{pp.key}: nusxa QR {i.get('qr')} MES qoidasiga mos emas (kutilgan {want}).")
            if i.get("pattern_no") is not None:
                bindings.append(
                    InstanceCell(
                        part_key=pp.key,
                        pattern_no=int(i["pattern_no"]),
                        cell_index=int(i["cell_index"]),
                        instance_no=int(i.get("n") or 1),
                    )
                )
        product.parts.append(pp)
    parts_by_key = {pp.key: pp for pr in products.values() for pp in pr.parts}

    model: dict[str, Any] = {"materials": [], "holes": {}}
    for cm in pkg.get("cut_maps") or []:
        mat = mats.get(cm.get("material_ref") or "") or {}
        sheets = []
        for s in cm.get("sheets") or []:
            cells = []
            for c in s.get("cells") or []:
                e: dict[str, Any] = {"cell": c["cell"], "x": c["x"], "y": c["y"], "w": c["w"], "h": c["h"]}
                if c.get("waste"):
                    e.update({"id": 0, "waste": True, "name": "atxot", "business": bool(c.get("business"))})
                    if c.get("remnant_no") is not None:
                        e["remnant_no"] = c["remnant_no"]
                else:
                    part = parts_by_key.get(str(c.get("part_key")))
                    e.update(
                        {
                            "id": part.file_part_id if part else c.get("part_uid"),
                            "key": c.get("part_key"),
                            "num": c.get("part_uid"),
                            "name": part.name if part else "",
                            "rot": bool(c.get("rot")),
                            "waste": False,
                            "eW": c.get("eW") or [None, None],
                            "eH": c.get("eH") or [None, None],
                            "txt": part.txt if part else False,
                        }
                    )
                cells.append(e)
            sheets.append(
                {
                    "no": s["no"],
                    # MX karta manzili — arra «list chiqdi» signali shu bilan MX ga boradi (EKO 3d)
                    "mx_op": cm.get("material_ref"),
                    "mx_index": s.get("index"),
                    "L": s["L"],
                    "W": s["W"],
                    "mult": s.get("mult") or 1,
                    "parts": cells,
                    "dims": [],
                    "cuts": s.get("cuts") or [],
                }
            )
        model["materials"].append({"name": str(mat.get("name") or ""), "sheets": sheets})

    _atx_belgila(model, pkg.get("remnants") or [])

    waste_items = [
        {
            "material_name": str(r.get("material_name") or "")[:150],
            "sheet_no": int(r.get("sheet_no") or 0),
            "length": float(r.get("length") or 0),
            "width": float(r.get("width") or 0),
            "qr_text": str(r["id"]),
        }
        for r in pkg.get("remnants") or []
        if r.get("to_warehouse", True) and r.get("id")
    ]

    materials = [
        ParsedMaterial(
            kind=_KIND.get(str(c.get("type")), "hardware"),
            name=str(c.get("name") or c.get("code") or ""),
            code=str(c.get("code") or "") or None,
            count=float(c.get("qty") or 0),
        )
        for c in pkg.get("consumption") or []
    ]

    # Prisadka qadami faqat stanok fayli bilan ochiladi: fayl kelmasa detal sexda shu postdan jimgina o'tib ketmasin
    faylsiz = [str(d.get("key")) for d in pkg.get("parts") or [] if d.get("xnc_refs") and d.get("key") not in cnc_keys]
    if faylsiz:
        warnings.insert(
            0,
            f"Prisadka qadami ochilmadi: XNC li {len(faylsiz)} ta detalga stanok fayli kelmagan "
            f"({', '.join(faylsiz[:3])}{' …' if len(faylsiz) > 3 else ''}). "
            "MX da prisadka stanogini yoqib, kroyni qayta yuboring.",
        )

    project = ParsedProject(
        uuid=f"mx:{src.get('project_id')}",
        name=str(src.get("project_name") or ""),
        generation="processed",
        products=[p for p in products.values() if p.parts],
        materials=materials,
        warnings=warnings,
    )
    return MxPaket(
        project=project,
        cutmap=CutmapResult(model=model, bindings=bindings),
        waste_items=waste_items,
        files=files,
        project_id=str(src.get("project_id") or ""),
        project_number=str(src.get("project_number") or ""),
        project_name=str(src.get("project_name") or ""),
    )
