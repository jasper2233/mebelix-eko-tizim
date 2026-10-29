"""MX Kroy qoldiq ombori (K3, `MES_QOLDIQ_V1.md`): MES — ombor ustasi, MX shu yerdan qidiradi, band qiladi,
kroydan keyin kirim/chiqim hujjatini yuboradi va bekor qiladi. `map.done` (karta listi arradan chiqdi) bo'lak
ulushini `kutish` dan `ombor` ga o'tkazadi.

Qoidalar (shartnoma §«Biznes qoidalari»):
- material faqat aynan o'zi — kod bo'yicha, kod bo'lmasa nom bo'yicha (katta-kichik harf va bo'shliqsiz);
- `kutish` dagi bo'lak boshqa buyurtmaga berilmaydi va band qilinmaydi;
- band — MX loyihasi bo'yicha (`project_id`); boshqa loyiha bandi — 409 `conflicts`;
- bo'lak butunligicha sotiladi: `consumed` dagi dona ombordan chiqadi, bekor qilinsa qaytadi.

Funksiyalar sessiyada ishlaydi va `commit` qilmaydi.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Integer, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order
from app.modules.ombor.models import CatalogItem, KroyIntake, OmborBolak
from app.modules.ombor.models.bolak import BEKOR, ISHLATILDI, KUTISH, OMBOR


class KroyError(Exception):
    """MX ga qaytariladigan rad sababi (400)."""


@dataclass
class Conflict:
    id: int
    order_number: str | None


def norm(s: str | None) -> str:
    """«LDSP KASHMIR SHAGREN» = «ldsp  kashmir shagren» (shartnoma 6-qoida)."""
    return re.sub(r"\s+", "", (s or "")).lower()


def status(b: OmborBolak) -> str:
    if b.joy == OMBOR and b.qty > 0:
        return "reserved" if b.band_loyiha else "available"
    if b.qty_pending > 0:
        return "pending"
    return "empty"


def item(b: OmborBolak, code: str | None = None) -> dict[str, Any]:
    return {
        "id": b.id,
        "material_code": b.material_kod or code or b.material_nom,
        "material_name": b.material_nom,
        "type": b.tur,
        "length": float(b.uzunlik),
        "width": float(b.eni),
        "thickness": float(b.qalinlik) if b.qalinlik is not None else None,
        "qty": b.qty if b.joy == OMBOR else 0,
        "qty_pending": b.qty_pending,
        "status": status(b),
        "sheet_area_m2": float(b.list_m2) if b.list_m2 is not None else None,
        "reserved_project": b.band_loyiha,
        "reserved_number": b.band_raqam,
        "note": b.izoh,
        "source_project": b.mx_loyiha,
        "source_number": b.mx_raqam,
        "source_map": b.karta,
        "linear": b.chiziqli,
        "clean_edges": b.toza_chet,
        "created_at": b.created_at.isoformat(),
    }


async def _order(db: AsyncSession, info: dict[str, Any]) -> Order | None:
    """MX buyurtma ma'lumotidan MES buyurtmasi: `mes_order_ref` = MES buyurtma id yoki raqami (`B-2026-101`)."""
    ref = str(info.get("mes_order_ref") or "").strip()
    if not ref:
        return None
    q = select(Order).where(Order.is_deleted == False)  # noqa: E712
    q = q.where(Order.id == int(ref)) if ref.isdigit() else q.where(Order.number == ref)
    return (await db.execute(q)).scalar_one_or_none()


async def search(
    db: AsyncSession,
    *,
    ids: list[int] | None = None,
    material: str | None = None,
    code: str | None = None,
    type_: str | None = None,
    thickness: Decimal | None = None,
    status_: str | None = None,
    linear: bool | None = None,
) -> list[dict[str, Any]]:
    q = (
        select(OmborBolak, CatalogItem.code)
        .outerjoin(CatalogItem, CatalogItem.id == OmborBolak.item_id)
        .where(OmborBolak.is_deleted == False, OmborBolak.joy.in_((OMBOR, KUTISH)))  # noqa: E712
    )
    if ids:
        q = q.where(OmborBolak.id.in_(ids))
    if linear is not None:
        q = q.where(OmborBolak.chiziqli == linear)
    if thickness:
        q = q.where(or_(OmborBolak.qalinlik.is_(None), OmborBolak.qalinlik == thickness))
    out = []
    want_code, want_name, want_type = norm(code), norm(material), norm(type_)
    for b, cat_code in (await db.execute(q.order_by(OmborBolak.id))).all():
        if want_code:
            if want_code not in (norm(b.material_kod), norm(cat_code)):
                continue
        elif want_name and norm(b.material_nom) != want_name:
            continue
        if want_type and b.tur and norm(b.tur) != want_type:
            continue
        d = item(b, cat_code)
        if status_ and d["status"] != status_:
            continue
        out.append(d)
    return out


