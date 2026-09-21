from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import KromkaVerdict, db_enum


class KromkaMeasurement(BaseModel):
    """Kromka stansiyasi o'lchovi — DETALGA bog'langan holda.

    Xom hodisa `andon_event` da o'zgarmasdan qoladi; bu jadval esa hukmni saqlaydi:
    qaysi nusxaga tegishli, qaysi tomon guruhi (uzunlik yoki eni) yopildi, kutilgan
    o'lcham qancha edi va farq qancha.

    Bog'lash qoidasi (`services/kromka.py`): detal BIRINCHI DATCHIKKA KIRGAN lahza
    hisoblanadi (o'lchov vaqtidan `ish_ms` ayiriladi) va shu lahza atrofidagi
    skanlardan o'lchamga mos keladigani tanlanadi (`kromka_bind_window_s`).
    Ya'ni «joriy detal» degan alohida holat saqlanmaydi — uni skanning o'zi bildiradi.

    Tomon NOMI (t/b/l/r) saqlanmaydi, GURUHI saqlanadi: bir xil uzunlikdagi ikki
    qirrani o'lchov ajrata olmaydi va ajratishi ham shart emas — ikkalasi ham
    lentalanadi, tartib befarq."""

    __tablename__ = "kromka_measurement"

    __table_args__ = (
        Index("ix_kromka_measurement_machine_at", "machine_id", "measured_at"),
        Index("ix_kromka_measurement_instance", "instance_id"),
    )

    machine_id: Mapped[int] = mapped_column(ForeignKey("machine.id"), kw_only=True)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), kw_only=True)
    #: Pico kodi: OK / FARQ / FAQAT1 / FAQAT2
    code: Mapped[str] = mapped_column(String(10), kw_only=True)
    verdict: Mapped[KromkaVerdict] = mapped_column(db_enum(KromkaVerdict), index=True, kw_only=True)
    #: Pico o'lchagan uzunlik (mm) — aynan shu safar kromkalanayotgan qirraning uzunligi.
    #: Kod OK bo'lmasa (FAQAT1/FAQAT2 — bitta datchik ishlagan) o'lcham umuman yo'q.
    measured_mm: Mapped[float | None] = mapped_column(Numeric(9, 1), default=None, kw_only=True)
    #: Bog'langan skan va nusxa (`skanersiz` da bo'sh)
    scan_id: Mapped[int | None] = mapped_column(ForeignKey("scan.id"), default=None, kw_only=True)
    instance_id: Mapped[int | None] = mapped_column(ForeignKey("part_instance.id"), default=None, kw_only=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("order.id"), default=None, kw_only=True)
    #: Qaysi guruh yopildi: `length` (uzunlik bo'ylab qirra) yoki `width` (eni bo'ylab)
    side_group: Mapped[str | None] = mapped_column(String(10), default=None, kw_only=True)
    expected_mm: Mapped[float | None] = mapped_column(Numeric(9, 1), default=None, kw_only=True)
    delta_mm: Mapped[float | None] = mapped_column(Numeric(9, 1), default=None, kw_only=True)
