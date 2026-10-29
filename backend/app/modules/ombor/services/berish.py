"""Materialni buyurtmaga (sexga) berish — skaner bilan (EKO TZ §4.4, 2.3-bosqich).

Har berish — SARF: qoldiq kamayadi (FIFO tannarxi bilan), rezerv qatorida `berilgan_qty` o'sadi,
harakat buyurtmaga bog'lanib yoziladi (buyurtma tannarxi). Hamma qator to'liq berilsa rezerv
`sarflandi`.

- **List / panel** (butun birlik): skanerlangan list butunligicha sarflanadi.
- **Rulon** (kromka, metrda): ombordagi rulon skanerlansa — butunligicha SEXGA o'tadi (miqdor
  kamaymaydi, rulon hali bizniki), shundan buyurtmaga kerakli metr sarflanadi; ortgani sexda qoladi.
  Sexdagi rulon skanerlansa — to'g'ridan-to'g'ri undan sarflanadi. Keyingi buyurtma avval sexdagi
  qoldiqdan oladi: berish varaqasi sexdagi rulonlarni birinchi ko'rsatadi.
- **Furnitura** (birliksiz): katalog kodi yoki ishlab chiqaruvchi shtrix-kodi + son.

Berish faqat ishlab chiqarishga darvoza ochiq buyurtmaga (`rezerv.production_block_reason`).
Rezerv qoplamagan qism faqat ERKIN qoldiqdan beriladi — boshqa buyurtmaning bandiga tegilmaydi.

Funksiyalar chaqiruvchining sessiyasida ishlaydi va `commit` qilmaydi.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order
from app.modules.ombor.models import CatalogItem, MaterialBirlik, Rezerv, RezervLine, StockMovement
from app.modules.ombor.models.birlik import OMBOR, SEX, TUGADI
from app.modules.ombor.services import birlik, rezerv
from app.modules.ombor.services.stock import consume, fmt


class BerishError(Exception):
    """Foydalanuvchiga ko'rsatiladigan rad sababi (o'zbekcha)."""


@dataclass
class Natija:
    xabar: str
    #: Shu skan bilan sarflangan miqdor (katalog birligida)
    sarf: Decimal = Decimal(0)
    rulon_qoldi: Decimal | None = None
    ogohlantirish: list[str] = field(default_factory=list)


async def _live(db: AsyncSession, order: Order) -> Rezerv:
    rez = (
        await db.execute(
            select(Rezerv)
            .where(
                Rezerv.order_id == order.id,
                Rezerv.holat.in_((rezerv.FAOL, rezerv.YECHILDI)),
                Rezerv.is_deleted == False,  # noqa: E712
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if rez is None:
        raise BerishError(f"{order.number}: berishga ochiq rezerv yo'q (to'liq berilgan yoki rezerv qurilmagan).")
    sabab = await rezerv.production_block_reason(db, order)
    if sabab:
        raise BerishError(f"{order.number}: material berilmaydi — {sabab}")
    return rez


async def _line(db: AsyncSession, rez: Rezerv, item: CatalogItem) -> RezervLine:
    lines = list(
        (
            await db.execute(
                select(RezervLine)
                .where(
                    RezervLine.rezerv_id == rez.id,
                    RezervLine.item_id == item.id,
                    RezervLine.is_deleted == False,  # noqa: E712
                )
                .order_by(RezervLine.id)
                .with_for_update()
            )
        ).scalars()
    )
    if not lines:
        raise BerishError(f"«{item.name}» bu buyurtmaning kroyida yo'q.")
    for ln in lines:
        if ln.berilgan_qty < ln.kerak_qty:
            return ln
    raise BerishError(f"«{item.name}» bu buyurtmaga to'liq berilgan.")


async def _erkin(db: AsyncSession, item: CatalogItem) -> Decimal:
    band = (await rezerv.reserved_qty(db, [item.id])).get(item.id, Decimal(0))
    return item.quantity - band


async def _sarf(
    db: AsyncSession,
    order: Order,
    item: CatalogItem,
    line: RezervLine,
    qty: Decimal,
    user_id: int | None,
    unit: MaterialBirlik | None,
) -> None:
    """`qty` ni buyurtmaga sarflaydi. Rezerv qoplamagan qism erkin qoldiqdan bo'lishi shart."""
    qoplangan_qolgan = max(line.qoplangan_qty - line.berilgan_qty, Decimal(0))
    tashqari = qty - min(qty, qoplangan_qolgan)
    if tashqari > 0:
        erkin = await _erkin(db, item)
        if tashqari > erkin:
            raise BerishError(
                f"«{item.name}»: {fmt(tashqari)} {item.unit or ''} rezervdan tashqari kerak, erkin qoldiq "
                f"{fmt(max(erkin, Decimal(0)))} — qolgani boshqa buyurtmalarga band."
            )
    amount = await consume(db, item, qty)
    item.quantity -= qty
    line.berilgan_qty += qty
    line.qoplangan_qty = max(line.qoplangan_qty, min(line.berilgan_qty, line.kerak_qty))
    note = f"Sarf · {order.number}" + (f" · {unit.barkod}" if unit is not None else "")
    db.add(
        StockMovement(
            item_id=item.id,
            kind="sarf",
            qty=-qty,
            balance=item.quantity,
            amount=amount,
            note=note[:200],
            user_id=user_id,
            order_id=order.id,
            birlik_id=unit.id if unit is not None else None,
        )
    )


