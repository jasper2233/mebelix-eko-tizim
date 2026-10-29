"""Integratsiya jadvallari: kiruvchi xabarlar (inbox) — EKO TZ §6, prototip qoidasi.

Har tashqi xabar (MX Kroy webhook) bir marta qo'llanadi: kalit (`event_id`, bo'lmasa yuklama xeshi) bo'yicha
takrori — `duplicate` (qayta qo'llanmaydi), xuddi shu kalit BOSHQA mazmun bilan — 409 (yuboruvchida xato).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class IntegInbox(BaseModel):
    __tablename__ = "integ_inbox"
    __table_args__ = (Index("ix_integ_inbox_kalit", "manba", "kalit", unique=True),)

    #: `kroy` (MX Kroy)
    manba: Mapped[str] = mapped_column(String(20), kw_only=True)
    #: `event_id` yoki `{event}:{sha256}` — idempotentlik kaliti
    kalit: Mapped[str] = mapped_column(String(200), kw_only=True)
    tur: Mapped[str] = mapped_column(String(40), kw_only=True)
    #: Yuklama xeshi (kanonik JSON) — takror xabar shu bilan solishtiriladi
    xesh: Mapped[str] = mapped_column(String(64), kw_only=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, kw_only=True)
    #: Qo'llash natijasi (masalan `ochildi:2`) yoki `saqlandi` (hozircha ishlov berilmaydigan tur)
    natija: Mapped[str] = mapped_column(String(200), default="", kw_only=True)


class KroyLoyiha(BaseModel):
    """MES buyurtmasi ↔ MX Kroy loyihasi (K1). «Kroy» tugmasi bosilganda yaratiladi; webhooklar shu orqali
    buyurtmaga bog'lanadi."""

    __tablename__ = "kroy_loyiha"

    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), unique=True, kw_only=True)
    #: MX loyiha id (`5d797a939170`) va raqami (`1000050`)
    project_id: Mapped[str] = mapped_column(String(40), unique=True, kw_only=True)
    number: Mapped[str] = mapped_column(String(40), default="", kw_only=True)
    #: MX holati: 0 Не заказан, 1 Заказан, 2 Утвержден, 3 Готов (`project.status` webhook)
    holat: Mapped[int] = mapped_column(default=0, server_default="0", kw_only=True)


class IntegOutbox(BaseModel):
    """Chiquvchi xabarlar navbati (MES → MX) — prototip qoidasi: tashqi tizim javob bermasa xabar YO'QOLMAYDI.

    Xabar tranzaksiya ichida yoziladi (biznes o'zgarishi bilan birga), worker keyin yuboradi. Tartib qat'iy:
    bitta xabar o'tmaguncha keyingilari kutadi; qayta urinish 1, 5, 30, 120, 360 daqiqadan keyin. Kalit bo'yicha
    takror yozilmaydi; MX ga `Idempotency-Key` sarlavhasi bilan boradi."""

    __tablename__ = "integ_outbox"
    __table_args__ = (
        Index("ix_integ_outbox_kalit", "manba", "kalit", unique=True),
        Index("ix_integ_outbox_navbat", "manba", "id", postgresql_where=text("holat = 'yangi'")),
    )

    manba: Mapped[str] = mapped_column(String(20), kw_only=True)
    kalit: Mapped[str] = mapped_column(String(200), kw_only=True)
    method: Mapped[str] = mapped_column(String(8), kw_only=True)
    #: MX API ichidagi yo'l (`/projects/{pid}/operations/{op}/maps/{n}`)
    path: Mapped[str] = mapped_column(String(300), kw_only=True)
    body: Mapped[Any] = mapped_column(JSONB, default=None, kw_only=True)
    #: `yangi` | `yuborildi` | `rad` (4xx — qayta urinishdan foyda yo'q, navbatni to'sib qo'ymaydi)
    holat: Mapped[str] = mapped_column(String(10), default="yangi", kw_only=True)
    urinish: Mapped[int] = mapped_column(default=0, server_default="0", kw_only=True)
    keyingi_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    yuborilgan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    xato: Mapped[str] = mapped_column(String(300), default="", kw_only=True)


class KroyKatalog(BaseModel):
    """MX ga oxirgi yuborilgan katalog holati (pozitsiya xeshi) — K5 faqat o'zgarganini yuboradi."""

    __tablename__ = "kroy_katalog"

    kod: Mapped[str] = mapped_column(String(64), unique=True, kw_only=True)
    xesh: Mapped[str] = mapped_column(String(64), kw_only=True)
