from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import PachkaStatus, db_enum


class Pachka(BaseModel):
    """Qadoq — bitta o'ramga yig'ilgan detal nusxalari (TZ Upakovka).

    Tarkibni ALGORITM emas, qadoqlovchi belgilaydi: "Qadoq yaratish" bosiladi,
    detallar birma-bir skanerlanadi, "Yakunlash" bilan yopiladi. Tizim og'irlikni
    faqat KO'RSATADI — chegara qo'ymaydi, qaror hodimniki.

    `code` — chekdagi QR matni. Detal QR'i `{mahsulot}_{detal}[_n]` shaklida
    (`scanning._QR_RE` ostki chiziq kutadi), bu esa `PK-` bilan boshlanadi va
    ostki chiziq umuman yo'q — terminal skanni ko'rib qaysi oqimga yuborishni
    shundan ajratadi.
    """

    __tablename__ = "pachka"

    __table_args__ = (
        Index("ix_pachka_code", "code", unique=True, postgresql_where=text("NOT is_deleted")),
        Index("ix_pachka_order_status", "order_id", "status"),
    )

    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), index=True, kw_only=True)
    code: Mapped[str] = mapped_column(String(40), kw_only=True)  # PK-B-2026-014-03
    status: Mapped[PachkaStatus] = mapped_column(
        db_enum(PachkaStatus), default=PachkaStatus.OPEN, index=True, kw_only=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    #: Ombordan chiqarilgan payt: bitta QR skani ichidagi HAMMA detalni chiqaradi.
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)


class PachkaItem(BaseModel):
    """Qadoq tarkibi: bitta detal NUSXASI bitta qadoqda bo'ladi.

    Yagonalik nusxa bo'yicha — bir nusxa ikki qadoqqa tushib qolsa ombor hisobi
    ikki marta chiqarilardi. Ochiq qadoqdan chiqarish — qatorni yumshoq o'chirish.
    """

    __tablename__ = "pachka_item"

    __table_args__ = (
        Index("ix_pachka_item_instance", "instance_id", unique=True, postgresql_where=text("NOT is_deleted")),
        Index("ix_pachka_item_pachka", "pachka_id"),
    )

    pachka_id: Mapped[int] = mapped_column(ForeignKey("pachka.id"), kw_only=True)
    instance_id: Mapped[int] = mapped_column(ForeignKey("part_instance.id"), kw_only=True)
