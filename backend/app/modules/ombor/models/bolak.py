"""Qoldiq bo'laklari — kroydan ortgan FOYDALI list bo'laklari (EKO TZ §4.4, 2.3b).

MES ularni allaqachon yozadi (`waste_item`, GibLab `business="true"`) va arra terminalida `ATX-…`
yorlig'ini chiqaradi. Ombor shu yorliqni skanerlab bo'lakni QABUL qiladi: endi u omborda turibdi,
materiali va o'lchami ma'lum — keyingi kroylarda ishlatish mumkin (MX Kroy integratsiyasi, 3-bosqich).

Bo'lak `catalog_item.quantity` ga KIRMAYDI: uning tannarxi butun list bilan asl buyurtmaga allaqachon
sarflangan. Bu — hisob emas, ro'yxat: qayerda, qanday o'lchamda, qaysi buyurtmaga ketgani.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel

OMBOR = "ombor"
#: Boshqa buyurtmaga ishlatildi
ISHLATILDI = "ishlatildi"
#: Yaroqsiz — chiqitga (o'tin)
CHIQIT = "chiqit"


class OmborBolak(BaseModel):
    __tablename__ = "ombor_bolak"
    __table_args__ = (
        Index("ix_ombor_bolak_waste", "waste_id", unique=True, postgresql_where=text("NOT is_deleted")),
        Index("ix_ombor_bolak_joy_item", "joy", "item_id"),
    )

    waste_id: Mapped[int] = mapped_column(ForeignKey("waste_item.id"), kw_only=True)
    #: Yorliqdagi QR (`ATX-…`) — skan shu bilan
    barkod: Mapped[str] = mapped_column(String(120), index=True, kw_only=True)
    #: Katalog pozitsiyasi (moslangan bo'lsa); bo'lmasa faqat fayldagi nom
    item_id: Mapped[int | None] = mapped_column(ForeignKey("catalog_item.id"), default=None, kw_only=True)
    material_nom: Mapped[str] = mapped_column(String(150), kw_only=True)
    #: Foydali o'lcham, mm
    uzunlik: Mapped[Decimal] = mapped_column(Numeric(8, 1), kw_only=True)
    eni: Mapped[Decimal] = mapped_column(Numeric(8, 1), kw_only=True)
    #: Qaysi buyurtma kroyidan chiqqan
    manba_order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), kw_only=True)
    joy: Mapped[str] = mapped_column(String(12), default=OMBOR, kw_only=True)
    #: Ishlatilgan bo'lsa — qaysi buyurtmaga
    order_id: Mapped[int | None] = mapped_column(ForeignKey("order.id"), default=None, kw_only=True)
    qabul_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    yopilgan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
