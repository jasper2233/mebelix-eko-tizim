"""ombor moduli ochiq interfeysi — tashqaridan faqat shu fayl import qilinadi.

Ishlab chiqarish ↔ ombor bog'lanishlari (TZ §5). Hammasi chaqiruvchining sessiyasida, `commit` siz:
buyurtma amali va ombor oqibati bitta tranzaksiyada.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order
from app.modules.ombor.services import rezerv


async def on_project_loaded(db: AsyncSession, order: Order) -> None:
    """B1: kroy (`.project`) yuklandi yoki qayta yuklandi → material rezervi (qayta) quriladi."""
    await rezerv.reserve_for_order(db, order)


async def on_payment_changed(db: AsyncSession, order: Order) -> None:
    """B2: buyurtma to'lovi yoki summasi o'zgardi → chegara bajarilsa rezerv yechiladi."""
    await rezerv.check_payment(db, order)


async def production_block_reason(db: AsyncSession, order: Order) -> str | None:
    """B4: ishlab chiqarishga o'tishga to'siq bo'lsa — foydalanuvchiga ko'rsatiladigan sabab."""
    return await rezerv.production_block_reason(db, order)


async def on_order_cancelled(db: AsyncSession, order_id: int) -> None:
    """B12: buyurtma bekor qilindi → rezerv bekor, material bo'shaydi."""
    await rezerv.cancel_for_order(db, order_id)


async def expire_reservations(db: AsyncSession) -> int:
    """B3 (cron): to'lov muddati o'tgan rezervlar bo'shatiladi. Nechtasi o'zgargani qaytadi."""
    return await rezerv.expire_due(db)


async def adopt_open_order(db: AsyncSession, order: Order) -> bool:
    """Rezerv qoidasiga o'tish kuni (bir martalik): tirik rezervi yo'q buyurtmaga rezerv quriladi va
    tizim nomidan ruxsat beriladi. Rezervi bor yoki fayli yo'q bo'lsa — hech narsa qilmaydi (False)."""
    if not order.material_usage or await rezerv.has_live(db, order.id):
        return False
    await rezerv.reserve_for_order(db, order)
    await rezerv.approve(db, order.id, None)
    return True
