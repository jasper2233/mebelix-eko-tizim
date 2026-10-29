"""Tannarx va ish haqi jadvallari (EKO 10).

Ishbay (sdelniy) ish haqi MES skanlaridan: bitta skan — postdagi bitta birlik ish, hajmi detal o'lchamidan
(`services/metrics.part_volume`: arra va qadoqlash — m², kromka — metr, qolgani — dona). Stavka post (kerak
bo'lsa aniq amal — `process_code`) bo'yicha, sanadan boshlab tarix bilan: o'tgan oy eski stavkada qoladi.
Vedomost — davr bo'yicha hisob; tasdiqlangach buxgalteriyaga hisoblangan ish haqi (D 2010 — K 6710) tushadi.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class IshStavka(BaseModel):
    """Post (yoki postdagi aniq amal) birligi uchun ishbay narx, `amal_boshi` dan boshlab."""

    __tablename__ = "ish_stavka"
    __table_args__ = (
        CheckConstraint("narx >= 0", name="ck_ish_stavka_narx"),
        Index(
            "ix_ish_stavka_kalit",
            "post_id",
            "process_code",
            "amal_boshi",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"), kw_only=True)
    #: Bo'sh — postning hamma amali; to'ldirilsa — faqat shu jarayon kodi (masalan stolyarkadagi bitta amal)
    process_code: Mapped[int | None] = mapped_column(default=None, kw_only=True)
    #: So'm / birlik (birlik — postniki: dona, m², metr)
    narx: Mapped[Decimal] = mapped_column(Numeric(14, 2), kw_only=True)
    amal_boshi: Mapped[date] = mapped_column(Date, kw_only=True)
    yozgan_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)


class IshHaqiVedomost(BaseModel):
    """Davr bo'yicha ishbay ish haqi vedomosti. `qoralama` → `tasdiqlangan` (ikki kalit) yoki `bekor`."""

    __tablename__ = "ish_haqi_vedomost"
    __table_args__ = (
        CheckConstraint("holat IN ('qoralama', 'tasdiqlangan', 'bekor')", name="ck_ish_haqi_vedomost_holat"),
        CheckConstraint("dan <= gacha", name="ck_ish_haqi_vedomost_davr"),
        Index("ix_ish_haqi_vedomost_davr", "dan", "gacha", postgresql_where=text("holat <> 'bekor'")),
    )

    no: Mapped[str] = mapped_column(String(20), unique=True, kw_only=True)
    dan: Mapped[date] = mapped_column(Date, kw_only=True)
    gacha: Mapped[date] = mapped_column(Date, kw_only=True)
    holat: Mapped[str] = mapped_column(String(14), kw_only=True)
    jami: Mapped[Decimal] = mapped_column(Numeric(16, 2), kw_only=True)
    skanlar: Mapped[int] = mapped_column(kw_only=True)
    yaratgan_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    tasdiqlagan_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    tasdiqlangan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)


class IshHaqiQator(BaseModel):
    """Vedomost qatori: hodim × post — hajm (post birligida), skan soni, summa."""

    __tablename__ = "ish_haqi_qator"

    vedomost_id: Mapped[int] = mapped_column(
        ForeignKey("ish_haqi_vedomost.id", ondelete="CASCADE"), index=True, kw_only=True
    )
    employee_id: Mapped[int] = mapped_column(ForeignKey("employee.id"), kw_only=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("post.id"), kw_only=True)
    hajm: Mapped[Decimal] = mapped_column(Numeric(14, 3), kw_only=True)
    skanlar: Mapped[int] = mapped_column(kw_only=True)
    summa: Mapped[Decimal] = mapped_column(Numeric(16, 2), kw_only=True)


class StanokNarx(BaseModel):
    """Stanok soatining narxi (amortizatsiya + elektr + xizmat), `amal_boshi` dan. Buyurtmaning boshqaruv
    tannarxiga ideal sikl vaqti bo'yicha, OEE yo'qotishiga — yo'qotilgan vaqt bo'yicha qo'shiladi."""

    __tablename__ = "stanok_narx"
    __table_args__ = (
        CheckConstraint("soat_narxi >= 0", name="ck_stanok_narx_soat"),
        Index("ix_stanok_narx_kalit", "machine_id", "amal_boshi", unique=True),
    )

    machine_id: Mapped[int] = mapped_column(ForeignKey("machine.id"), kw_only=True)
    soat_narxi: Mapped[Decimal] = mapped_column(Numeric(14, 2), kw_only=True)
    amal_boshi: Mapped[date] = mapped_column(Date, kw_only=True)
    yozgan_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)


class AsbobStavka(BaseModel):
    """Asbob (tig') eskirishi va sarf normasi bitta amal birligiga, `amal_boshi` dan.

    `amal`: teshik, qirra_teshik, paz, freza (prisadka, `Part.xnc_summary` sanog'i), rover_metr (kontur metri),
    kromka_metr (yelim, frezer pichog'i), arra_m2 (arra diski). Norma — o'rtacha: masalan sverlo narxi ÷ resursi."""

    __tablename__ = "asbob_stavka"
    __table_args__ = (
        CheckConstraint("narx >= 0", name="ck_asbob_stavka_narx"),
        CheckConstraint(
            "amal IN ('teshik', 'qirra_teshik', 'paz', 'freza', 'rover_metr', 'kromka_metr', 'arra_m2')",
            name="ck_asbob_stavka_amal",
        ),
        Index("ix_asbob_stavka_kalit", "amal", "amal_boshi", unique=True),
    )

    amal: Mapped[str] = mapped_column(String(16), kw_only=True)
    narx: Mapped[Decimal] = mapped_column(Numeric(14, 4), kw_only=True)
    amal_boshi: Mapped[date] = mapped_column(Date, kw_only=True)
    yozgan_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
