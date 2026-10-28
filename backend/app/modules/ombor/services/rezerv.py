"""Rezerv qoidalari — EKO TIZIM TZ §4.3 (Q12–Q14, Q22–Q24).

1. Kroy tayyor (`.project` yuklandi) → `reserve_for_order`: har material katalogga moslanadi
   (`material_map`), mavjud qoldiqdan qoplanadi; yetmagani — ta'minot ehtiyoji. Muddat: N kun.
2. To'lov `ENG_KAM_AVANS_FOIZ` ga muddat ichida yetsa → `yechildi` (buyurtmaniki).
3. Muddat o'tsa (cron) → `muddati_otdi`, qoplangan miqdor sotuvga qaytadi. Keyin to'lasa — qayta rezerv.
4. Kirim kelganda (`recover_shortages`) yetmaganlar navbat bilan qoplanadi: avval yechilganlar.
5. Ishlab chiqarishga darvoza (`production_block_reason`): yechilgan, direktor ruxsati yoki doimiy
   mijozning kredit limiti doirasida.

Kassa bo'lguncha to'langan summa — `order.advance_payment`, buyurtma summasi — `order.amount` (Q24):
ularni faqat `paid_and_required` o'qiydi.

Funksiyalar chaqiruvchining sessiyasida ishlaydi va `commit` qilmaydi.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client, Order
from app.models.enums import OrderStatus
from app.modules.ombor.models import CatalogItem, MaterialMap, Rezerv, RezervLine
from app.services.settings_service import ENG_KAM_AVANS_FOIZ, REZERV_DARVOZA, REZERV_MUDDAT_KUN, get_setting

FAOL = "faol"
YECHILDI = "yechildi"
SARFLANDI = "sarflandi"
MUDDATI_OTDI = "muddati_otdi"
BEKOR = "bekor"
#: Qoldiqni band qiladigan holatlar — mavjud qoldiq shulardan hisoblanadi
BAND = (FAOL, YECHILDI)
#: Buyurtmada bittadan ortiq bo'lmaydigan «tirik» holatlar (`ix_rezerv_order_tirik`)
TIRIK = (FAOL, YECHILDI, MUDDATI_OTDI)

_Q = Decimal("0.001")


def usage_key(code: str | None, name: str) -> str:
    """Moslash kaliti: fayldagi kod; kodsiz eski fayllarda — kichik harfli, bo'shliqlari siqilgan nom."""
    if code and code.strip():
        return code.strip()
    return re.sub(r"\s+", " ", name).strip().lower()


def _som(x: Decimal) -> str:
    """1000000 → «1 000 000» (o'zbekcha minglik ajratuvchi — bo'shliq)."""
    return f"{x:,.0f}".replace(",", " ")


def _now() -> datetime:
    return datetime.now(UTC)


async def _tirik(db: AsyncSession, order_id: int) -> Rezerv | None:
    return (
        await db.execute(
            select(Rezerv).where(Rezerv.order_id == order_id, Rezerv.holat.in_(TIRIK), Rezerv.is_deleted == False)  # noqa: E712
        )
    ).scalar_one_or_none()


async def reserved_qty(db: AsyncSession, item_ids: Iterable[int]) -> dict[int, Decimal]:
    """Pozitsiyalar bo'yicha buyurtmalarga band (qoplangan) miqdor."""
    ids = list(set(item_ids))
    if not ids:
        return {}
    rows = await db.execute(
        select(RezervLine.item_id, func.coalesce(func.sum(RezervLine.qoplangan_qty), 0))
        .join(Rezerv, Rezerv.id == RezervLine.rezerv_id)
        .where(
            RezervLine.item_id.in_(ids),
            RezervLine.is_deleted == False,  # noqa: E712
            Rezerv.holat.in_(BAND),
            Rezerv.is_deleted == False,  # noqa: E712
        )
        .group_by(RezervLine.item_id)
    )
    return {iid: Decimal(q) for iid, q in rows.all()}


