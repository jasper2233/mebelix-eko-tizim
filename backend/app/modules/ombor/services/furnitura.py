"""Buyurtma furniturasi: fayldan (`order.material_usage`, kroy bilan almashadi) va qo'lda (`buyurtma_furnitura`).

Qo'lda qo'shilgani alohida saqlanadi — qayta yuborilgan kroy uni o'chirmasin. Rezerv ikkalasini bitta kalit bo'yicha
qo'shib hisoblaydi (`rezerv.reserve_for_order`), shuning uchun bir xil furnituraning miqdori jamlanadi.
Har o'zgarishdan keyin rezerv qayta quriladi: katalogdan tanlangani darhol band bo'ladi, yo'g'i Ta'minotga tushadi.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, NotFoundException
from app.models import Order, User
from app.models.enums import OrderStatus
from app.modules.ombor.models import BuyurtmaFurnitura, CatalogItem, MaterialMap, Rezerv, RezervLine
from app.modules.ombor.services import rezerv
from app.modules.ombor.services.rezerv import usage_key

#: Furnitura katalogi: `F` guruhi, kromkasiz (kromka o'z yo'li bilan keladi)
KATALOG = "F"
KROMKA_GURUH = "F-KM-%"
#: Topshirilgan va bekor qilingan buyurtma yopiq; qoralama hali texnologda emas
OCHIQ = {OrderStatus.TECHNICAL_REVIEW, OrderStatus.PRODUCTION, OrderStatus.COMPLETED}
_HARDWARE = "hardware"


@dataclass
class Taklif:
    item_id: int
    code: str
    name: str
    unit: str
    qoldiq: Decimal
    erkin: Decimal


@dataclass
class Qator:
    id: int | None
    manba: str
    kalit: str
    code: str | None
    nom: str
    soni: Decimal
    birlik: str
    item_id: int | None
    kim: str | None
    vaqt: datetime | None
    moslangan: bool
    kerak: Decimal
    qoplangan: Decimal
    berilgan: Decimal


async def qidir(db: AsyncSession, q: str, limit: int = 20) -> list[Taklif]:
    """Kod, artikul yoki nomning bir qismi bo'yicha (aniq kod birinchi). Erkin — boshqa rezervlardan tashqari."""
    t = q.strip()
    if len(t) < 2:
        return []
    naqsh = "%" + t.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    rows = (
        (
            await db.execute(
                select(CatalogItem)
                .where(
                    CatalogItem.catalog == KATALOG,
                    CatalogItem.is_deleted == False,  # noqa: E712
                    CatalogItem.code.not_ilike(KROMKA_GURUH),
                    or_(
                        CatalogItem.code.ilike(naqsh, escape="\\"),
                        CatalogItem.name.ilike(naqsh, escape="\\"),
                        CatalogItem.article.ilike(naqsh, escape="\\"),
                    ),
                )
                .order_by(
                    (func.lower(CatalogItem.code) == t.lower()).desc(), CatalogItem.quantity.desc(), CatalogItem.name
                )
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    band = await rezerv.reserved_qty(db, [r.id for r in rows])
    return [
        Taklif(
            item_id=r.id,
            code=r.code,
            name=r.name,
            unit=r.unit or "dona",
            qoldiq=r.quantity,
            erkin=max(r.quantity - band.get(r.id, Decimal(0)), Decimal(0)),
        )
        for r in rows
    ]


async def qolda_qatorlar(db: AsyncSession, order_id: int) -> list[BuyurtmaFurnitura]:
    return list(
        (
            await db.execute(
                select(BuyurtmaFurnitura)
                .where(BuyurtmaFurnitura.order_id == order_id, BuyurtmaFurnitura.is_deleted == False)  # noqa: E712
                .order_by(BuyurtmaFurnitura.id)
            )
        ).scalars()
    )


def _fayldan(order: Order) -> list[dict[str, Any]]:
    return [m for m in order.material_usage or [] if m.get("kind") == _HARDWARE]


async def _oxirgi_rezerv(db: AsyncSession, order_id: int) -> Rezerv | None:
    return (
        await db.execute(
            select(Rezerv)
            .where(Rezerv.order_id == order_id, Rezerv.is_deleted == False)  # noqa: E712
            .order_by(Rezerv.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def royxat(db: AsyncSession, order: Order) -> list[Qator]:
    """Fayldagi va qo'lda qo'shilgan furnitura; rezerv ustunlari — shu kalitning UMUMIY qatoridan."""
    rez = await _oxirgi_rezerv(db, order.id)
    lines: dict[str, RezervLine] = {}
    if rez is not None:
        lines = {
            ln.tashqi_kalit: ln
            for ln in (
                await db.execute(
                    select(RezervLine).where(
                        RezervLine.rezerv_id == rez.id,
                        RezervLine.kind == _HARDWARE,
                        RezervLine.is_deleted == False,  # noqa: E712
                    )
                )
            ).scalars()
        }

    def qator(
        kalit: str,
        id_: int | None,
        manba: str,
        code: str | None,
        nom: str,
        soni: Decimal,
        birlik: str,
        kim: str | None,
        vaqt: datetime | None,
        item_id: int | None,
    ) -> Qator:
        ln = lines.get(kalit)
        return Qator(
            id=id_,
            manba=manba,
            kalit=kalit,
            code=code,
            nom=nom,
            soni=soni,
            birlik=birlik,
            item_id=ln.item_id if ln is not None else item_id,
            kim=kim,
            vaqt=vaqt,
            moslangan=ln is not None and ln.item_id is not None,
            kerak=ln.kerak_qty if ln is not None else Decimal(0),
            qoplangan=ln.qoplangan_qty if ln is not None else Decimal(0),
            berilgan=ln.berilgan_qty if ln is not None else Decimal(0),
        )

    out = [
        qator(
            usage_key(m.get("code"), str(m["name"])),
            None,
            "fayl",
            m.get("code"),
            str(m["name"]),
            Decimal(str(m.get("count") or 0)),
            str(m.get("unit") or "dona"),
            None,
            None,
            None,
        )
        for m in _fayldan(order)
    ]
    qolda = await qolda_qatorlar(db, order.id)
    users = {
        u.id: u.name or u.username
        for u in (await db.execute(select(User).where(User.id.in_([f.yaratgan_id for f in qolda])))).scalars()
    }
    for f in qolda:
        out.append(
            qator(
                f.kalit,
                f.id,
                "qolda",
                f.code,
                f.nom,
                f.soni,
                f.birlik,
                users.get(f.yaratgan_id) if f.yaratgan_id else None,
                f.created_at,
                f.item_id,
            )
        )
    return out


async def _ochiq_order(db: AsyncSession, order_id: int) -> Order:
    """Bir buyurtmaning furniturasi ketma-ket o'zgaradi: rezerv qurilishi va jamlash poygaga tushmasin."""
    order = (
        await db.execute(
            select(Order).where(Order.id == order_id, Order.is_deleted == False).with_for_update()  # noqa: E712
        )
    ).scalar_one_or_none()
    if order is None:
        raise NotFoundException("Buyurtma topilmadi.")
    if order.status not in OCHIQ:
        raise ForbiddenException("Furnitura faqat tasdiqlangan va hali topshirilmagan buyurtmaga qo'shiladi.")
    return order


async def _fayldagi_soni(db: AsyncSession, order: Order, kalit: str, item_id: int | None) -> tuple[Decimal, str]:
    """Fayldan shu furnituradan qancha kelgan: kalit bir xil yoki moslash orqali o'sha katalog pozitsiyasi."""
    fayl = _fayldan(order)
    kalitlar = {usage_key(m.get("code"), str(m["name"])) for m in fayl}
    bir_xil = {kalit}
    if item_id is not None and kalitlar:
        bir_xil |= set(
            (
                await db.execute(
                    select(MaterialMap.tashqi_kalit).where(
                        MaterialMap.kind == _HARDWARE,
                        MaterialMap.item_id == item_id,
                        MaterialMap.tashqi_kalit.in_(kalitlar),
                        MaterialMap.is_deleted == False,  # noqa: E712
                    )
                )
            ).scalars()
        )
    jami, birlik = Decimal(0), ""
    for m in fayl:
        if usage_key(m.get("code"), str(m["name"])) in bir_xil:
            jami += Decimal(str(m.get("count") or 0))
            birlik = str(m.get("unit") or "")
    return jami, birlik


async def qosh(
    db: AsyncSession, order_id: int, item_id: int | None, nom: str | None, soni: Decimal, user_id: int
) -> tuple[Order, BuyurtmaFurnitura, str | None]:
    """Yangi qator yoki mavjudiga qo'shish. Uchinchi qiymat — fayldan ham kelgan bo'lsa ogohlantirish."""
    order = await _ochiq_order(db, order_id)
    if item_id is not None:
        item = await db.get(CatalogItem, item_id)
        if item is None or item.is_deleted:
            raise NotFoundException("Katalog pozitsiyasi topilmadi.")
        kalit, code, nomi, birlik = usage_key(item.code, item.name), item.code, item.name, item.unit or "dona"
    else:
        nomi = " ".join((nom or "").split())
        if len(nomi) < 2:
            raise ForbiddenException("Furnitura nomini yozing yoki katalogdan tanlang.")
        kalit, code, birlik = usage_key(None, nomi), None, "dona"
    bor = next((f for f in await qolda_qatorlar(db, order.id) if f.kalit == kalit), None)
    if bor is not None:
        bor.soni += soni
        row = bor
    else:
        row = BuyurtmaFurnitura(
            order_id=order.id,
            item_id=item_id,
            kalit=kalit,
            code=code,
            nom=nomi,
            soni=soni,
            birlik=birlik,
            yaratgan_id=user_id,
        )
        db.add(row)
    await db.flush()
    await rezerv.reserve_for_order(db, order)
    fayldan, fb = await _fayldagi_soni(db, order, kalit, item_id)
    ogoh = None
    if fayldan > 0:
        jami = _son(fayldan + row.soni)
        ogoh = f"Kroyda bu furnituradan {_son(fayldan)} {fb} bor edi: jami {jami} {birlik} kerak bo'ladi."
    return order, row, ogoh


def _son(v: Decimal) -> str:
    return format(v.normalize(), "f").replace(".", ",")


async def _qator(db: AsyncSession, order_id: int, qator_id: int) -> BuyurtmaFurnitura:
    row = await db.get(BuyurtmaFurnitura, qator_id)
    if row is None or row.is_deleted or row.order_id != order_id:
        raise NotFoundException("Furnitura qatori topilmadi.")
    return row


async def _berilgandan_kam_emas(db: AsyncSession, order: Order, row: BuyurtmaFurnitura, yangi: Decimal) -> None:
    """Omborchi bergan miqdordan kamaytirib bo'lmaydi: shu kalitning umumiy ehtiyoji berilgandan past tushmasin."""
    rez = await _oxirgi_rezerv(db, order.id)
    if rez is None:
        return
    ln = (
        await db.execute(
            select(RezervLine).where(
                RezervLine.rezerv_id == rez.id,
                RezervLine.kind == _HARDWARE,
                RezervLine.tashqi_kalit == row.kalit,
                RezervLine.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if ln is None or ln.berilgan_qty <= 0 or ln.fayl_qty <= 0:
        return
    # Fayl birligiga o'giriladi: moslash koeffitsienti kerak_qty / fayl_qty da turadi
    koef = ln.kerak_qty / ln.fayl_qty
    if (ln.fayl_qty - row.soni + yangi) * koef < ln.berilgan_qty:
        raise ForbiddenException(
            f"Omborchi {_son(ln.berilgan_qty)} {row.birlik} berib bo'lgan: bundan kam qilib bo'lmaydi. "
            "Avval omborchi «Material berish» sahifasida ortig'ini omborga qaytarsin."
        )


async def ozgartir(db: AsyncSession, order_id: int, qator_id: int, soni: Decimal) -> tuple[Order, BuyurtmaFurnitura]:
    order = await _ochiq_order(db, order_id)
    row = await _qator(db, order.id, qator_id)
    await _berilgandan_kam_emas(db, order, row, soni)
    row.soni = soni
    await db.flush()
    await rezerv.reserve_for_order(db, order)
    return order, row


async def ochir(db: AsyncSession, order_id: int, qator_id: int) -> tuple[Order, BuyurtmaFurnitura]:
    order = await _ochiq_order(db, order_id)
    row = await _qator(db, order.id, qator_id)
    await _berilgandan_kam_emas(db, order, row, Decimal(0))
    row.is_deleted = True
    await db.flush()
    await rezerv.reserve_for_order(db, order)
    return order, row
