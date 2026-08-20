from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import StopKind, db_enum


class StopReason(BaseModel):
    """Stanok to'xtash sababi — ro'yxatni admin yuritadi.

    `kind` — egasining taksonomiyasi (rejali/rejasiz), OEE hisobiga TA'SIR QILMAYDI.
    Hisobni `excludes_planned` hal qiladi:

      True   vaqt PLANNED TIME dan chiqariladi — ishlab chiqarish uchun
             rejalashtirilmagan (tushlik, tanaffus, smena yo'q). OEE tushmaydi.
      False  vaqt RUN dan chiqadi, PLANNED joyida qoladi — ya'ni Availability
             YO'QOTISHI (sozlash, arra almashtirish, nosozlik, material yo'q).

    Ikki ustunni ajratish ataylab: "sozlash" egasining ro'yxatida rejali, lekin
    standart bo'yicha u qisqartirilishi mumkin bo'lgan yo'qotish (Six Big Losses
    — Setup & Adjustments). PLANNED dan chiqarilsa, eng katta zaxira hisobotda
    umuman ko'rinmay qolardi. Bayroq sozlanadigan — qaror kodda qotib qolmasin.
    """

    __tablename__ = "stop_reason"

    __table_args__ = (Index("ix_stop_reason_name", "name", unique=True, postgresql_where=text("NOT is_deleted")),)

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    name: Mapped[str] = mapped_column(String(60), kw_only=True)
    kind: Mapped[StopKind] = mapped_column(db_enum(StopKind), kw_only=True)
    excludes_planned: Mapped[bool] = mapped_column(default=False, kw_only=True)
    order_index: Mapped[int] = mapped_column(default=0, kw_only=True)
    is_active: Mapped[bool] = mapped_column(default=True, kw_only=True)


class MachineStop(BaseModel):
    """Bitta to'xtash oralig'i. `ended_at IS NULL` = hozir to'xtab turibdi.

    Ish markaziga yoziladi, smenaga emas: stanok operatorsiz ham to'xtab turadi
    ("operator yo'q", "zakaz yo'q") va o'sha vaqt ham Availability yo'qotishi.
    `employee_id` — tugmani bosgan odam, bo'lmasligi mumkin.
    """

    __tablename__ = "machine_stop"

    __table_args__ = (
        # Hisobot davr kesimida o'qiydi; ochiq to'xtashni topish ham shu indeksda
        Index("ix_machine_stop_machine_started", "machine_id", "started_at"),
    )

    machine_id: Mapped[int] = mapped_column(ForeignKey("machine.id"), kw_only=True)
    reason_id: Mapped[int] = mapped_column(ForeignKey("stop_reason.id"), kw_only=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), kw_only=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employee.id"), default=None, kw_only=True)
    note: Mapped[str | None] = mapped_column(Text, default=None, kw_only=True)
