"""Mahsulotlar ombori: narx qoidalari va ABC (docs/14 §8, 2026-10-16 — «Qudrat Ombor» dizayni).

Narx katalog varag'idan emas, OMBORDAN boshqariladi:

* Furnitura (`F`): sotuv = xarid × (1 + ustama%), 100 so'mgacha yaxlitlanadi. Ustama — pozitsiyaniki,
  bo'lmasa guruhniki, u ham bo'lmasa umumiy. Ustama berilmagan pozitsiyada sotuv qo'lda qoladi.
* LDSP / LMDF dekorlari (`M-LD`, `M-LM`): sinf (Standart / Medium / Premium) belgilangan bo'lsa
  sotuv = shu sinfning BITTA list narxi — sinf narxi o'zgarsa hamma dekor birdan yangilanadi.
* Xarid dollarda (`purchase_usd`) bo'lsa so'mdagi xarid = $ × kurs; kurs o'zgarsa qayta hisoblanadi.

Qoidalar dizayndagi `markupPrice` / `setTierPrice` / `setUsd` bilan bir xil."""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CatalogItem
from app.schemas.catalog import WarehousePricing
from app.services.settings_service import get_setting

WAREHOUSE_PRICING = "warehouse_pricing"
#: Sex xo'jaligi guruhlari (dizayndagi `SEX_G`) — katalog varag'ida yo'q, birinchi pozitsiya shu nom bilan
#: ochiladi. Frontend'dagi nusxasi: `lib/warehouse.ts: SEX_GROUPS`.
SEX_GROUPS = {
    "S-ZP": "Uskuna zapchastlari",
    "S-AS": "Sex asbob va sarfi",
    "S-KG": "Qog'oz va kanselyariya",
    "S-XJ": "Xo'jalik va himoya",
    "S-UP": "Upakovka materiali",
}
#: Sinf narxi qo'llanadigan guruhlar — LDSP va LMDF dekorlari
#: Sotuv narxi SINF bo'yicha qo'yiladigan guruhlar: LDSP va LMDF dekorlari (1 list uchun) va
#: KROMKA (2026-10-18, 1 METR uchun — kromka rulon bo'lib keladi va metrlab sotiladi).
#: Bu guruhlarda ustama ISHLAMAYDI: narxni egasi sinf bo'yicha qo'yadi.
TIER_GROUPS = ("M-LD", "M-LM", "F-KM")


async def get_pricing(db: AsyncSession) -> WarehousePricing:
    raw = await get_setting(db, WAREHOUSE_PRICING)
    return WarehousePricing.model_validate_json(raw) if raw else WarehousePricing()


def group_key(item: CatalogItem) -> str:
    return f"{item.catalog}-{item.group_code}"


def _butun(v: Decimal) -> Decimal:
    return v.quantize(Decimal(1), rounding=ROUND_HALF_UP)


def markup_of(item: CatalogItem, cfg: WarehousePricing) -> Decimal | None:
    """Amaldagi ustama: pozitsiyaniki → guruhniki → umumiy."""
    if item.markup_pct is not None:
        return item.markup_pct
    return cfg.markup_groups.get(group_key(item), cfg.markup_all)


def reprice(item: CatalogItem, cfg: WarehousePricing) -> None:
    """Pozitsiyaning so'mdagi xaridi va sotuvini qoidalar bo'yicha yangilaydi (joyida)."""
    if item.purchase_usd is not None:
        item.purchase_price = _butun(item.purchase_usd * cfg.usd_rate)
    # Sinf narxi ustamadan USTUN: kromka ham furnitura katalogida, lekin uning sotuvi
    # tannarxdan emas, egasi qo'ygan metr narxidan keladi (docs/14 §8.2)
    if group_key(item) in TIER_GROUPS and item.tier:
        narx = cfg.tier_prices.get(group_key(item), {}).get(item.tier)  # type: ignore[call-overload]
        if narx:
            item.sale_price = narx
    elif item.catalog == "F":
        mk = markup_of(item, cfg)
        if mk is not None and item.purchase_price:
            # 100 so'mgacha: dizayndagi `Math.round(b * (1 + v / 100) / 100) * 100`
            item.sale_price = _butun(item.purchase_price * (1 + mk / 100) / 100) * 100


def abc_classes(items: list[CatalogItem]) -> dict[int, str]:
    """ABC: qoldiq qiymati (miqdor × xarid, xarid yo'q bo'lsa sotuv) bo'yicha — jami qiymatning
    80% ini beradigan pozitsiyalar A, keyingi 15% B, qolgani C. Xizmatda None (chaqiruvchi)."""
    qiymat = sorted(
        (
            (i.id, v)
            for i in items
            if i.catalog != "X" and (v := i.quantity * (i.purchase_price or i.sale_price or 0)) > 0
        ),
        key=lambda z: -z[1],
    )
    jami = sum((v for _, v in qiymat), Decimal(0)) or Decimal(1)
    out: dict[int, str] = {}
    acc = Decimal(0)
    for n, (iid, v) in enumerate(qiymat):
        acc += v
        ulush = acc / jami
        # Eng qimmati HAR DOIM A. Aks holda jami qiymatning 80% idan ko'pini bitta pozitsiya
        # ushlaganda (omborda oddiy hol) u B yoki C bo'lib qolardi va ro'yxatda A sinf UMUMAN
        # bo'lmasdi — ombor hisobotida (docs/14 §11) «A sinf 0 ta · 0%» bo'lib ko'rinardi.
        out[iid] = "A" if n == 0 or ulush <= Decimal("0.8") else "B" if ulush <= Decimal("0.95") else "C"
    return out