async def _lock_items(db: AsyncSession, ids: Iterable[int]) -> dict[int, CatalogItem]:
    # Qulf tartibi id bo'yicha — ikki parallel rezerv bir-birini kutib qolmasin (deadlock)
    ids = sorted(set(ids))
    if not ids:
        return {}
    q = select(CatalogItem).where(CatalogItem.id.in_(ids)).order_by(CatalogItem.id).with_for_update()
    return {i.id: i for i in (await db.execute(q)).scalars()}


async def _free(db: AsyncSession, items: dict[int, CatalogItem]) -> dict[int, Decimal]:
    band = await reserved_qty(db, items)
    return {iid: max(it.quantity - band.get(iid, Decimal(0)), Decimal(0)) for iid, it in items.items()}


async def reserve_for_order(db: AsyncSession, order: Order) -> Rezerv | None:
    """Buyurtma rezervini (qayta) quradi. Eski tirik rezerv bekor qilinadi, to'lov saqlanadi (TZ §4.3 8-band)."""
    old = await _tirik(db, order.id)
    if old is not None:
        old.holat = BEKOR
        await db.flush()
    if not order.material_usage:
        return None

    # Bir xil material bir necha marta kelishi mumkin — kalit bo'yicha jamlanadi
    agg: dict[tuple[str, str], dict[str, object]] = {}
    for m in order.material_usage:
        akey = (str(m["kind"]), usage_key(m.get("code"), str(m["name"])))
        row = agg.setdefault(akey, {"nom": str(m["name"]), "birlik": str(m.get("unit") or ""), "qty": Decimal(0)})
        row["qty"] = Decimal(row["qty"]) + Decimal(str(m.get("count") or 0))  # type: ignore[arg-type]

    maps = {
        (mm.kind, mm.tashqi_kalit): mm
        for mm in (
            await db.execute(
                select(MaterialMap).where(
                    MaterialMap.is_deleted == False,  # noqa: E712
                    MaterialMap.tashqi_kalit.in_([k for _, k in agg]),
                )
            )
        ).scalars()
    }
    items = await _lock_items(db, (mm.item_id for mm in maps.values()))
    free = await _free(db, items)

    days = int(await get_setting(db, REZERV_MUDDAT_KUN))
    rez = Rezerv(order_id=order.id, holat=FAOL, muddat=_now() + timedelta(days=days))
    db.add(rez)
    await db.flush()
    for (kind, key), row in sorted(agg.items()):
        mm = maps.get((kind, key))
        line = RezervLine(
            rezerv_id=rez.id,
            kind=kind,
            tashqi_kalit=key,
            tashqi_nom=str(row["nom"])[:200],
            fayl_qty=Decimal(row["qty"]),  # type: ignore[arg-type]
            fayl_birlik=str(row["birlik"])[:10],
        )
        if mm is not None and mm.item_id in items:
            _cover(line, mm, free)
        db.add(line)
    await db.flush()
    await check_payment(db, order)
    return rez


def _cover(line: RezervLine, mm: MaterialMap, free: dict[int, Decimal]) -> None:
    line.item_id = mm.item_id
    line.kerak_qty = (line.fayl_qty * mm.koef).quantize(_Q, ROUND_HALF_UP)
    line.qoplangan_qty = min(line.kerak_qty, free.get(mm.item_id, Decimal(0)))
    free[mm.item_id] = free.get(mm.item_id, Decimal(0)) - line.qoplangan_qty