async def reserve(db: AsyncSession, order: dict[str, Any], ids: list[int], mode: str) -> list[Conflict]:
    """`add` | `remove` | `set`. Boshqa loyiha bandi yoki `kutish` dagi bo'lak — konflikt (hech narsa o'zgarmaydi)."""
    pid = str(order.get("project_id") or "").strip()
    if not pid:
        raise KroyError("order.project_id bo'sh")
    number = str(order.get("number") or "")[:40] or None
    rows = {
        b.id: b
        for b in (
            await db.execute(
                select(OmborBolak)
                .where(
                    or_(OmborBolak.id.in_(ids), OmborBolak.band_loyiha == pid),
                    OmborBolak.is_deleted == False,  # noqa: E712
                )
                .order_by(OmborBolak.id)
                .with_for_update()
            )
        ).scalars()
    }
    if mode == "remove":
        for i in ids:
            b = rows.get(i)
            if b is not None and b.band_loyiha == pid:
                b.band_loyiha = b.band_raqam = None
        await db.flush()
        return []
    conflicts = []
    for i in ids:
        b = rows.get(i)
        if b is None or b.joy != OMBOR or b.qty <= 0:
            conflicts.append(Conflict(i, None))
        elif b.band_loyiha and b.band_loyiha != pid:
            conflicts.append(Conflict(i, b.band_raqam))
    if conflicts:
        return conflicts
    if mode == "set":
        for b in rows.values():
            if b.band_loyiha == pid and b.id not in ids:
                b.band_loyiha = b.band_raqam = None
    for i in ids:
        rows[i].band_loyiha, rows[i].band_raqam = pid, number
    await db.flush()
    return []


async def _next_no(db: AsyncSession, year: int) -> str:
    prefix = f"IN-{year}-"
    await db.execute(select(func.pg_advisory_xact_lock(func.hashtext(prefix))))
    last = await db.scalar(
        select(func.max(cast(func.split_part(KroyIntake.no, "-", 3), Integer))).where(KroyIntake.no.like(f"{prefix}%"))
    )
    return f"{prefix}{(last or 0) + 1:04d}"


def _dec(v: Any) -> Decimal | None:
    return None if v in (None, "") else Decimal(str(v))


