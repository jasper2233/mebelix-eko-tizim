from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import DowntimeKind, db_enum


class DowntimeReason(BaseModel):
    """To'xtash sababi — ro'yxatni admin Tizim sozlamalarida yuritadi (egasining xlsx ro'yxati kodga
    yozilmaydi). O'chirilmaydi, faqat `is_active=False`: eski to'xtashlar sababini yo'qotmasin.

    Nomi `stop_reason` EMAS: o'sha nomdagi eski (2026-08-21 da qaytarilgan) jadval prodda qolgan
    (`migrations/env.py: LEGACY_TABLES`)."""

    __tablename__ = "downtime_reason"

    name: Mapped[str] = mapped_column(String(60), kw_only=True)
    #: Rejali to'xtash (tushlik, sozlash) — OEE reja vaqtidan chiqariladi, Availability'ni tushirmaydi
    is_planned: Mapped[bool] = mapped_column(default=False, kw_only=True)
    #: "Boshqa" kabi sabab — izohsiz saqlanmaydi
    needs_note: Mapped[bool] = mapped_column(default=False, kw_only=True)
    order_index: Mapped[int] = mapped_column(default=0, kw_only=True)
    is_active: Mapped[bool] = mapped_column(default=True, kw_only=True)


class Downtime(BaseModel):
    """Stanok to'xtashi — sababi shu yerga yoziladi.

    Pico to'xtashlari xom `andon_event` dan CHIQARILADI (`services/downtimes.sync_machine`): qizil
    (FAULT), hammasi o'chiq (OFF) va sariq chiroq Tizim sozlamalaridagi chegaradan uzoq yonsa (IDLE,
    vaqt sariq yongan paytdan). LOCK — operator qulf tugmasida sababni o'zi aytgan to'xtash.

    `start_key` — to'xtashni boshlagan hodisa (`{session}-{seq}`) yoki `lock-{uuid}`: qayta hisoblash
    shu kalit bo'yicha yozuvni topib faqat `ended_at` ni yangilaydi, sababga tegmaydi."""

    __tablename__ = "downtime"

    __table_args__ = (
        Index("ix_downtime_machine_key", "machine_id", "start_key", unique=True),
        Index("ix_downtime_machine_started", "machine_id", "started_at"),
    )

    machine_id: Mapped[int] = mapped_column(ForeignKey("machine.id"), kw_only=True)
    kind: Mapped[DowntimeKind] = mapped_column(db_enum(DowntimeKind), kw_only=True)
    start_key: Mapped[str] = mapped_column(String(40), kw_only=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), kw_only=True)
    #: `None` — to'xtash davom etmoqda
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    reason_id: Mapped[int | None] = mapped_column(ForeignKey("downtime_reason.id"), default=None, kw_only=True)
    note: Mapped[str | None] = mapped_column(Text, default=None, kw_only=True)
    #: Sababni kiritgan — o'sha paytdagi smena egasi (brigadaning langar smenasi)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employee.id"), default=None, kw_only=True)
    reason_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