async def _yopish(db: AsyncSession, rez: Rezerv) -> None:
    """Hamma qator (moslanmaganlar ham) to'liq berilgan bo'lsa — rezerv `sarflandi`."""
    qolgan = await db.scalar(
        select(RezervLine.id).where(
            RezervLine.rezerv_id == rez.id,
            RezervLine.is_deleted == False,  # noqa: E712
            or_(RezervLine.item_id.is_(None), RezervLine.berilgan_qty < RezervLine.kerak_qty),
        )
    )
    if qolgan is None:
        rez.holat = rezerv.SARFLANDI
    await db.flush()


async def skan_birlik(db: AsyncSession, order: Order, barkod: str, user_id: int | None) -> Natija:
    unit = await birlik.find(db, barkod, lock=True)
    if unit is None or unit.is_deleted:
        raise BerishError(f"{barkod}: bunday barkod yo'q.")
    if unit.joy == TUGADI or unit.qoldiq <= 0:
        raise BerishError(f"{unit.barkod}: bu birlik allaqachon ishlatilgan.")
    item = await db.get(CatalogItem, unit.item_id, with_for_update=True)
    assert item is not None
    rez = await _live(db, order)
    line = await _line(db, rez, item)
    kerak = line.kerak_qty - line.berilgan_qty
    natija = Natija(xabar="")
    if not birlik.is_roll(item):
        await _sarf(db, order, item, line, unit.qoldiq, user_id, unit)
        natija.sarf = unit.qoldiq
        unit.qoldiq = Decimal(0)
        unit.joy = TUGADI
        unit.order_id = order.id
        natija.xabar = f"{unit.barkod} «{item.name}» berildi. Qoldi: {fmt(max(kerak - natija.sarf, Decimal(0)))}"
    else:
        # Rulondan faqat shu buyurtmaning bandi + erkin qoldiq olinadi; qolgani boshqa buyurtmalarniki
        mumkin = max(line.qoplangan_qty - line.berilgan_qty, Decimal(0)) + max(await _erkin(db, item), Decimal(0))
        ol = min(kerak, unit.qoldiq, mumkin)
        if ol <= 0:
            raise BerishError(
                f"«{item.name}»: bu buyurtmaga band qoldiq qolmagan, erkin qoldiq ham yo'q — "
                "qolgani boshqa buyurtmalarga band. Ta'minot kerak."
            )
        if ol < min(kerak, unit.qoldiq):
            natija.ogohlantirish.append(
                f"Faqat {fmt(ol)} {item.unit or ''} berildi: yana {fmt(kerak - ol)} kerak, lekin u boshqa "
                "buyurtmalarga band — ta'minot kerak."
            )
        if unit.joy == OMBOR:
            # Ombordagi rulon — avval sexdagi qoldiqni ishlatish kerak (foydalanuvchi qarori, 2026-10-29)
            sexda = await db.scalar(
                select(MaterialBirlik.barkod).where(
                    MaterialBirlik.item_id == item.id,
                    MaterialBirlik.joy == SEX,
                    MaterialBirlik.qoldiq > 0,
                    MaterialBirlik.is_deleted == False,  # noqa: E712
                )
            )
            if sexda is not None:
                natija.ogohlantirish.append(f"Sexda shu kromkadan ochiq rulon bor ({sexda}) — avval o'shani ishlating.")
            unit.joy = SEX
            unit.sexga_at = datetime.now(UTC)
            db.add(
                StockMovement(
                    item_id=item.id,
                    kind="sexga",
                    qty=Decimal(0),
                    balance=item.quantity,
                    note=f"Rulon sexga · {unit.barkod} · {fmt(unit.qoldiq)} {item.unit or ''} · {order.number}"[:200],
                    user_id=user_id,
                    order_id=order.id,
                    birlik_id=unit.id,
                )
            )
        await _sarf(db, order, item, line, ol, user_id, unit)
        unit.qoldiq -= ol
        unit.order_id = order.id
        if unit.qoldiq <= 0:
            unit.joy = TUGADI
        natija.sarf = ol
        natija.rulon_qoldi = unit.qoldiq
        natija.xabar = f"{unit.barkod}: {fmt(ol)} {item.unit or ''} «{item.name}» buyurtmaga yozildi, " + (
            f"rulonda {fmt(unit.qoldiq)} qoldi (sexda)." if unit.qoldiq > 0 else "rulon tugadi."
        )
        if kerak > ol and unit.qoldiq == 0:
            natija.xabar += f" Yana {fmt(kerak - ol)} kerak — keyingi rulonni skanerlang."
    await _yopish(db, rez)
    return natija


