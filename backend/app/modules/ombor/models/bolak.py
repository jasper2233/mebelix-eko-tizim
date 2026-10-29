"""Qoldiq bo'laklari — kroydan ortgan FOYDALI list bo'laklari (EKO TZ §4.4, 2.3b; MX Kroy K3, 3-bosqich).

Yagona registr, ikki manba:
- `mes` — MES o'zi yozgan bo'lak (`waste_item`, GibLab `business="true"`, arra terminalida `ATX-…` yorlig'i):
  omborchi yorliqni skanerlab QABUL qiladi.
- `mx` — MX Kroy kroydan keyin yuborgan kirim hujjati (`kroy_intake`, `MES_QOLDIQ_V1.md` §3): bo'lak `kutish`
  holatida yaratiladi va shu karta listi arradan chiqqach (`map.done`) `ombor` ga o'tadi.

MX qoldiq ombori sifatida shu jadvaldan qidiradi, band qiladi va ishlatadi (`routes/kroy.py`). Bitta qatorda
bir xil o'lchamdagi `qty` dona bo'lishi mumkin (karta nusxalari); `qty_pending` — hali arradan chiqmagani.

Bo'lak `catalog_item.quantity` ga KIRMAYDI: uning tannarxi butun list bilan asl buyurtmaga allaqachon
sarflangan. Bu — hisob emas, ro'yxat: qayerda, qanday o'lchamda, qaysi buyurtmaga ketgani.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel

#: Arradan chiqishini kutmoqda (MX kirimi) — boshqa buyurtmaga berilmaydi
KUTISH = "kutish"
OMBOR = "ombor"
#: Boshqa buyurtmaga ishlatildi (sotildi)
ISHLATILDI = "ishlatildi"
#: Yaroqsiz — chiqitga (o'tin)
CHIQIT = "chiqit"
#: MX kirimi bekor qilindi — bo'lak umuman bo'lmagan
BEKOR = "bekor"


class OmborBolak(BaseModel):
    __tablename__ = "ombor_bolak"
    __table_args__ = (
        Index("ix_ombor_bolak_waste", "waste_id", unique=True, postgresql_where=text("NOT is_deleted")),
        Index("ix_ombor_bolak_joy_item", "joy", "item_id"),
        Index("ix_ombor_bolak_kirim", "kirim_id"),
        CheckConstraint("qty >= 0 AND qty_pending >= 0", name="ck_ombor_bolak_qty"),
    )

    #: MES bo'lagi (`ATX-…`); MX kirimida bo'sh
    waste_id: Mapped[int | None] = mapped_column(ForeignKey("waste_item.id"), default=None, kw_only=True)
    #: Yorliqdagi QR (`ATX-…`) yoki MX bo'lagida `MX-{kirim}-{n}` — skan shu bilan
    barkod: Mapped[str] = mapped_column(String(120), index=True, kw_only=True)
    #: Katalog pozitsiyasi (moslangan bo'lsa); bo'lmasa faqat fayldagi nom
    item_id: Mapped[int | None] = mapped_column(ForeignKey("catalog_item.id"), default=None, kw_only=True)
    material_nom: Mapped[str] = mapped_column(String(150), kw_only=True)
    #: Material kodi (MX: operatsiya kodi; bo'lmasa bo'sh) va turi (`LDSP`, `HDF` …), qalinlik mm
    material_kod: Mapped[str] = mapped_column(String(60), default="", kw_only=True)
    tur: Mapped[str] = mapped_column(String(20), default="", kw_only=True)
    qalinlik: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), default=None, kw_only=True)
    #: Foydali o'lcham, mm
    uzunlik: Mapped[Decimal] = mapped_column(Numeric(8, 1), kw_only=True)
    eni: Mapped[Decimal] = mapped_column(Numeric(8, 1), kw_only=True)
    #: Mavjud dona va arradan chiqishini kutayotgan dona
    qty: Mapped[int] = mapped_column(default=1, server_default="1", kw_only=True)
    qty_pending: Mapped[int] = mapped_column(default=0, server_default="0", kw_only=True)
    #: Kirimdagi jami dona — arradan chiqish ulushi shundan hisoblanadi (keyin sotilgani ta'sir qilmaydi)
    jami: Mapped[int] = mapped_column(default=1, server_default="1", kw_only=True)
    #: Qaysi buyurtma kroyidan chiqqan (MX kirimida `mes_order_ref` bo'lmasa bo'sh)
    manba_order_id: Mapped[int | None] = mapped_column(ForeignKey("order.id"), default=None, kw_only=True)
    joy: Mapped[str] = mapped_column(String(12), default=OMBOR, kw_only=True)
    #: Ishlatilgan bo'lsa — qaysi buyurtmaga
    order_id: Mapped[int | None] = mapped_column(ForeignKey("order.id"), default=None, kw_only=True)
    qabul_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    yopilgan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    # --- MX Kroy (K3) ---
    #: `mes` | `mx`
    manba: Mapped[str] = mapped_column(String(4), default="mes", server_default="mes", kw_only=True)
    #: MX kirim hujjati (`IN-2026-0001`), karta raqami va nusxalari (arradan chiqish ulushi uchun)
    kirim_id: Mapped[str | None] = mapped_column(String(20), default=None, kw_only=True)
    karta: Mapped[int | None] = mapped_column(default=None, kw_only=True)
    nusxa: Mapped[int] = mapped_column(default=1, server_default="1", kw_only=True)
    #: MX loyihasi (manba) va band qilgan MX loyihasi / raqami
    mx_loyiha: Mapped[str | None] = mapped_column(String(40), default=None, kw_only=True)
    #: MX operatsiyasi (material): karta raqami har operatsiyada 1 dan boshlanadi — `map.done` shu bilan
    mx_op: Mapped[str | None] = mapped_column(String(40), default=None, kw_only=True)
    mx_raqam: Mapped[str | None] = mapped_column(String(40), default=None, kw_only=True)
    band_loyiha: Mapped[str | None] = mapped_column(String(40), default=None, index=True, kw_only=True)
    band_raqam: Mapped[str | None] = mapped_column(String(40), default=None, kw_only=True)
    chiziqli: Mapped[bool] = mapped_column(default=False, server_default="false", kw_only=True)
    toza_chet: Mapped[bool] = mapped_column(default=False, server_default="false", kw_only=True)
    #: Butun list maydoni (m²) va foiz — MX hisoblagan (sotuv narxi va hisobot uchun)
    list_m2: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), default=None, kw_only=True)
    foiz: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), default=None, kw_only=True)
    m2_narx: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), default=None, kw_only=True)
    izoh: Mapped[str] = mapped_column(String(200), default="", kw_only=True)


class KroyIntake(BaseModel):
    """MX kroyidan keyingi kirim/chiqim hujjati (`MES_QOLDIQ_V1.md` §3). Bekor qilinsa (§4) — teskarisi."""

    __tablename__ = "kroy_intake"

    #: `IN-2026-0001` — MX shu raqamni saqlaydi va bekor qilishda qaytaradi
    no: Mapped[str] = mapped_column(String(20), unique=True, kw_only=True)
    mx_loyiha: Mapped[str] = mapped_column(String(40), index=True, kw_only=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("order.id"), default=None, kw_only=True)
    #: `faol` | `bekor`
    holat: Mapped[str] = mapped_column(String(8), default="faol", kw_only=True)
    #: MX yuborgan hujjat butunligicha (mijozga berilgan bo'laklar, narxlar — hisobot uchun)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, kw_only=True)
    #: Ishlatilgan ombor bo'laklari: [{"id": 101, "qty": 1}] — bekor qilinganda qaytariladi
    consumed: Mapped[list[dict[str, int]]] = mapped_column(JSONB, default_factory=list, kw_only=True)
