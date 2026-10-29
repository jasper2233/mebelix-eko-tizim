"""Kassa jadvallari (EKO TZ §7; prototip `Kassa.dc.html` / `kassa-core.js`).

Pul faqat ORDER bilan harakatlanadi: kirim (PKO) yoki chiqim (RKO). Order — JURNAL: o'zgartirilmaydi va
o'chirilmaydi (bazada trigger, mebel-erp-prototip qoidasi); xato order teskari STORNO orderi bilan tuzatiladi
(Moliya, ikki kalit). Hisob qoldig'i = boshlang'ich qoldiq + orderlar yig'indisi — alohida «qoldiq» ustuni yo'q,
ya'ni u jurnaldan ajrab qololmaydi.

Buyurtma bo'yicha to'langan summa — `kassa_taqsimot` (bitta order bir necha buyurtmaga taqsimlanishi mumkin:
mijoz qarzini to'lashda eng eski buyurtmadan yopiladi). Rezerv (EKO TZ §4.3) to'lovni shundan o'qiydi.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class KassaHisob(BaseModel):
    """Pul turgan joy: naqd kassa, karta terminali, bank hisobi."""

    __tablename__ = "kassa_hisob"

    kod: Mapped[str] = mapped_column(String(20), unique=True, kw_only=True)
    nom: Mapped[str] = mapped_column(String(100), kw_only=True)
    #: `naqd` | `karta` | `bank`
    tur: Mapped[str] = mapped_column(String(10), kw_only=True)
    #: Tizimga o'tish kunidagi qoldiq (naqd uchun birinchi smenada sanalgani)
    boshlangich: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=Decimal(0), kw_only=True)
    #: Bank / terminal komissiyasi, % (chiqimda alohida order bo'lib ushlanadi)
    komissiya_foiz: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal(0), kw_only=True)
    faol: Mapped[bool] = mapped_column(default=True, server_default="true", kw_only=True)


class KassaSmena(BaseModel):
    """Kassir smenasi. Naqd faqat ochiq smenada qabul qilinadi/beriladi; kassada bittadan ortiq ochiq smena yo'q."""

    __tablename__ = "kassa_smena"
    __table_args__ = (
        Index("ix_kassa_smena_ochiq", "hisob_id", unique=True, postgresql_where=text("yopilgan_at IS NULL")),
    )

    no: Mapped[str] = mapped_column(String(20), unique=True, kw_only=True)
    hisob_id: Mapped[int] = mapped_column(ForeignKey("kassa_hisob.id"), kw_only=True)
    ochgan_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    ochilgan_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), kw_only=True)
    #: Ochishda sanalgan naqd, hisobdagi (kitob) qoldiq va farqi; kupyuralar {nominal: soni}
    ochilish_naqd: Mapped[Decimal] = mapped_column(Numeric(16, 2), kw_only=True)
    ochilish_kitob: Mapped[Decimal] = mapped_column(Numeric(16, 2), kw_only=True)
    ochilish_kupyura: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, kw_only=True)
    yopgan_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    yopilgan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None, kw_only=True)
    yopilish_naqd: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), default=None, kw_only=True)
    yopilish_kupyura: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, kw_only=True)
    #: Yopishda: smenadagi naqd kirim/chiqim, kutilgan qoldiq, sanash farqi (farq orderi bilan yozilgan)
    kirim: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), default=None, kw_only=True)
    chiqim: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), default=None, kw_only=True)
    kutilgan: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), default=None, kw_only=True)
    farq: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), default=None, kw_only=True)
    #: Karta terminali Z-hisoboti (kassir kiritadi) va tizimdagi karta tushumi — solishtirish uchun
    terminal_z: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), default=None, kw_only=True)
    karta_tushum: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), default=None, kw_only=True)


class KassaOrder(BaseModel):
    """Kirim (PKO) yoki chiqim (RKO) orderi — JURNAL, faqat qo'shiladi (UPDATE/DELETE bazada taqiqlangan).

    `summa` — so'mda, musbat. STORNO orderi asl orderni teskari qaytaradi: `storno_of_id` bilan, `summa` manfiy."""

    __tablename__ = "kassa_order"
    __table_args__ = (
        CheckConstraint("summa > 0 OR storno_of_id IS NOT NULL", name="ck_kassa_order_summa"),
        CheckConstraint("tur IN ('kirim', 'chiqim')", name="ck_kassa_order_tur"),
        Index(
            "ix_kassa_order_storno_of", "storno_of_id", unique=True, postgresql_where=text("storno_of_id IS NOT NULL")
        ),
        Index("ix_kassa_order_hisob", "hisob_id", "id"),
    )

    #: `PKO-2026-0001` | `RKO-2026-0001`
    no: Mapped[str] = mapped_column(String(20), unique=True, kw_only=True)
    tur: Mapped[str] = mapped_column(String(6), kw_only=True)
    #: kirim: `avans` `tolov` `qarz` `sotuv` `boshqa`; chiqim: `taminotchi` `xarajat` `qaytarish` `inkassatsiya`
    #: `boshqa`; ikkalasida: `farq` (smena sanash farqi), `otkazma` (hisobdan hisobga), `komissiya`
    maqsad: Mapped[str] = mapped_column(String(12), kw_only=True)
    hisob_id: Mapped[int] = mapped_column(ForeignKey("kassa_hisob.id"), kw_only=True)
    summa: Mapped[Decimal] = mapped_column(Numeric(16, 2), kw_only=True)
    #: Dollarda qabul qilingan bo'lsa: dollar summasi va kurs (`summa` = valyuta × kurs)
    valyuta_summa: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None, kw_only=True)
    kurs: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None, kw_only=True)
    smena_id: Mapped[int | None] = mapped_column(ForeignKey("kassa_smena.id"), index=True, default=None, kw_only=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("order.id"), index=True, default=None, kw_only=True)
    client_id: Mapped[int | None] = mapped_column(ForeignKey("client.id"), index=True, default=None, kw_only=True)
    stock_doc_id: Mapped[int | None] = mapped_column(ForeignKey("stock_doc.id"), default=None, kw_only=True)
    #: Kimdan / kimga (mijoz, yetkazib beruvchi, xodim) — matn
    kontragent: Mapped[str] = mapped_column(String(150), default="", kw_only=True)
    #: Xarajat turkumi (chiqimda)
    turkum: Mapped[str] = mapped_column(String(60), default="", kw_only=True)
    izoh: Mapped[str] = mapped_column(String(300), default="", kw_only=True)
    #: Aralash to'lov (naqd + karta) va o'tkazma qismlari bitta guruh
    guruh: Mapped[str | None] = mapped_column(String(20), index=True, default=None, kw_only=True)
    #: Naqd qabulda: mijoz bergan pul va qaytim
    mijoz_berdi: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), default=None, kw_only=True)
    qaytim: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), default=None, kw_only=True)
    kassir_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
    storno_of_id: Mapped[int | None] = mapped_column(ForeignKey("kassa_order.id"), default=None, kw_only=True)


class KassaTaqsimot(BaseModel):
    """Order summasi buyurtmalarga taqsimoti — buyurtma bo'yicha to'langan summa shundan (rezerv, qarz). Jurnal."""

    __tablename__ = "kassa_taqsimot"

    kassa_order_id: Mapped[int] = mapped_column(ForeignKey("kassa_order.id"), index=True, kw_only=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("order.id"), index=True, kw_only=True)
    #: Kirim — musbat, buyurtma bo'yicha qaytarish (chiqim) va storno — manfiy
    summa: Mapped[Decimal] = mapped_column(Numeric(16, 2), kw_only=True)
