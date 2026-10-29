"""Barkodli birliklar: yaratish (kirim, eski qoldiqni yorliqlash) va qoldiq bilan moslash (EKO TZ §4.4).

Qoida: birliklar qoldig'i yig'indisi (ombor + sex) hech qachon `catalog_item.quantity` dan oshmaydi.
Kamaygan har o'zgarishdan keyin (sotuv, inventarizatsiya, tuzatish) `sync_down` ortiqchani eng eski
ombordagi birliklardan, keyin sexdagilardan oladi. Yorlig'i yo'q qism (`unlabeled`) — birlik
tizimidan oldin kelgan qoldiq: omborchi uni bir marta yorliqlaydi.

Funksiyalar chaqiruvchining sessiyasida ishlaydi va `commit` qilmaydi.
"""

from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ombor.models import CatalogItem, MaterialBirlik
from app.modules.ombor.models.birlik import OMBOR, SEX, TUGADI


def tracked(item: CatalogItem) -> bool:
    """Birlik bilan yuradimi: listlar/panellar (`M`) va metrdagi materiallar (kromka, profil)."""
    return item.catalog == "M" or (item.catalog != "X" and item.unit == "metr")


def is_roll(item: CatalogItem) -> bool:
    """Rulon (uzunligi bilan, qismlab sarflanadi) yoki butun dona (list — bittada sarflanadi)."""
    return item.unit == "metr"


def barkod_of(birlik_id: int) -> str:
    return f"EK{birlik_id:07d}"


async def labeled(db: AsyncSession, item_id: int) -> Decimal:
    q = await db.scalar(
        select(func.coalesce(func.sum(MaterialBirlik.qoldiq), 0)).where(
            MaterialBirlik.item_id == item_id,
            MaterialBirlik.joy.in_((OMBOR, SEX)),
            MaterialBirlik.is_deleted == False,  # noqa: E712
        )
    )
    return Decimal(q or 0)


async def unlabeled(db: AsyncSession, item: CatalogItem) -> Decimal:
    return max(item.quantity - await labeled(db, item.id), Decimal(0))


def split(item: CatalogItem, qty: Decimal, hajm: Decimal | None) -> list[Decimal] | str:
    """Miqdorni birliklarga bo'ladi; bo'lmasa — xato matni. Rulonda oxirgisi qisqa bo'lishi mumkin."""
    if not is_roll(item):
        if qty != qty.to_integral_value():
            return f"«{item.name}»: {qty} — butun son bo'lishi kerak (har {item.unit or 'dona'} alohida barkod oladi)"
        return [Decimal(1)] * int(qty)
    h = hajm or item.birlik_hajm
    if h is None or h <= 0:
        return f"«{item.name}»: bitta rulon necha metr — kiritilmagan"
    n, rem = divmod(qty, h)
    out = [h] * int(n)
    if rem > 0:
        out.append(rem)
    if len(out) > 1000:
        return f"«{item.name}»: {len(out)} ta rulon — rulon uzunligini tekshiring"
    return out


async def create(
    db: AsyncSession, item: CatalogItem, sizes: list[Decimal], doc_id: int | None = None
) -> list[MaterialBirlik]:
    if not sizes:
        return []
    units = [MaterialBirlik(item_id=item.id, hajm=s, qoldiq=s, doc_id=doc_id) for s in sizes]
    db.add_all(units)
    await db.flush()
    for u in units:
        u.barkod = barkod_of(u.id)
    await db.flush()
    return units


async def sync_down(db: AsyncSession, item: CatalogItem) -> None:
    """Qoldiq kamaygach birliklar undan oshib qolmasin: ortiqchani eski ombordagilardan, keyin sexdan oladi."""
    ortiq = await labeled(db, item.id) - item.quantity
    if ortiq <= 0:
        return
    units = (
        await db.execute(
            select(MaterialBirlik)
            .where(
                MaterialBirlik.item_id == item.id,
                MaterialBirlik.joy.in_((OMBOR, SEX)),
                MaterialBirlik.qoldiq > 0,
                MaterialBirlik.is_deleted == False,  # noqa: E712
            )
            .order_by(case((MaterialBirlik.joy == OMBOR, 0), else_=1), MaterialBirlik.id)
            .with_for_update()
        )
    ).scalars()
    for u in units:
        if ortiq <= 0:
            break
        t = min(u.qoldiq, ortiq)
        u.qoldiq -= t
        ortiq -= t
        if u.qoldiq <= 0:
            u.joy = TUGADI
    await db.flush()


async def find(db: AsyncSession, barkod: str, lock: bool = False) -> MaterialBirlik | None:
    q = select(MaterialBirlik).where(MaterialBirlik.barkod == barkod.strip().upper())
    return (await db.execute(q.with_for_update() if lock else q)).scalar_one_or_none()
