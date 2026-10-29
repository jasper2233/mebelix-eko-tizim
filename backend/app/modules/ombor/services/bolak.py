"""Qoldiq bo'laklari: qabul, ishlatish, chiqitga (EKO TZ §4.4). Sessiyada ishlaydi, `commit` qilmaydi."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, WasteItem
from app.modules.ombor.models import MaterialMap, OmborBolak, Rezerv, RezervLine
from app.modules.ombor.models.bolak import CHIQIT, ISHLATILDI, OMBOR
from app.modules.ombor.services.rezerv import usage_key


class BolakError(Exception):
    """Foydalanuvchiga ko'rsatiladigan rad sababi (o'zbekcha)."""


def is_bolak(kod: str) -> bool:
    return kod.strip().upper().startswith("ATX-")


async def _item_for(db: AsyncSession, w: WasteItem) -> int | None:
    """Bo'lak materiali → katalog: avval moslash jadvali (nom kaliti), keyin manba buyurtma rezervidagi
    shu nomli list qatori (fayl kodi bilan moslangan bo'lsa)."""
    mm = await db.scalar(
        select(MaterialMap.item_id).where(
            MaterialMap.kind == "sheet",
            MaterialMap.tashqi_kalit == usage_key(None, w.material_name),
            MaterialMap.is_deleted == False,  # noqa: E712
        )
    )
    if mm is not None:
        return int(mm)
    iid = await db.scalar(
        select(RezervLine.item_id)
        .join(Rezerv, Rezerv.id == RezervLine.rezerv_id)
        .where(
            Rezerv.order_id == w.order_id,
            RezervLine.kind == "sheet",
            RezervLine.tashqi_nom == w.material_name,
            RezervLine.item_id.is_not(None),
        )
        .order_by(RezervLine.id.desc())
        .limit(1)
    )
    return int(iid) if iid is not None else None


async def find(db: AsyncSession, kod: str, lock: bool = False) -> OmborBolak | None:
    q = select(OmborBolak).where(OmborBolak.barkod == kod.strip(), OmborBolak.is_deleted == False)  # noqa: E712
    return (await db.execute(q.with_for_update() if lock else q)).scalar_one_or_none()


async def qabul(db: AsyncSession, kod: str, user_id: int | None) -> OmborBolak:
    """`ATX-…` yorlig'i skanerlandi — bo'lak omborga olinadi (ikkinchi skan — o'sha bo'lak)."""
    bor = await find(db, kod)
    if bor is not None:
        if bor.joy != OMBOR:
            raise BolakError(f"{bor.barkod}: bu bo'lak allaqachon {bor.joy}.")
        return bor
    w = (
        await db.execute(
            select(WasteItem).where(WasteItem.qr_text == kod.strip(), WasteItem.is_deleted == False)  # noqa: E712
        )
    ).scalar_one_or_none()
    if w is None:
        raise BolakError(f"{kod}: bunday qoldiq yorlig'i yo'q.")
    b = OmborBolak(
        waste_id=w.id,
        barkod=w.qr_text,
        item_id=await _item_for(db, w),
        material_nom=w.material_name,
        uzunlik=Decimal(str(w.length)),
        eni=Decimal(str(w.width)),
        manba_order_id=w.order_id,
        qabul_by_id=user_id,
    )
    db.add(b)
    await db.flush()
    return b


async def ishlat(db: AsyncSession, kod: str, order: Order, user_id: int | None) -> OmborBolak:
    """Bo'lak buyurtmaga berildi (skaner bilan). Omborga qabul qilinmagan bo'lsa — shu yerning o'zida."""
    b = await find(db, kod, lock=True) or await qabul(db, kod, user_id)
    if b.joy != OMBOR or b.qty < 1:
        raise BolakError(f"{b.barkod}: bu bo'lak omborda yo'q ({b.joy}).")
    if b.manba_order_id == order.id:
        raise BolakError(f"{b.barkod}: bu bo'lak shu buyurtmaning o'z kroyidan.")
    if b.band_loyiha:
        raise BolakError(f"{b.barkod}: MX Kroy'da {b.band_raqam or b.band_loyiha} loyihasiga band.")
    b.qty -= 1
    b.order_id = order.id
    if b.qty == 0 and b.qty_pending == 0:
        b.joy = ISHLATILDI
        b.yopilgan_at = datetime.now(UTC)
    await db.flush()
    return b


async def chiqit(db: AsyncSession, bolak_id: int) -> OmborBolak:
    b = await db.get(OmborBolak, bolak_id, with_for_update=True)
    if b is None or b.is_deleted:
        raise BolakError("Bo'lak topilmadi.")
    if b.joy != OMBOR:
        raise BolakError(f"{b.barkod}: bu bo'lak allaqachon {b.joy}.")
    if b.band_loyiha:
        raise BolakError(f"{b.barkod}: MX Kroy'da {b.band_raqam or b.band_loyiha} loyihasiga band.")
    b.qty = 0
    b.joy = CHIQIT
    b.yopilgan_at = datetime.now(UTC)
    await db.flush()
    return b