async def find_item(db: AsyncSession, kod: str) -> CatalogItem | None:
    """Birliksiz pozitsiya: katalog kodi (`F-PT-012-01`) yoki ishlab chiqaruvchi shtrix-kodi."""
    k = kod.strip()
    return (
        await db.execute(
            select(CatalogItem)
            .where(
                or_(CatalogItem.code == k.upper(), CatalogItem.ishlab_barkod == k),
                CatalogItem.is_deleted == False,  # noqa: E712
            )
            .limit(1)
        )
    ).scalar_one_or_none()


async def ber_dona(db: AsyncSession, order: Order, item_id: int, qty: Decimal, user_id: int | None) -> Natija:
    item = await db.get(CatalogItem, item_id, with_for_update=True)
    if item is None or item.is_deleted:
        raise BerishError("Pozitsiya topilmadi.")
    if birlik.tracked(item):
        raise BerishError(f"«{item.name}» barkodli birlik bilan beriladi — list/rulon yorlig'ini skanerlang.")
    if qty <= 0:
        raise BerishError("Soni kiritilmagan.")
    rez = await _live(db, order)
    line = await _line(db, rez, item)
    kerak = line.kerak_qty - line.berilgan_qty
    if qty > kerak:
        raise BerishError(
            f"«{item.name}»: buyurtmaga yana {fmt(kerak)} {item.unit or ''} kerak, {fmt(qty)} berilmoqda."
        )
    if qty > item.quantity:
        raise BerishError(f"«{item.name}»: omborda {fmt(item.quantity)} {item.unit or ''} bor.")
    await _sarf(db, order, item, line, qty, user_id, None)
    await _yopish(db, rez)
    return Natija(xabar=f"«{item.name}» — {fmt(qty)} {item.unit or ''} berildi.", sarf=qty)


async def rulon_tugadi(db: AsyncSession, barkod: str, user_id: int | None) -> Decimal:
    """Sexdagi rulon amalda tugadi: hisobdagi qoldig'i (stanok chiqindisi, bosh-oxiri) hisobdan chiqadi.
    Qaytaradi — hisobdan chiqarilgan miqdor."""
    unit = await birlik.find(db, barkod, lock=True)
    if unit is None or unit.is_deleted:
        raise BerishError(f"{barkod}: bunday barkod yo'q.")
    if unit.joy != SEX:
        raise BerishError(f"{unit.barkod}: rulon sexda emas.")
    item = await db.get(CatalogItem, unit.item_id, with_for_update=True)
    assert item is not None
    q = min(unit.qoldiq, item.quantity)
    amount = await consume(db, item, q) if q > 0 else Decimal(0)
    item.quantity -= q
    db.add(
        StockMovement(
            item_id=item.id,
            kind="sex_farq",
            qty=-q,
            balance=item.quantity,
            amount=amount,
            note=f"Rulon tugadi · {unit.barkod} · hisobda {fmt(unit.qoldiq)} qolgan edi"[:200],
            user_id=user_id,
            birlik_id=unit.id,
        )
    )
    unit.qoldiq = Decimal(0)
    unit.joy = TUGADI
    await db.flush()
    return q


async def omborga_qaytar(db: AsyncSession, barkod: str) -> MaterialBirlik:
    """Sexdagi rulonni omborga qaytarish (masalan, uzoq vaqt kerak bo'lmasa)."""
    unit = await birlik.find(db, barkod, lock=True)
    if unit is None or unit.is_deleted:
        raise BerishError(f"{barkod}: bunday barkod yo'q.")
    if unit.joy != SEX:
        raise BerishError(f"{unit.barkod}: rulon sexda emas.")
    unit.joy = OMBOR
    unit.sexga_at = None
    await db.flush()
    return unit
