"""CS `data` blob decoder (TZ 5.7): base64, UNENCRYPTED big-endian binary.

Grammar verified byte-for-byte on 1144 patterns / 398 blobs; zero unknown bytes remain.
This replaces the licensed GibCut/GibSaw station (~$4000) — MANDATORY for the ARRA post.

Layout:
    u32=0, u32=1, u8=3, u32=N_pattern                # global header (constants)
    N × pattern block, each addressed relative to `dims`:
        u32  mult          @dims-4    # pattern is cut on `mult` sheets; Σ = cMaterialCount
        f64  L, W          @dims,+8   # sheet size
        u32  stock_part_id @dims+16
        u8   0             @dims+20
        4×f64 = -1.0       @dims+21   # signature (dims is found 21 bytes before it)
        ... statistics block (see fields below) ...
        u32  Nr            @dims+113  # record count INCLUDING the slot
        15B  slot          @dims+117  # ROOT-AXIS MARKER (TZ 5.7.3)
        (Nr-1) × 15B       @dims+132  # preorder guillotine tree

15-byte record: u8 tag (depth = tag>>3, type = tag&7), f64 value (strip size, mm),
u8 flag (0), u8 qty, i32 part_id (-1 = structural).
Types: 1=trim/kerf strip · 2=inner strip with children · 3=part · 4=registered waste.
"""

import base64
import struct
from dataclasses import dataclass, field

from .models import ParseError

_REC = struct.Struct(">BdBBi")  # tag, value, flag, qty, part_id — 15 bytes


@dataclass
class BlobRecord:
    depth: int
    type: int  # 1 trim · 2 strip · 3 part · 4 waste
    value: float
    qty: int
    part_id: int
    children: list["BlobRecord"] = field(default_factory=list)


@dataclass
class BlobPattern:
    mult: int
    length: float
    width: float
    stock_part_id: int
    part_count: int
    waste_area: float
    part_area: float
    waste_count: int
    packets: int
    cut_length_m: float
    cut_count: int
    filling: float
    root_axis_vertical: bool  # True → first cuts are vertical (along X)
    leading_trim: float | None  # slot-encoded 2mm trim (not repeated in the stream)
    records: list[BlobRecord] = field(default_factory=list)  # depth-1 roots (tree built)


def _u32(raw: bytes, off: int) -> int:
    return int(struct.unpack_from(">I", raw, off)[0])


def _f64(raw: bytes, off: int) -> float:
    return float(struct.unpack_from(">d", raw, off)[0])


def _parse_record(raw: bytes, off: int) -> tuple[int, int, float, int, int]:
    tag, value, _flag, qty, part_id = _REC.unpack_from(raw, off)
    return tag >> 3, tag & 7, value, qty, part_id


def _build_tree(flat: list[tuple[int, int, float, int, int]]) -> list[BlobRecord]:
    """Preorder + explicit depth → tree. Depth starts at 1 for top-level strips."""
    roots: list[BlobRecord] = []
    stack: list[BlobRecord] = []
    for depth, rtype, value, qty, part_id in flat:
        node = BlobRecord(depth=depth, type=rtype, value=value, qty=qty, part_id=part_id)
        while stack and stack[-1].depth >= depth:
            stack.pop()
        if not stack:
            roots.append(node)
        else:
            stack[-1].children.append(node)
        stack.append(node)
    return roots


