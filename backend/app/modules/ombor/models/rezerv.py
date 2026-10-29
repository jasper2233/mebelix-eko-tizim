"""Rezerv, material moslash — EKO TIZIM TZ §4.3, Q12–Q14, Q22–Q24.

Kroy tayyor bo'lganda (`.project` yuklandi) buyurtmaning material ehtiyoji (`order.material_usage`)
katalog pozitsiyalariga band qilinadi. To'lov muddat ichida chegaraga yetsa rezerv «yechiladi»
(buyurtmaniki), yetmasa muddati o'tadi va material yana sotuvga ochiladi.

Mavjud qoldiq = `catalog_item.quantity` − faol va yechilgan rezervlar qoplagan miqdor.
Rezerv qoldiqni o'zi kamaytirmaydi — kamaytirish (sarf) faqat ombor hujjati bilan.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class MaterialMap(BaseModel):
    """Loyiha fayli materiali → katalog pozitsiyasi. Bir marta bog'lanadi, keyin o'zi topiladi (Q23).

    `koef` — fayl birligidan katalog birligiga: masalan kromka faylda metrda, katalogda rulonda
    (50 m) bo'lsa koef = 0.02. Bir xil birlikda 1.
    """

    __tablename__ = "material_map"
    __table_args__ = (
        Index("ix_material_map_key", "kind", "tashqi_kalit", unique=True, postgresql_where=text("NOT is_deleted")),
    )

    #: `sheet` | `band` | `hardware` (giblab `material_usage[].kind`)
    kind: Mapped[str] = mapped_column(String(10), kw_only=True)
    #: Fayldagi kod; kodsiz eski fayllarda — kichik harfli, bo'shliqlari siqilgan nom
    tashqi_kalit: Mapped[str] = mapped_column(String(200), kw_only=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("catalog_item.id"), kw_only=True)
    koef: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=Decimal(1), kw_only=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)


class Rezerv(BaseModel):
    """Buyurtma rezervi (sarlavha). Buyurtmada bir vaqtda bittadan ortiq tirik rezerv bo'lmaydi.

    Holat: `faol` → `yechildi` → `sarflandi`; `faol` → `muddati_otdi`; har qaysidan → `bekor`.
    """

    __tablename__ = "rezerv"
    __table_args__ = (
        Index(
            "ix_rezerv_order_tirik",
            "order_id",
            unique=True,
            postgresql_where=text("NOT is_deleted AND holat IN ('faol', 'yechildi', 'muddati_otdi')"),
        ),
    )

    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), index=True, kw_only=True)
    holat: Mapped[str] = mapped_column(String(20), default="faol", kw_only=True)
    #: To'lov shu paytgacha chegaraga yetmasa — `muddati_otdi`
    muddat: Mapped[datetime] = mapped_column(DateTime(timezone=True), kw_only=True)
    yechilgan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    #: Direktor ruxsati: to'lovsiz / limitdan oshgan holda ishlab chiqarishga (Q14, Q22)
    tasdiq_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    tasdiq_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)


class RezervLine(BaseModel):
    """Rezerv qatori — bitta material. Moslanmagan material ham yoziladi (`item_id` bo'sh):
    ehtiyoj ko'rinib tursin va bog'langanda shu qatordan davom etilsin."""

    __tablename__ = "rezerv_line"
    __table_args__ = (
        CheckConstraint("qoplangan_qty >= 0 AND berilgan_qty >= 0 AND kerak_qty >= 0", name="ck_rezerv_line_qty"),
    )

    rezerv_id: Mapped[int] = mapped_column(ForeignKey("rezerv.id", ondelete="CASCADE"), index=True, kw_only=True)
    kind: Mapped[str] = mapped_column(String(10), kw_only=True)
    tashqi_kalit: Mapped[str] = mapped_column(String(200), kw_only=True)
    tashqi_nom: Mapped[str] = mapped_column(String(200), kw_only=True)
    #: Fayldagi miqdor va birlik (list / metr / dona)
    fayl_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), kw_only=True)
    fayl_birlik: Mapped[str] = mapped_column(String(10), kw_only=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("catalog_item.id"), index=True, default=None, kw_only=True)
    #: Katalog birligida: kerak = fayl_qty × koef; qoplangan ≤ kerak. Farqi — ta'minot ehtiyoji
    kerak_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal(0), kw_only=True)
    qoplangan_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal(0), kw_only=True)
    #: Sexga berilgan (sarflangan). Band = qoplangan − berilgan: berilgani endi qoldiqda yo'q
    berilgan_qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal(0), kw_only=True)
