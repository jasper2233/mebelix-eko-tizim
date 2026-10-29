"""Moliya jadvallari (EKO TZ §8; prototip `Moliya.dc.html`).

Pul harakati — kassa jurnalida (`kassa_order`), material — ombor jurnalida; Moliya ularni o'qib hisobot quradi va
faqat o'zining sozlamalarini saqlaydi: rejali to'lovlar, mijoz shartnomasi (to'lov muddati), yopilgan davrlar.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class MoliyaReja(BaseModel):
    """Rejali to'lov (ijara, kommunal, kredit...) — to'lov kalendariga tushadi; o'zi pul yozmaydi."""

    __tablename__ = "moliya_reja"
    __table_args__ = (
        CheckConstraint("summa > 0", name="ck_moliya_reja_summa"),
        CheckConstraint("tur IN ('kirim', 'chiqim')", name="ck_moliya_reja_tur"),
        CheckConstraint("takror IN ('oylik', 'bir')", name="ck_moliya_reja_takror"),
    )

    nom: Mapped[str] = mapped_column(String(120), kw_only=True)
    tur: Mapped[str] = mapped_column(String(6), kw_only=True)
    summa: Mapped[Decimal] = mapped_column(Numeric(16, 2), kw_only=True)
    #: Chiqimda — xarajat moddasi
    turkum: Mapped[str] = mapped_column(String(60), default="", kw_only=True)
    #: `oylik` — har oy shu kuni; `bir` — bir marta shu sanada
    takror: Mapped[str] = mapped_column(String(6), kw_only=True)
    sana: Mapped[date] = mapped_column(Date, kw_only=True)
    faol: Mapped[bool] = mapped_column(default=True, server_default="true", kw_only=True)
    yaratgan_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)


class MoliyaMijozShart(BaseModel):
    """Mijoz shartnomasi: raqami va to'lov muddati (kun). Kredit limiti — `client.kredit_limit` (rezerv ham o'qiydi)."""

    __tablename__ = "moliya_mijoz_shart"

    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"), unique=True, kw_only=True)
    shartnoma_no: Mapped[str] = mapped_column(String(40), default="", kw_only=True)
    #: Bo'sh — umumiy sozlama `tolov_muddat_kun`
    muddat_kun: Mapped[int | None] = mapped_column(default=None, kw_only=True)


class MoliyaDavr(BaseModel):
    """Yopilgan oy (EKO TZ §8 «Davr yopish»): o'sha oy sanasi bilan hujjat yozilmaydi, hisobot natijasi qotadi.

    Qayta ochish — ikki kalit (TZ §10): bir xodim so'raydi, BOSHQA xodim tasdiqlaydi."""

    __tablename__ = "moliya_davr"
    __table_args__ = (CheckConstraint("holat IN ('yopiq', 'ochildi')", name="ck_moliya_davr_holat"),)

    #: Oyning birinchi kuni
    oy: Mapped[date] = mapped_column(Date, unique=True, kw_only=True)
    holat: Mapped[str] = mapped_column(String(8), kw_only=True)
    yopgan_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    yopilgan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    #: Yopilgandagi foyda va zarar (qotgan nusxa — keyingi storno uni o'zgartirmaydi, u joriy oyga tushadi)
    natija: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, kw_only=True)
    ochish_sorov_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    ochish_sabab: Mapped[str] = mapped_column(String(200), default="", kw_only=True)
    ochgan_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    ochilgan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
