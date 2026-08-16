from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import StockCatalog, db_enum


class StockItem(BaseModel):
    """MATERIALLAR OMBORI pozitsiyasi — kod, qoldiq va narx.

    `Material` dan AYRIM jadval, garchi ikkalasi ham "material" desa ham:

    * `Material` — GibLab `.project` faylidan AVTOMAT to'ladigan ishlab chiqarish
      katalogi (plita nomi, qalinlik, kromka eni). Uni ingest qayta yozadi va
      qoldiq tushunchasi yo'q.
    * `StockItem` — omborchi YURITADIGAN katalog: kod bo'yicha qoldiq, minimal
      zaxira va narx. Furnitura ham bor (u `.project` da umuman uchramaydi).

    Ularni bitta jadvalga qo'shsak, har `.project` yuklanishida ingest omborchining
    qoldiq va narxini bosib ketardi.

    Kod `K-GG-MMM-VV` (`F-RC-001-01`): katalog - guruh - model - variant. Ombor
    hisobi variant darajasida yuritiladi — "Ruchka 0014" emas, "Ruchka 0014 bronza
    128", chunki qoldiq aynan shu buyumga tegishli.
    """

    __tablename__ = "stock_item"

    __table_args__ = (Index("ix_stock_item_code", "code", unique=True, postgresql_where=text("NOT is_deleted")),)

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    code: Mapped[str] = mapped_column(String(20), kw_only=True)
    catalog: Mapped[StockCatalog] = mapped_column(db_enum(StockCatalog), index=True, kw_only=True)
    group_code: Mapped[str] = mapped_column(String(4), index=True, kw_only=True)
    group_name: Mapped[str] = mapped_column(String(60), kw_only=True)
    name: Mapped[str] = mapped_column(String(200), kw_only=True)
    #: Variantni ajratuvchi belgi: furniturada rang, materialda struktura
    variant: Mapped[str | None] = mapped_column(String(40), default=None, kw_only=True)
    size: Mapped[str | None] = mapped_column(String(40), default=None, kw_only=True)
    unit: Mapped[str | None] = mapped_column(String(16), default=None, kw_only=True)
    #: Qoldiq. Kasr: kromka va smola metr/kg bilan o'lchanadi.
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal(0), kw_only=True)
    #: Minimal zaxira — bundan pastda pozitsiya "buyurtma berish kerak" deb belgilanadi.
    #: 0 = nazorat qilinmaydi (katalogda Min ustuni bo'sh kelgan pozitsiyalar).
    min_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal(0), kw_only=True)
    purchase_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), default=None, kw_only=True)
    purchase_uzs: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None, kw_only=True)
    sale_uzs: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None, kw_only=True)
    note: Mapped[str | None] = mapped_column(String(200), default=None, kw_only=True)