def decode_cs_blob(b64: str) -> list[BlobPattern]:
    try:
        raw = base64.b64decode(b64)
    except Exception as exc:
        raise ParseError(f"CS data blob base64 emas: {exc}") from exc

    if len(raw) < 13 or _u32(raw, 0) != 0 or _u32(raw, 4) != 1 or raw[8] != 3:
        raise ParseError("CS data blob sarlavhasi noto'g'ri (0,1,3 kutilgan edi).")
    n_patterns = _u32(raw, 9)

    patterns: list[BlobPattern] = []
    off = 13
    for idx in range(n_patterns):
        dims = off + 4
        if dims + 132 > len(raw):
            raise ParseError(f"CS blob qisqa: {idx + 1}-pattern sarlavhasi sig'maydi.")
        for k in range(4):
            if _f64(raw, dims + 21 + 8 * k) != -1.0:
                raise ParseError(f"CS blob imzosi topilmadi ({idx + 1}-pattern, dims+21).")

        nr = _u32(raw, dims + 113)
        if nr < 1:
            raise ParseError(f"CS blob: {idx + 1}-patternda yozuvlar yo'q.")

        slot = _parse_record(raw, dims + 117)
        slot_depth, slot_type, slot_value = slot[0], slot[1], slot[2]
        # Root axis (TZ 5.7.3): null slot (type=1, v=0) → horizontal first cuts;
        # a depth-1 trim record → vertical, and the slot IS the leading 2mm trim.
        # Torsovkasiz vertikal xaritada (205-korpus: XDF listlar) yetakchi qirqim yo'q —
        # slot birinchi HAQIQIY yozuvning o'zi (polosa/detal/qoldiq) bo'lib keladi; uni
        # daraxtga birinchi bo'lib qo'shamiz, aks holda birinchi polosa butunlay yo'qolardi.
        slot_rec = None
        if slot_type == 1 and slot_value == 0:
            root_vertical = False
            leading_trim = None
        elif slot_depth == 1 and slot_type == 1:
            root_vertical = True
            leading_trim = slot_value
        elif slot_depth == 1 and slot_type in (2, 3, 4):
            root_vertical = True
            leading_trim = None
            slot_rec = slot
        else:
            raise ParseError(f"CS blob: {idx + 1}-pattern root-o'q sloti noma'lum (tag turi {slot_type}).")

        rec_off = dims + 132
        end = rec_off + 15 * (nr - 1)
        if end > len(raw):
            raise ParseError(f"CS blob qisqa: {idx + 1}-pattern yozuvlari sig'maydi.")
        flat = [_parse_record(raw, rec_off + 15 * j) for j in range(nr - 1)]
        if slot_rec is not None:
            flat.insert(0, slot_rec)

        patterns.append(
            BlobPattern(
                mult=_u32(raw, off),
                length=_f64(raw, dims),
                width=_f64(raw, dims + 8),
                stock_part_id=_u32(raw, dims + 16),
                part_count=_u32(raw, dims + 53),
                waste_area=_f64(raw, dims + 57),
                part_area=_f64(raw, dims + 69),
                waste_count=_u32(raw, dims + 77),
                packets=_u32(raw, dims + 89),
                cut_length_m=_f64(raw, dims + 93),
                cut_count=_u32(raw, dims + 101),
                filling=_f64(raw, dims + 105),
                root_axis_vertical=root_vertical,
                leading_trim=leading_trim,
                records=_build_tree(flat),
            )
        )
        off = end

    if off != len(raw):
        raise ParseError(f"CS blob oxirida {len(raw) - off} bayt ortiqcha qoldi — format mos emas.")
    return patterns


def self_check(patterns: list[BlobPattern], stats: dict[str, float]) -> list[str]:
    """TZ 5.7.4 equalities. Any mismatch marks the file as broken (returned as messages).

    Note: cWasteCount is mult-multiplied in the CS attribute, but per-pattern wasteCount
    is NOT — the comparison must apply mult (TZ 5.3.4).
    """
    problems: list[str] = []

    def close(a: float, b: float, tol: float = 0.05) -> bool:
        return abs(a - b) <= tol

    if stats.get("cMaterialCount"):
        total = sum(p.mult for p in patterns)
        if total != int(stats["cMaterialCount"]):
            problems.append(f"Σ mult={total} ≠ cMaterialCount={stats['cMaterialCount']:.0f}")
    if stats.get("cPartCount"):
        total = sum(p.part_count for p in patterns)
        if total != int(stats["cPartCount"]):
            problems.append(f"Σ partCount={total} ≠ cPartCount={stats['cPartCount']:.0f}")
    if stats.get("cCountPackets"):
        total = sum(p.packets for p in patterns)
        if total != int(stats["cCountPackets"]):
            problems.append(f"Σ packets={total} ≠ cCountPackets={stats['cCountPackets']:.0f}")
    if stats.get("cWasteAmount"):
        total_f = sum(p.waste_area * p.mult for p in patterns)
        if not close(total_f, stats["cWasteAmount"]):
            problems.append(f"Σ wasteArea×mult={total_f:.3f} ≠ cWasteAmount={stats['cWasteAmount']:.3f}")
    if stats.get("cPartAmount"):
        total_f = sum(p.part_area * p.mult for p in patterns)
        if not close(total_f, stats["cPartAmount"]):
            problems.append(f"Σ partArea×mult={total_f:.3f} ≠ cPartAmount={stats['cPartAmount']:.3f}")
    if stats.get("cTrimLength"):
        total_f = sum(p.cut_length_m for p in patterns)
        if not close(total_f, stats["cTrimLength"], tol=0.5):
            problems.append(f"Σ cutLength={total_f:.2f} ≠ cTrimLength={stats['cTrimLength']:.2f}")
    if stats.get("cTrimCount"):
        total = sum(p.cut_count for p in patterns)
        if total != int(stats["cTrimCount"]):
            problems.append(f"Σ cutCount={total} ≠ cTrimCount={stats['cTrimCount']:.0f}")
    return problems
