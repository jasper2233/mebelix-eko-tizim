"""Buxgalteriya jadvallari (EKO 7): schyotlar rejasi, qoidalar va provodkalar jurnali — 1C siz.

Provodkalar ikki xil: AVTOMATIK (`guruh` — manba kaliti: kassa orderi, ombor harakati, buyurtma, oy soliqi) va
QO'LDA (`guruh` bo'sh). Avtomatik provodkalar manba jurnallaridan hisoblanadi: «bo'lishi kerak» − «yozilgan» =
farq yoziladi (sinxron qayta ishga tushsa ham ikki marta yozilmaydi; manba o'zgarsa tuzatish provodkasi tushadi).
Jurnal faqat qo'shiladi (bazada trigger) — tuzatish ham yangi provodka.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class BuxSchyot(BaseModel):
    """Schyot (BHMS 21 asosida). `tur`: `A` aktiv, `P` passiv, `AP` aktiv-passiv (saldo ikki tomonda)."""

    __tablename__ = "bux_schyot"
    __table_args__ = (CheckConstraint("tur IN ('A', 'P', 'AP')", name="ck_bux_schyot_tur"),)

    kod: Mapped[str] = mapped_column(String(8), unique=True, kw_only=True)
    nom: Mapped[str] = mapped_column(String(150), kw_only=True)
    tur: Mapped[str] = mapped_column(String(2), kw_only=True)
    faol: Mapped[bool] = mapped_column(default=True, server_default="true", kw_only=True)


class BuxQoida(BaseModel):
    """Avtomatik provodka qoidasi: kalit → schyot. Masalan `hisob:naqd` → 5010, `xarajat:Ijara` → 9420,
    `xarajat:*` — moddasi yozilmagan xarajat. O'zgarsa sinxron eski provodkalarni tuzatish bilan qayta tasniflaydi."""

    __tablename__ = "bux_qoida"

    kalit: Mapped[str] = mapped_column(String(80), unique=True, kw_only=True)
    schyot: Mapped[str] = mapped_column(String(8), kw_only=True)


class BuxYozuv(BaseModel):
    """Provodka: Debet `debet` — Kredit `kredit`, summa > 0. Jurnal (UPDATE/DELETE taqiqlangan)."""

    __tablename__ = "bux_yozuv"
    __table_args__ = (
        CheckConstraint("summa > 0", name="ck_bux_yozuv_summa"),
        CheckConstraint("debet <> kredit", name="ck_bux_yozuv_tomon"),
        Index("ix_bux_yozuv_sana", "sana"),
        Index("ix_bux_yozuv_debet", "debet", "sana"),
        Index("ix_bux_yozuv_kredit", "kredit", "sana"),
    )

    sana: Mapped[date] = mapped_column(Date, kw_only=True)
    debet: Mapped[str] = mapped_column(String(8), kw_only=True)
    kredit: Mapped[str] = mapped_column(String(8), kw_only=True)
    summa: Mapped[Decimal] = mapped_column(Numeric(16, 2), kw_only=True)
    izoh: Mapped[str] = mapped_column(String(300), default="", kw_only=True)
    #: Avtomatik provodka manbasi (`ko:15`, `sm:204`, `order:7`, `oy:2026-10`); qo'lda — bo'sh
    guruh: Mapped[str | None] = mapped_column(String(60), index=True, default=None, kw_only=True)
    #: Subkonto: mijoz (4010) va kontragent nomi (6010 — yetkazib beruvchi)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("client.id"), index=True, default=None, kw_only=True)
    kontragent: Mapped[str] = mapped_column(String(150), default="", kw_only=True)
    yozgan_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    #: Qo'lda provodka stornosi
    storno_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("bux_yozuv.id"), unique=True, default=None, kw_only=True
    )
