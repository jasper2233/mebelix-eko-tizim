"""Mahsulotlar ombori — hujjatlar, FIFO partiyalar va harakatlar (docs/14 §9, 2-bosqich).

Qoldiq (`catalog_item.quantity`) FAQAT shu yerdan o'zgaradi: tasdiqlangan kirim/chiqim hujjati yoki
qo'lda tuzatish. Har o'zgarish `stock_movement` qatori (izi) va FIFO partiyasi bilan.

Nomlar ATAYLAB `stock_move` / `stock_item` emas: o'sha nomdagi eski bo'sh jadvallar prodda yotibdi
(`migrations/env.py: LEGACY_TABLES`, 2026-08-17 dagi olib tashlangan modul).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel


class StockDoc(BaseModel):
    """Ombor hujjati: `kirim` (yetkazib beruvchidan, narx DOLLARDA) yoki `chiqim` (sotuv, so'mda).

    `draft` — qoralama, qoldiqqa ta'sir qilmaydi va tahrirlanadi; `confirmed` — tasdiqlangan,
    QULFLANGAN: qoldiq, partiya va harakatlar yozilgan. Raqam (`KIR-2026-0148`) yaratilganda beriladi."""

    __tablename__ = "stock_doc"

    no: Mapped[str] = mapped_column(String(20), unique=True, kw_only=True)
    #: `kirim` | `chiqim`
    kind: Mapped[str] = mapped_column(String(10), index=True, kw_only=True)
    #: `draft` | `confirmed`
    status: Mapped[str] = mapped_column(String(10), default="draft", kw_only=True)
    doc_date: Mapped[date] = mapped_column(Date, kw_only=True)
    #: Bosh qism — dizayndagi maydonlar o'z nomi bilan: kirimda `supplier`, `phone`, `note`,
    #: `invoice`, `receiver`, `due`; chiqimda `client`, `phone`, `addr`, `order`, `seller`, `due`
    head: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, kw_only=True)
    #: Kirim dollar kursi (tasdiqlanganda qotadi)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None, kw_only=True)
    #: Jami summa, so'm (kirimda $ × kurs)
    total: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal(0), kw_only=True)
    #: Chiqimning FIFO tannarxi, so'm — foyda = total − cogs
    cogs: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), default=None, kw_only=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    confirmed_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)


class StockDocLine(BaseModel):
    """Hujjat qatori. `item_id` bo'sh bo'lishi mumkin faqat QORALAMADA (nom yozilgan, hali tanlanmagan)."""

    __tablename__ = "stock_doc_line"

    doc_id: Mapped[int] = mapped_column(ForeignKey("stock_doc.id", ondelete="CASCADE"), index=True, kw_only=True)
    line_no: Mapped[int] = mapped_column(kw_only=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("catalog_item.id"), default=None, kw_only=True)
    #: Yozilgan nom — tanlanmagan qatorda ham, pozitsiya keyin o'chirilsa ham hujjatda qoladi
    name: Mapped[str] = mapped_column(String(200), default="", kw_only=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal(0), kw_only=True)
    #: Narx: kirimda DOLLAR, chiqimda so'm
    price: Mapped[Decimal] = mapped_column(Numeric(14, 4), default=Decimal(0), kw_only=True)
    #: Chegirma, so'm (faqat chiqim) — qator summasidan oshmaydi
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal(0), kw_only=True)
    note: Mapped[str] = mapped_column(String(200), default="", kw_only=True)
    #: Chiqimda shu qatorning FIFO tannarxi, so'm (tasdiqlanganda)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), default=None, kw_only=True)


class StockLot(BaseModel):
    """FIFO partiyasi: kirim (yoki boshlang'ich qoldiq / ortiqcha tuzatish) bitta partiya ochadi,
    chiqim ENG ESKI partiyadan oladi. `qty_left` — shu partiyadan qolgani."""

    __tablename__ = "stock_lot"

    __table_args__ = (
        # Chiqimda: shu pozitsiyaning qolgan partiyalari, eng eskisi birinchi
        Index("ix_stock_lot_open", "item_id", "received_on", "id", postgresql_where=text("qty_left > 0")),
    )

    item_id: Mapped[int] = mapped_column(ForeignKey("catalog_item.id"), index=True, kw_only=True)
    #: Bo'sh — boshlang'ich qoldiq yoki qo'lda tuzatish
    doc_id: Mapped[int | None] = mapped_column(ForeignKey("stock_doc.id"), default=None, kw_only=True)
    received_on: Mapped[date] = mapped_column(Date, kw_only=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), kw_only=True)
    qty_left: Mapped[Decimal] = mapped_column(Numeric(12, 3), kw_only=True)
    #: Bir birlik tannarxi, so'm
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), kw_only=True)
    usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), default=None, kw_only=True)
    rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None, kw_only=True)
    #: `Boshlang'ich` / kirim raqami / `Tuzatish` — kartochkadagi «Hujjat» ustuni
    source: Mapped[str] = mapped_column(String(30), default="", kw_only=True)


class StockMovement(BaseModel):
    """Qoldiq harakati — har o'zgarishning izi (kartochkadagi «Harakat tarixi»)."""

    __tablename__ = "stock_movement"

    __table_args__ = (Index("ix_stock_movement_item", "item_id", "created_at"),)

    item_id: Mapped[int] = mapped_column(ForeignKey("catalog_item.id"), kw_only=True)
    doc_id: Mapped[int | None] = mapped_column(ForeignKey("stock_doc.id"), default=None, kw_only=True)
    #: `kirim` | `chiqim` | `tuzatish` (keyin `sex`, `inv`)
    kind: Mapped[str] = mapped_column(String(12), kw_only=True)
    #: Ishorali: kirim +, chiqim −
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), kw_only=True)
    #: Harakatdan keyingi qoldiq
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 3), kw_only=True)
    #: Chiqimning FIFO tannarxi, so'm (kirimda — partiya qiymati)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), default=None, kw_only=True)
    #: «Kirim · Ningbo Haitian», «Sotuv · Jahongir Rustamov · Jahongir Abdullayev»
    note: Mapped[str] = mapped_column(String(200), default="", kw_only=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
