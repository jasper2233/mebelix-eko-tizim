from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseModel
from .enums import PaymentMethod, SaleStatus, StockCatalog, StockMoveKind, db_enum


class StockItem(BaseModel):
    """MATERIALLAR OMBORI tovarsi — kod, qoldiq va narx.

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
    #: Minimal zaxira — bundan pastda tovar "buyurtma berish kerak" deb belgilanadi.
    #: 0 = nazorat qilinmaydi (katalogda Min ustuni bo'sh kelgan tovarlar).
    min_qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=Decimal(0), kw_only=True)
    purchase_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), default=None, kw_only=True)
    purchase_uzs: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None, kw_only=True)
    sale_uzs: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None, kw_only=True)
    note: Mapped[str | None] = mapped_column(String(200), default=None, kw_only=True)


class Sale(BaseModel):
    """Ombordan SOTUV hujjati — mijozga to'g'ridan-to'g'ri sotilgan tovar.

    Satrlari alohida jadval emas, `StockMove.sale_id` orqali bog'lanadi: sotuv
    satri va ombor harakati bir xil voqea, ikki joyda saqlansa ular bir-biridan
    ajralib ketishi mumkin edi.

    Qarz = `total_uzs - paid_uzs`. `paid_uzs` — `Payment` yig'indisining keshi:
    qarzdorlar ro'yxati eng ko'p so'raladigan sahifa, uni har safar to'lovlarni
    yig'ib hisoblash sekin bo'lardi.
    """

    __tablename__ = "sale"

    organization_id: Mapped[int] = mapped_column(ForeignKey("organization.id"), default=1, kw_only=True)
    #: Qarzga sotilganda MAJBURIY (kimdan undirishni bilish kerak), naqd sotuvda
    #: bo'lmasligi mumkin — o'tkinchi xaridor.
    client_id: Mapped[int | None] = mapped_column(ForeignKey("client.id"), default=None, index=True, kw_only=True)
    total_uzs: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal(0), kw_only=True)
    paid_uzs: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal(0), kw_only=True)
    status: Mapped[SaleStatus] = mapped_column(db_enum(SaleStatus), default=SaleStatus.DEBT, index=True, kw_only=True)
    note: Mapped[str | None] = mapped_column(String(200), default=None, kw_only=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)


class Payment(BaseModel):
    """Sotuvga tushgan to'lov. Bo'lib-bo'lib to'lash uchun bir sotuvda bir nechta.

    Ayrim yozuv sifatida saqlanadi — `sale.paid_uzs` ni shunchaki yangilash
    "qachon va qanday to'ladi" degan savolni yo'qotardi.
    """

    __tablename__ = "payment"

    sale_id: Mapped[int] = mapped_column(ForeignKey("sale.id"), index=True, kw_only=True)
    amount_uzs: Mapped[Decimal] = mapped_column(Numeric(14, 2), kw_only=True)
    method: Mapped[PaymentMethod] = mapped_column(db_enum(PaymentMethod), default=PaymentMethod.CASH, kw_only=True)
    note: Mapped[str | None] = mapped_column(String(200), default=None, kw_only=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)


class StockMove(BaseModel):
    """Ombordagi HAR o'zgarish. `stock_item.qty` shu qatorlar yig'indisining keshi.

    Ilgari harakat faqat audit logga yozilardi. Miqdorni tuzatish uchun u yetardi,
    lekin talab o'zgardi: buyurtmaga berilgan furnituraning tannarxi va sotuv
    daromadi hisobot bo'lib chiqishi kerak — JSON izohdan hisobot chiqmaydi.
    """

    __tablename__ = "stock_move"

    __table_args__ = (Index("ix_stock_move_order", "order_id"), Index("ix_stock_move_sale", "sale_id"))

    stock_item_id: Mapped[int] = mapped_column(ForeignKey("stock_item.id"), index=True, kw_only=True)
    #: ISHORALI: kirim musbat, chiqim manfiy. Ikki ustun (kirim/chiqim) o'rniga
    #: bittasi — yig'indi to'g'ridan-to'g'ri qoldiqni beradi.
    qty: Mapped[Decimal] = mapped_column(Numeric(12, 3), kw_only=True)
    kind: Mapped[StockMoveKind] = mapped_column(db_enum(StockMoveKind), index=True, kw_only=True)
    #: `kind=BUYURTMA` da majburiy — tannarx shu buyurtmaga yoziladi
    order_id: Mapped[int | None] = mapped_column(ForeignKey("order.id"), default=None, kw_only=True)
    #: `kind=SOTUV` da majburiy — sotuv hujjatining satri
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("sale.id"), default=None, kw_only=True)
    #: Birlik narxi HARAKAT PAYTIDA muzlatiladi: katalogdagi narx keyin
    #: o'zgaradi, o'tgan oyning hisoboti esa o'zgarmasligi kerak.
    price_uzs: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None, kw_only=True)
    note: Mapped[str | None] = mapped_column(String(200), default=None, kw_only=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), default=None, kw_only=True)
