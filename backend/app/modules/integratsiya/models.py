"""Integratsiya jadvallari: kiruvchi xabarlar (inbox) — EKO TZ §6, prototip qoidasi.

Har tashqi xabar (MX Kroy webhook) bir marta qo'llanadi: kalit (`event_id`, bo'lmasa yuklama xeshi) bo'yicha
takrori — `duplicate` (qayta qo'llanmaydi), xuddi shu kalit BOSHQA mazmun bilan — 409 (yuboruvchida xato).
"""

from typing import Any

from sqlalchemy import ForeignKey, Index, String
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
