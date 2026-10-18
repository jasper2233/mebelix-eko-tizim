from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB
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
    #: PAKET bo'lsa — unda nechta bo'lak bo'lgani (detallar + to'ldiruvchi), aks holda bo'sh.
    #: 15 sm dan kichik detal lentada qaltiraydi, shuning uchun 4 tagacha detal zich tiqilib
    #: birga o'tkaziladi va Pico paketni BITTA detal deb o'lchaydi (docs/12 §4.26). Shunday
    #: qatorda `measured_mm` — PAKETNING uzunligi, bu detalning emas, `delta_mm` esa bo'sh:
    #: yig'indi mos kelgani ma'lum, lekin har bo'lakning uzunligi alohida o'lchanmagan.
    pack_n: Mapped[int | None] = mapped_column(SmallInteger, default=None, kw_only=True)


class KromkaKalibSession(BaseModel):
    """Kalibrlash sessiyasi — admin etalon detallarni o'tkazayotgan vaqt oralig'i (docs/12 §4.19).

    Nuqtalar alohida saqlanmaydi: ular oddiy `olchov` hodisalari (`andon_event`), Pico ularni har
    o'tishda `d1`/`d2`/`ish_ms` bilan yuboradi. Sessiya faqat aytadi: shu oraliqda o'tgan detal
    ETALON edi va uzunligi qancha. Shu oraliqdagi o'lchov skanga bog'lanmaydi.

    `segments` — `[{"L_ref": mm, "dan": iso}]`: etalon almashganda yangi bo'lak qo'shiladi, hodisa
    vaqti bo'yicha eng oxirgi boshlangan bo'lak olinadi. `excluded` — admin chetlatgan hodisa id'lari."""

    __tablename__ = "kromka_kalib_session"

    __table_args__ = (
        # Stanokda bir vaqtda bitta ochiq sessiya
        Index(
            "ix_kromka_kalib_session_open",
            "machine_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL AND NOT is_deleted"),
        ),
    )

    machine_id: Mapped[int] = mapped_column(ForeignKey("machine.id"), kw_only=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), kw_only=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    segments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default_factory=list, kw_only=True)
    excluded: Mapped[list[int]] = mapped_column(JSONB, default_factory=list, kw_only=True)


class KromkaKalApply(BaseModel):
    """Kalibrlashni Pico'ga qo'llash buyrug'i (docs/12 §4.20, 3-qadam).

    Server buyruqni agentga `POST /bridge-agents/andon` JAVOBIDA beradi (`kal_set`), agent
    (1.12.0+) uni Pico'ga `SET ...` qatori qilib yozadi, Pico `{"ev":"kal",...}` bilan javob
    qaytaradi — o'sha `kal` hodisasidagi qiymatlar `values` ga mos kelsa `confirmed_at` yoziladi.
    `previous` — qo'llashdan oldingi Pico qiymatlari: orqaga qaytarish shu bilan yangi buyruq."""

    __tablename__ = "kromka_kal_apply"

    __table_args__ = (Index("ix_kromka_kal_apply_machine", "machine_id", "created_at"),)

    machine_id: Mapped[int] = mapped_column(ForeignKey("machine.id"), kw_only=True)
    session_id: Mapped[int | None] = mapped_column(ForeignKey("kromka_kalib_session.id"), default=None, kw_only=True)
    #: Pico'ga yuboriladigan qiymatlar (faqat shu kalitlar `SET` ga kiradi)
    values: Mapped[dict[str, float]] = mapped_column(JSONB, kw_only=True)
    previous: Mapped[dict[str, float]] = mapped_column(JSONB, kw_only=True)
    #: Orqaga qaytarish bo'lsa — qaysi qo'llash bekor qilinmoqda
    rollback_of_id: Mapped[int | None] = mapped_column(ForeignKey("kromka_kal_apply.id"), default=None, kw_only=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    #: Agentga birinchi marta berilgan payt
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    #: Pico qiymatlarni qaytarib aytgan payt (`kal` hodisasi)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