async def intake(db: AsyncSession, body: dict[str, Any]) -> tuple[str, list[int]]:
    """Kroydan keyin: `pieces` → `kutish` bo'laklar, `consumed` → ishlatilgan ombor bo'laklari (shu loyiha bandi)."""
    order, op = body.get("order") or {}, body.get("op") or {}
    pid = str(order.get("project_id") or "").strip()
    if not pid:
        raise KroyError("order.project_id bo'sh")
    mes_order = await _order(db, order)
    consumed = [{"id": int(c["id"]), "qty": int(c.get("qty") or 1)} for c in body.get("consumed") or []]
    used = {
        b.id: b
        for b in (
            await db.execute(select(OmborBolak).where(OmborBolak.id.in_([c["id"] for c in consumed])).with_for_update())
        ).scalars()
    }
    for c in consumed:
        b = used.get(c["id"])
        if b is None or b.joy != OMBOR or b.qty < c["qty"]:
            raise KroyError(f"qoldiq {c['id']}: omborda yo'q yoki yetarli emas")
        if b.band_loyiha and b.band_loyiha != pid:
            raise KroyError(f"qoldiq {c['id']}: boshqa loyihaga band ({b.band_raqam})")
    now = datetime.now(UTC)
    doc = KroyIntake(
        no=await _next_no(db, now.year),
        mx_loyiha=pid,
        order_id=mes_order.id if mes_order else None,
        payload=body,
        consumed=consumed,
    )
    db.add(doc)
    await db.flush()
    for c in consumed:
        b = used[c["id"]]
        b.qty -= c["qty"]
        b.band_loyiha = b.band_raqam = None
        b.order_id = mes_order.id if mes_order else b.order_id
        if b.qty == 0 and b.qty_pending == 0:
            b.joy, b.yopilgan_at = ISHLATILDI, now
    ids = []
    for n, p in enumerate(body.get("pieces") or [], start=1):
        b = OmborBolak(
            barkod=f"MX-{doc.no}-{n}",
            material_nom=str(op.get("name") or "")[:150],
            material_kod=str(op.get("code") or "")[:60],
            tur=str(op.get("type") or "")[:20],
            qalinlik=_dec(op.get("thickness")),
            uzunlik=Decimal(str(p["length"])),
            eni=Decimal(str(p["width"])),
            qty=0,
            qty_pending=int(p.get("qty") or 1),
            jami=int(p.get("qty") or 1),
            manba_order_id=mes_order.id if mes_order else None,
            joy=KUTISH,
            manba="mx",
            kirim_id=doc.no,
            karta=int(p["map"]) if p.get("map") is not None else None,
            nusxa=max(int(p.get("copies") or 1), 1),
            mx_loyiha=pid,
            mx_op=str(op.get("id") or "")[:40] or None,
            mx_raqam=str(order.get("number") or "")[:40] or None,
            chiziqli=bool(op.get("linear", False)),
            toza_chet=True,
            list_m2=_dec(body.get("sheet_area_m2")),
            foiz=_dec(p.get("percent")),
            m2_narx=_dec(body.get("m2_price")),
            izoh=f"{order.get('number') or ''} · karta {p.get('map')}"[:200],
        )
        db.add(b)
        await db.flush()
        ids.append(b.id)
    return doc.no, ids


async def cancel(db: AsyncSession, no: str) -> KroyIntake:
    """Kirimni bekor qiladi: hali ishlatilmagan bo'laklar `bekor`, ishlatilganlar omborga qaytadi."""
    doc = (await db.execute(select(KroyIntake).where(KroyIntake.no == no).with_for_update())).scalar_one_or_none()
    if doc is None:
        raise KroyError(f"{no}: kirim topilmadi")
    if doc.holat == "bekor":
        return doc  # takror bekor — xavfsiz
    now = datetime.now(UTC)
    for b in (await db.execute(select(OmborBolak).where(OmborBolak.kirim_id == no).with_for_update())).scalars():
        if b.order_id is None and not b.band_loyiha:
            b.joy, b.qty, b.qty_pending, b.yopilgan_at = BEKOR, 0, 0, now
        # boshqa buyurtmaga ketgan yoki band bo'lgani — jismonan bor, tegilmaydi (hisobotda ko'rinadi)
    for c in doc.consumed:
        ub = await db.get(OmborBolak, c["id"], with_for_update=True)
        if ub is not None:
            ub.qty += c["qty"]
            ub.joy, ub.yopilgan_at = OMBOR, None
            if ub.order_id == doc.order_id:
                ub.order_id = None
    doc.holat = "bekor"
    await db.flush()
    return doc


async def map_done(db: AsyncSession, mx_loyiha: str, mx_op: str, karta: int, done_count: int) -> int:
    """Karta listi arradan `done_count` marta chiqdi: shu karta bo'laklarining ulushi `ombor` ga o'tadi.
    Ulush = jami × done / nusxa (takroriy signal xavfsiz — jami holat bo'yicha). Qaytaradi: o'tgan dona."""
    moved = 0
    for b in (
        await db.execute(
            select(OmborBolak)
            .where(
                OmborBolak.mx_loyiha == mx_loyiha,
                OmborBolak.mx_op == mx_op,
                OmborBolak.karta == karta,
                OmborBolak.manba == "mx",
                OmborBolak.joy.in_((KUTISH, OMBOR)),
                OmborBolak.is_deleted == False,  # noqa: E712
            )
            .with_for_update()
        )
    ).scalars():
        tayyor = min(b.jami, b.jami * max(done_count, 0) // b.nusxa)
        ochilgan = b.jami - b.qty_pending
        if tayyor > ochilgan:
            n = min(tayyor - ochilgan, b.qty_pending)
            moved += n
            b.qty_pending -= n
            b.qty += n
            b.joy = OMBOR
    await db.flush()
    return moved
