"""Sexdan material so'rovlari (EKO TZ §4.4). Funksiyalar chaqiruvchining sessiyasida, `commit` qilmaydi."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ombor.models import MaterialSorov, Rezerv, RezervLine
from app.modules.ombor.models.sorov import YANGI, YETKAZILDI
from app.modules.ombor.services import rezerv

#: Post → rezerv qatorlari turi (`material_usage[].kind`): arra listni, kromka/oval lentani oladi
POST_KINDS: dict[str, tuple[str, ...]] = {"ARRA": ("sheet",), "KROMKA": ("band",), "OVAL": ("band",)}


async def ochiq(db: AsyncSession, order_id: int, post: str) -> MaterialSorov | None:
    return (
        await db.execute(
            select(MaterialSorov).where(
                MaterialSorov.order_id == order_id,
                MaterialSorov.post == post,
                MaterialSorov.holat == YANGI,
                MaterialSorov.is_deleted == False,  # noqa: E712
            )
        )
    ).scalar_one_or_none()


async def sora(
    db: AsyncSession, order_id: int, post: str, machine_id: int | None, izoh: str, user_id: int | None
) -> MaterialSorov:
    """Ochiq so'rov bo'lsa — o'sha (izohi yangilanadi), bo'lmasa yangisi."""
    s = await ochiq(db, order_id, post)
    if s is None:
        s = MaterialSorov(order_id=order_id, post=post, machine_id=machine_id, izoh=izoh, created_by_id=user_id)
        db.add(s)
    elif izoh:
        s.izoh = izoh
    await db.flush()
    return s


def yop(s: MaterialSorov, user_id: int | None) -> None:
    s.holat = YETKAZILDI
    s.yopilgan_at = datetime.now(UTC)
    s.yopgan_id = user_id


async def auto_yop(db: AsyncSession, order_id: int, user_id: int | None) -> None:
    """Postning hamma materiali berilgan bo'lsa — uning ochiq so'rovi yopiladi (berishdan keyin chaqiriladi)."""
    for post, kinds in POST_KINDS.items():
        s = await ochiq(db, order_id, post)
        if s is None:
            continue
        qolgan = await db.scalar(
            select(RezervLine.id)
            .join(Rezerv, Rezerv.id == RezervLine.rezerv_id)
            .where(
                Rezerv.order_id == order_id,
                Rezerv.holat.in_(rezerv.BAND),
                Rezerv.is_deleted == False,  # noqa: E712
                RezervLine.is_deleted == False,  # noqa: E712
                RezervLine.kind.in_(kinds),
                RezervLine.berilgan_qty < RezervLine.kerak_qty,
            )
            .limit(1)
        )
        if qolgan is None:
            yop(s, user_id)
    await db.flush()
