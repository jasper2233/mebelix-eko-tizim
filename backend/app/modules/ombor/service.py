"""ombor moduli ochiq interfeysi — tashqaridan faqat shu fayl import qilinadi.

Ishlab chiqarish ↔ ombor bog'lanishlari (TZ §5). Hammasi chaqiruvchining sessiyasida, `commit` siz:
buyurtma amali va ombor oqibati bitta tranzaksiyada.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order
from app.modules.ombor.services import kroy, moliya_oqish, mx_katalog, rezerv, solishtirish
from app.modules.ombor.services.kroy_auth import kroy_token

__all__ = ["kroy_token"]


async def on_project_loaded(db: AsyncSession, order: Order) -> None:
    """B1: kroy (`.project`) yuklandi yoki qayta yuklandi → material rezervi (qayta) quriladi."""
    await rezerv.reserve_for_order(db, order)


async def on_payment_changed(db: AsyncSession, order: Order) -> None:
    """B2: buyurtma to'lovi yoki summasi o'zgardi → chegara bajarilsa rezerv yechiladi."""
    await rezerv.check_payment(db, order)


async def rezerv_holati(db: AsyncSession, order: Order) -> tuple[Decimal, Decimal, bool] | None:
    """Kassa uchun (EKO 4): (to'langan, chegara, material biriktirildimi) yoki rezerv yo'q — None."""
    return await rezerv.holati(db, order)


async def production_block_reason(db: AsyncSession, order: Order) -> str | None:
    """B4: ishlab chiqarishga o'tishga to'siq bo'lsa — foydalanuvchiga ko'rsatiladigan sabab."""
    return await rezerv.production_block_reason(db, order)


async def on_order_cancelled(db: AsyncSession, order_id: int) -> None:
    """B12: buyurtma bekor qilindi → rezerv bekor, material bo'shaydi."""
    await rezerv.cancel_for_order(db, order_id)


async def kroy_yorliqla(
    db: AsyncSession,
    mx_loyiha: str,
    kartalar: dict[int, tuple[str, int]],
    qoldiqlar: list[tuple[int, str, int, float, float]],
) -> int:
    """Kroy paketidagi `ATX` qoldiqlarini MX bo'laklariga bog'laydi (EKO 3e)."""
    return await kroy.yorliqla(db, mx_loyiha, kartalar, qoldiqlar)


async def kroy_map_done(db: AsyncSession, mx_loyiha: str, mx_op: str, karta: int, done: int) -> int:
    """MX `map.done`: karta listi arradan chiqdi — shu kartaning qoldiq bo'laklari ulushi omborga."""
    return await kroy.map_done(db, mx_loyiha, mx_op, karta, done)


async def katalog_mx(db: AsyncSession) -> list[dict[str, Any]]:
    """Katalog MX Kroy shaklida (K5): papkalar va list/kromka pozitsiyalari."""
    return await mx_katalog.items(db)


async def reconcile(db: AsyncSession) -> list[solishtirish.Farq]:
    """Kechki solishtirish natijasi (bo'sh — hammasi mos)."""
    return await solishtirish.solishtir(db)


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


# ── Moliya (EKO TZ §8) uchun o'qish ──
Hujjat = moliya_oqish.Hujjat


async def sotuv_hujjatlari(db: AsyncSession, dan: date | None = None, gacha: date | None = None) -> list[Hujjat]:
    """Do'kon sotuvi (chiqim hujjatlari) summasi va FIFO tannarxi; storno — manfiy qator."""
    return await moliya_oqish.hujjatlar(db, "chiqim", dan, gacha)


async def kirim_hujjatlari(db: AsyncSession, dan: date | None = None, gacha: date | None = None) -> list[Hujjat]:
    """Ta'minotchidan kirimlar (kreditorlik manbasi); storno — manfiy qator."""
    return await moliya_oqish.hujjatlar(db, "kirim", dan, gacha)


async def buyurtma_tannarxi(db: AsyncSession, order_ids: list[int]) -> dict[int, Decimal]:
    """Buyurtmaga sarflangan material FIFO tannarxi (qaytgani ayirilgan)."""
    return await moliya_oqish.buyurtma_tannarxi(db, order_ids)


async def kromka_normasi(db: AsyncSession, order_ids: list[int]) -> dict[int, tuple[Decimal, Decimal]]:
    """Buyurtma kromkasi (metr, so'm) — sexga rulonda berilgani uchun FIFO sarfda yo'q qismi."""
    return await moliya_oqish.kromka_normasi(db, order_ids)


async def ombor_qiymati(db: AsyncSession) -> Decimal:
    return await moliya_oqish.ombor_qiymati(db)


async def qoralamalar(db: AsyncSession, dan: date, gacha: date) -> list[str]:
    return await moliya_oqish.qoralamalar(db, dan, gacha)


# ── Soliq (EKO TZ §9) uchun ──
Pozitsiya = moliya_oqish.Pozitsiya
HujjatQatori = moliya_oqish.Qator


async def soliq_pozitsiyalar(db: AsyncSession, ids: list[int]) -> dict[int, Pozitsiya]:
    """Katalog pozitsiyalarining MXIK, o'lchov birligi kodi va QQS turi."""
    return await moliya_oqish.pozitsiyalar(db, ids)


async def hujjat_qatorlari(db: AsyncSession, doc_id: int) -> tuple[Any, list[HujjatQatori]]:
    """Ombor hujjati (StockDoc yoki None) va qatorlari (chegirmadan keyingi summa bilan)."""
    return await moliya_oqish.hujjat_qatorlari(db, doc_id)


async def sotuv_qatorlari(db: AsyncSession, dan: date, gacha: date) -> list[tuple[Decimal, str]]:
    """Do'kon sotuvi qatorlari (summa, QQS turi) — storno manfiy."""
    return await moliya_oqish.sotuv_qatorlari(db, dan, gacha)


async def soliq_saqla(db: AsyncSession, item_id: int, mxik: str | None, birlik_kod: str | None, qqs_turi: str) -> bool:
    """Pozitsiyaning soliq maydonlari; topilmasa False."""
    return await moliya_oqish.soliq_saqla(db, item_id, mxik, birlik_kod, qqs_turi) is not None


# ── Buxgalteriya (EKO 7) uchun ──
Harakat = moliya_oqish.Harakat


async def bux_harakatlar(db: AsyncSession) -> list[Harakat]:
    """Qiymatli ombor harakatlari: ombor qiymatiga ta'siri ishorali (kirim +, chiqim/sarf −)."""
    return await moliya_oqish.harakatlar(db)


async def boshlangich_qiymat(db: AsyncSession) -> Decimal:
    """Tizimga o'tishdagi ombor qiymati (buxgalteriyada boshlang'ich qoldiq)."""
    return await moliya_oqish.boshlangich_qiymat(db)


# ── Ishga tayyorlik ──
async def mxik_qamrovi(db: AsyncSession) -> tuple[int, int]:
    """(qoldig'i bor pozitsiyalar, shundan MXIK i borlari)."""
    return await moliya_oqish.mxik_qamrovi(db)


async def inventarizatsiya_bormi(db: AsyncSession) -> bool:
    """Tasdiqlangan inventarizatsiya hujjati bormi."""
    return await moliya_oqish.inventarizatsiya_bormi(db)