async def paid_and_required(db: AsyncSession, order: Order) -> tuple[Decimal, Decimal]:
    """(to'langan, chegara) so'mda. Kassa (4-bosqich) kelganda faqat shu funksiya almashadi (Q24)."""
    pct = Decimal(await get_setting(db, ENG_KAM_AVANS_FOIZ))
    paid = order.advance_payment or Decimal(0)
    required = ((order.amount or Decimal(0)) * pct / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return paid, required


async def check_payment(db: AsyncSession, order: Order) -> str | None:
    """To'lov o'zgargandan keyin chaqiriladi. Yangi holat (o'zgargan bo'lsa) qaytadi."""
    rez = await _tirik(db, order.id)
    if rez is None or rez.holat == YECHILDI:
        return None
    paid, required = await paid_and_required(db, order)
    if paid < required or order.amount is None:
        return None
    if rez.holat == FAOL and _now() <= rez.muddat:
        rez.holat = YECHILDI
        rez.yechilgan_at = _now()
        await db.flush()
        return YECHILDI
    if rez.holat == MUDDATI_OTDI:
        # Kech to'ladi — material bo'shab qolgan, qaytadan band qilinadi (TZ §4.3 5-band)
        new = await reserve_for_order(db, order)
        return new.holat if new is not None else None
    return None


async def expire_due(db: AsyncSession) -> int:
    """Muddati o'tgan faol rezervlar → `muddati_otdi` (cron)."""
    res = await db.execute(
        update(Rezerv)
        .where(Rezerv.holat == FAOL, Rezerv.muddat < _now(), Rezerv.is_deleted == False)  # noqa: E712
        .values(holat=MUDDATI_OTDI)
    )
    return int(res.rowcount or 0)  # type: ignore[attr-defined]


async def recover_shortages(db: AsyncSession, item_ids: Iterable[int]) -> None:
    """Kirimdan keyin yetmay turgan rezerv qatorlarini qoplaydi: avval yechilganlar, keyin vaqt bo'yicha."""
    items = await _lock_items(db, item_ids)
    if not items:
        return
    free = await _free(db, items)
    lines = (
        await db.execute(
            select(RezervLine)
            .join(Rezerv, Rezerv.id == RezervLine.rezerv_id)
            .where(
                RezervLine.item_id.in_(list(items)),
                RezervLine.kerak_qty > RezervLine.qoplangan_qty,
                RezervLine.is_deleted == False,  # noqa: E712
                Rezerv.holat.in_(BAND),
                Rezerv.is_deleted == False,  # noqa: E712
            )
            .order_by(case((Rezerv.holat == YECHILDI, 0), else_=1), Rezerv.created_at, RezervLine.id)
        )
    ).scalars()
    for line in lines:
        assert line.item_id is not None
        add = min(line.kerak_qty - line.qoplangan_qty, free.get(line.item_id, Decimal(0)))
        if add > 0:
            line.qoplangan_qty += add
            free[line.item_id] -= add
    await db.flush()


async def apply_mapping(
    db: AsyncSession, kind: str, tashqi_kalit: str, item_id: int, koef: Decimal, user_id: int | None
) -> MaterialMap:
    """Materialni katalogga bog'laydi (yoki qayta bog'laydi) va tirik rezervlardagi moslanmagan qatorlarni qoplaydi."""
    old = (
        await db.execute(
            select(MaterialMap).where(
                MaterialMap.kind == kind,
                MaterialMap.tashqi_kalit == tashqi_kalit,
                MaterialMap.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()
    if old is not None:
        old.is_deleted = True
        old.deleted_at = _now()
        await db.flush()
    mm = MaterialMap(kind=kind, tashqi_kalit=tashqi_kalit, item_id=item_id, koef=koef, created_by_id=user_id)
    db.add(mm)
    lines = (
        await db.execute(
            select(RezervLine)
            .join(Rezerv, Rezerv.id == RezervLine.rezerv_id)
            .where(
                RezervLine.kind == kind,
                RezervLine.tashqi_kalit == tashqi_kalit,
                RezervLine.item_id.is_(None),
                Rezerv.holat.in_(BAND),
                Rezerv.is_deleted == False,  # noqa: E712
            )
        )
    ).scalars()
    for line in lines:
        line.item_id = item_id
        line.kerak_qty = (line.fayl_qty * koef).quantize(_Q, ROUND_HALF_UP)
    await db.flush()
    await recover_shortages(db, [item_id])
    return mm


async def client_debt(db: AsyncSession, client_id: int) -> Decimal:
    """Mijozning ochiq qarzi: bekor qilinmagan buyurtmalar bo'yicha `summa − to'langan` (Q24 manbasi)."""
    unpaid = Order.amount - func.coalesce(Order.advance_payment, 0)
    q = select(func.coalesce(func.sum(unpaid), 0)).where(
        Order.client_id == client_id,
        Order.status != OrderStatus.CANCELLED,
        Order.is_deleted == False,  # noqa: E712
        and_(Order.amount.is_not(None), unpaid > 0),
    )
    return Decimal((await db.execute(q)).scalar_one() or 0)


async def production_block_reason(db: AsyncSession, order: Order) -> str | None:
    """Ishlab chiqarishga o'tishga to'siq bo'lsa — sababi (o'zbekcha), bo'lmasa None (TZ §5 B4)."""
    if await get_setting(db, REZERV_DARVOZA) == "0":
        return None
    rez = await _tirik(db, order.id)
    if rez is not None and (rez.holat == YECHILDI or rez.tasdiq_at is not None):
        return None
    client = await db.get(Client, order.client_id)
    if client is not None and client.doimiy and client.kredit_limit is not None:
        if await client_debt(db, client.id) <= client.kredit_limit:
            return None
    paid, required = (_som(x) for x in await paid_and_required(db, order))
    if rez is None:
        return "Buyurtmada material rezervi yo'q. Rezervni qayta hisoblang yoki direktor ruxsatini oling."
    if rez.holat == MUDDATI_OTDI:
        return f"Rezerv muddati o'tgan: to'langan {paid}, kerak {required} so'm. Direktor ruxsati kerak."
    return f"To'lov chegarasi bajarilmagan: to'langan {paid}, kerak {required} so'm. Direktor ruxsati kerak."


async def approve(db: AsyncSession, order_id: int, user_id: int | None) -> Rezerv | None:
    """Direktor ruxsati (Q22): to'lovsiz yoki limitdan oshgan buyurtma ishlab chiqarishga o'tadi."""
    rez = await _tirik(db, order_id)
    if rez is None:
        return None
    rez.tasdiq_by_id = user_id
    rez.tasdiq_at = _now()
    await db.flush()
    return rez


async def cancel_for_order(db: AsyncSession, order_id: int) -> None:
    rez = await _tirik(db, order_id)
    if rez is not None:
        rez.holat = BEKOR
        await db.flush()


@dataclass
class Shortage:
    item_id: int | None
    nom: str
    birlik: str
    kerak: Decimal
    qoplangan: Decimal
    buyurtmalar: int


async def shortages(db: AsyncSession) -> list[Shortage]:
    """Ta'minot ehtiyoji: band holatdagi rezervlarda yetmayotgan miqdor, pozitsiya bo'yicha.
    Moslanmagan materiallar `item_id=None` bilan, fayldagi nomi va birligida."""
    # Moslangan qatorlar pozitsiya bo'yicha bitta guruh (fayldagi nomlari har xil bo'lsa ham)
    nom = func.coalesce(CatalogItem.name, RezervLine.tashqi_nom)
    birlik = func.coalesce(CatalogItem.unit, RezervLine.fayl_birlik)
    rows = await db.execute(
        select(
            RezervLine.item_id,
            nom,
            birlik,
            func.sum(case((RezervLine.item_id.is_(None), RezervLine.fayl_qty), else_=RezervLine.kerak_qty)),
            func.sum(RezervLine.qoplangan_qty),
            func.count(func.distinct(Rezerv.order_id)),
        )
        .join(Rezerv, Rezerv.id == RezervLine.rezerv_id)
        .outerjoin(CatalogItem, CatalogItem.id == RezervLine.item_id)
        .where(
            Rezerv.holat.in_(BAND),
            Rezerv.is_deleted == False,  # noqa: E712
            RezervLine.is_deleted == False,  # noqa: E712
            (RezervLine.item_id.is_(None)) | (RezervLine.kerak_qty > RezervLine.qoplangan_qty),
        )
        .group_by(RezervLine.item_id, nom, birlik)
        .order_by(nom)
    )
    return [Shortage(iid, n_, b_ or "", Decimal(k), Decimal(q), n) for iid, n_, b_, k, q, n in rows.all()]
