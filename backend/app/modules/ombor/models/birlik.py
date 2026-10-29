"""Barkodli jismoniy birlik — bitta list yoki bitta rulon (EKO TZ §4.4, 2.3-bosqich).

Katalog pozitsiyasi (`catalog_item`) — «nima»; birlik — «qaysi biri». Har birlik kirimda tizimning
o'z barkodini oladi (`EK0000123`); ishlab chiqaruvchi kodi alohida saqlanadi (ta'minotchi zavodga
buyurtmani shu kod/nom bilan beradi).

Qaysi pozitsiyalar birlik bilan yuradi — `services/birlik.py: tracked`: listlar va paneallar (`M`)
— har biri 1 dona; metrdagi materiallar (kromka) — har rulon o'z uzunligi bilan. Furnitura donada,
birliksiz — u katalog kodi bo'yicha beriladi.

`catalog_item.quantity` — korxonaga tegishli JAMI miqdor: ombordagi va SEXDAGI rulon qoldiqlari ham
kiradi. Rulon sexga berilganda miqdor kamaymaydi (u hali bizniki), kamayish faqat buyurtmaga sarf
yoki «rulon tugadi» bilan. Shuning uchun sexdagi qoldiq rezervni ham qoplaydi va keyingi buyurtma
avval o'shandan oladi.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel

#: Birlik joyi
OMBOR = "ombor"
SEX = "sex"
#: Sarflangan, sotilgan yoki hisobdan chiqarilgan — qoldig'i 0
TUGADI = "tugadi"


class MaterialBirlik(BaseModel):
    __tablename__ = "material_birlik"
    __table_args__ = (
        # Berishda: pozitsiyaning shu joydagi tirik birliklari, eng eskisi birinchi
        Index("ix_material_birlik_item_joy", "item_id", "joy", "id", postgresql_where=text("qoldiq > 0")),
    )

    #: Tizim barkodi `EK` + 7 raqam — id dan yasaladi (yaratilgandan keyin beriladi)
    barkod: Mapped[str | None] = mapped_column(String(20), unique=True, default=None, kw_only=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("catalog_item.id"), index=True, kw_only=True)
    #: Ishlab chiqaruvchining yorlig'idagi kod (bo'lsa)
    ishlab_kod: Mapped[str | None] = mapped_column(String(60), default=None, kw_only=True)
    #: Boshlang'ich hajm katalog birligida: listda 1, rulonda metr
    hajm: Mapped[Decimal] = mapped_column(Numeric(12, 3), kw_only=True)
    qoldiq: Mapped[Decimal] = mapped_column(Numeric(12, 3), kw_only=True)
    joy: Mapped[str] = mapped_column(String(10), default=OMBOR, kw_only=True)
    #: Qaysi kirim bilan kelgan (yorliqlangan eski qoldiqda bo'sh)
    doc_id: Mapped[int | None] = mapped_column(ForeignKey("stock_doc.id"), default=None, kw_only=True)
    #: Oxirgi marta qaysi buyurtmaga sarflangan
    order_id: Mapped[int | None] = mapped_column(ForeignKey("order.id"), default=None, kw_only=True)
    sexga_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
