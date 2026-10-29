"""Soliq jadvallari (EKO TZ §9).

Stavka va rejim kodga yozilmaydi: har obunachi (o'z bazasi) sozlaydi va TARIX saqlanadi — rejim yil o'rtasida
almashsa ham o'tgan oy o'sha paytdagi rejim va stavka bilan hisoblanadi. ESF — chiquvchi (sotuvdan) va kiruvchi
(yetkazib beruvchidan); operatorga yuborish adapter orqali, navbat bilan (operator ishlamasa sotuv to'xtamaydi).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SoliqKorxona(BaseModel):
    """Korxona rekvizitlari va soliq sozlamalari — bitta qator (id=1)."""

    __tablename__ = "soliq_korxona"

    nomi: Mapped[str] = mapped_column(String(200), default="", kw_only=True)
    stir: Mapped[str] = mapped_column(String(9), default="", kw_only=True)
    manzil: Mapped[str] = mapped_column(String(300), default="", kw_only=True)
    bank: Mapped[str] = mapped_column(String(150), default="", kw_only=True)
    mfo: Mapped[str] = mapped_column(String(5), default="", kw_only=True)
    hisob_raqam: Mapped[str] = mapped_column(String(20), default="", kw_only=True)
    direktor: Mapped[str] = mapped_column(String(120), default="", kw_only=True)
    buxgalter: Mapped[str] = mapped_column(String(120), default="", kw_only=True)
    #: QQS to'lovchi ro'yxatdan o'tish kodi (QQS rejimida ESF da)
    qqs_kod: Mapped[str] = mapped_column(String(20), default="", kw_only=True)
    #: ESF operatori: `sinov` (lokal sinov operatori); haqiqiy operatorlar adapteri qo'shilganda nomi shu yerga
    esf_operator: Mapped[str] = mapped_column(String(20), default="sinov", kw_only=True)
    #: Buyurtma (mebel) ESF qatori: nomi, MXIK, o'lchov birligi kodi
    buyurtma_nomi: Mapped[str] = mapped_column(String(200), default="Mebel (buyurtma bo'yicha)", kw_only=True)
    buyurtma_mxik: Mapped[str] = mapped_column(String(17), default="", kw_only=True)
    buyurtma_birlik: Mapped[str] = mapped_column(String(10), default="", kw_only=True)


class SoliqRejim(BaseModel):
    """Soliq rejimi va stavkalari `amal_boshi` sanasidan boshlab (tarix)."""

    __tablename__ = "soliq_rejim"
    __table_args__ = (
        CheckConstraint("rejim IN ('qqs', 'aylanma')", name="ck_soliq_rejim_rejim"),
        CheckConstraint("qqs_foiz >= 0 AND qqs_foiz <= 50", name="ck_soliq_rejim_qqs"),
        CheckConstraint("aylanma_foiz >= 0 AND aylanma_foiz <= 50", name="ck_soliq_rejim_aylanma"),
    )

    amal_boshi: Mapped[date] = mapped_column(Date, unique=True, kw_only=True)
    #: `qqs` — QQS to'lovchi; `aylanma` — aylanmadan olinadigan soliq (yagona soliq)
    rejim: Mapped[str] = mapped_column(String(8), kw_only=True)
    qqs_foiz: Mapped[Decimal] = mapped_column(Numeric(5, 2), kw_only=True)
    aylanma_foiz: Mapped[Decimal] = mapped_column(Numeric(5, 2), kw_only=True)
    yozgan_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)


class SoliqMijoz(BaseModel):
    """Mijoz soliq rekvizitlari (EKO TZ §9 S8): yuridik — STIR, jismoniy — JShShIR."""

    __tablename__ = "soliq_mijoz"

    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"), unique=True, kw_only=True)
    yuridik: Mapped[bool] = mapped_column(default=False, kw_only=True)
    nomi: Mapped[str] = mapped_column(String(200), default="", kw_only=True)
    stir: Mapped[str] = mapped_column(String(9), default="", kw_only=True)
    jshshir: Mapped[str] = mapped_column(String(14), default="", kw_only=True)
    bank: Mapped[str] = mapped_column(String(150), default="", kw_only=True)
    mfo: Mapped[str] = mapped_column(String(5), default="", kw_only=True)
    hisob_raqam: Mapped[str] = mapped_column(String(20), default="", kw_only=True)
    qqs_kod: Mapped[str] = mapped_column(String(20), default="", kw_only=True)


class SoliqEsf(BaseModel):
    """Elektron hisob-faktura. Holatlar (TZ S3): qoralama → navbatda → yuborildi → qabul_qilindi / rad_etildi;
    `bekor`; kiruvchida: kutilmoqda → qabul_qilindi / rad_etildi. Qatorlar va rekvizitlar yasalgan paytdagi nusxa."""

    __tablename__ = "soliq_esf"
    __table_args__ = (
        CheckConstraint("tur IN ('chiquvchi', 'kiruvchi')", name="ck_soliq_esf_tur"),
        # Bitta buyurtma / hujjatga bitta tirik ESF
        Index(
            "ix_soliq_esf_order_tirik",
            "order_id",
            unique=True,
            postgresql_where=text("order_id IS NOT NULL AND holat NOT IN ('bekor', 'rad_etildi')"),
        ),
        Index(
            "ix_soliq_esf_doc_tirik",
            "stock_doc_id",
            "tur",
            unique=True,
            postgresql_where=text("stock_doc_id IS NOT NULL AND holat NOT IN ('bekor', 'rad_etildi')"),
        ),
        Index("ix_soliq_esf_holat", "holat", "keyingi_urinish"),
    )

    no: Mapped[str] = mapped_column(String(20), unique=True, kw_only=True)
    tur: Mapped[str] = mapped_column(String(10), kw_only=True)
    holat: Mapped[str] = mapped_column(String(14), kw_only=True)
    sana: Mapped[date] = mapped_column(Date, index=True, kw_only=True)
    #: Hisob-faktura raqami (operator / yetkazib beruvchi bergan)
    raqam: Mapped[str] = mapped_column(String(40), default="", kw_only=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("order.id"), default=None, kw_only=True)
    stock_doc_id: Mapped[int | None] = mapped_column(ForeignKey("stock_doc.id"), default=None, kw_only=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("client.id"), default=None, kw_only=True)
    #: Kontragent (chiquvchida — xaridor, kiruvchida — sotuvchi)
    kontragent: Mapped[str] = mapped_column(String(200), default="", kw_only=True)
    kontragent_stir: Mapped[str] = mapped_column(String(14), default="", kw_only=True)
    #: Yasalgan paytdagi rekvizitlar va qatorlar: [{nom, mxik, birlik, miqdor, narx, summa, qqs_foiz, qqs, jami}]
    rekvizit: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, kw_only=True)
    qatorlar: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default_factory=list, kw_only=True)
    #: `qqs` | `aylanma` — yasalgan sanadagi rejim
    rejim: Mapped[str] = mapped_column(String(8), kw_only=True)
    summa: Mapped[Decimal] = mapped_column(Numeric(16, 2), kw_only=True)
    qqs: Mapped[Decimal] = mapped_column(Numeric(16, 2), kw_only=True)
    jami: Mapped[Decimal] = mapped_column(Numeric(16, 2), kw_only=True)
    operator: Mapped[str] = mapped_column(String(20), kw_only=True)
    operator_id: Mapped[str | None] = mapped_column(String(64), unique=True, default=None, kw_only=True)
    xato: Mapped[str] = mapped_column(Text, default="", kw_only=True)
    urinish: Mapped[int] = mapped_column(default=0, kw_only=True)
    keyingi_urinish: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    yuborilgan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    javob_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    yaratgan_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)


class SoliqSinovOperator(BaseModel):
    """LOKAL SINOV operatori xotirasi (haqiqiy operator emas): yuborilgan ESF lar va «yetkazib beruvchilar
    yuborgan» kiruvchi ESF lar. Faqat `esf_operator = sinov` da ishlatiladi."""

    __tablename__ = "soliq_sinov_operator"

    operator_id: Mapped[str] = mapped_column(String(64), unique=True, kw_only=True)
    #: `chiquvchi` (bizdan) | `kiruvchi` (bizga)
    yonalish: Mapped[str] = mapped_column(String(10), kw_only=True)
    holat: Mapped[str] = mapped_column(String(14), kw_only=True)
    xabar: Mapped[str] = mapped_column(String(300), default="", kw_only=True)
    hujjat: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, kw_only=True)
